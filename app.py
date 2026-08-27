"""
Agente de WhatsApp con Claude + Twilio + Google Sheets.

Flujo:
1. Twilio reenvía a este servidor los mensajes de WhatsApp entrantes vía
   webhook HTTP POST (application/x-www-form-urlencoded).
2. Se valida la firma de Twilio para confirmar que la petición es legítima.
3. El mensaje se clasifica por palabras clave para detectar prospectos.
4. Si es un prospecto calificado, se guarda en Google Sheets.
5. Se genera una respuesta con la API de Claude.
6. Se responde a Twilio con TwiML para que la respuesta se envíe
   automáticamente por WhatsApp.

Ejecutar en desarrollo:  python app.py
Ejecutar en producción:  gunicorn -w 2 -b 0.0.0.0:$PORT app:app
"""

import logging

from flask import Flask, Response, request
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from claude_client import ClaudeReplyGenerator
from config import Config, ConfigError
from logging_config import setup_logging
from prospect_classifier import classify_message
from sheets_client import SheetsClient, SheetsClientError

setup_logging()
logger = logging.getLogger("whatsapp_agent")

app = Flask(__name__)

# --- Validación de configuración al arrancar ---
try:
    Config.validate()
except ConfigError as exc:
    logger.critical("Configuración inválida al arrancar: %s", exc)
    raise

PROSPECT_KEYWORDS = Config.get_prospect_keywords()
logger.info("Palabras clave de calificación de prospectos: %s", list(PROSPECT_KEYWORDS.keys()))

twilio_validator = RequestValidator(Config.TWILIO_AUTH_TOKEN)

claude_generator = ClaudeReplyGenerator(
    api_key=Config.ANTHROPIC_API_KEY,
    model=Config.CLAUDE_MODEL,
    business_name=Config.BUSINESS_NAME,
    max_tokens=Config.CLAUDE_MAX_TOKENS,
    effort=Config.CLAUDE_EFFORT,
)

# El cliente de Google Sheets se inicializa en modo "best effort": si falla
# (credenciales inválidas, hoja no compartida, etc.) el bot sigue
# respondiendo mensajes, pero no podrá guardar prospectos hasta que se
# corrija la configuración. Cada intento de guardado fallido queda
# registrado en el log.
sheets_client = None
if Config.sheets_configured():
    try:
        sheets_client = SheetsClient(
            sheet_url=Config.GOOGLE_SHEETS_URL,
            service_account_info=Config.get_google_service_account_info(),
        )
    except (SheetsClientError, ConfigError) as exc:
        logger.error(
            "No se pudo inicializar Google Sheets; el bot seguirá funcionando "
            "sin guardar prospectos hasta corregir la configuración. Detalle: %s",
            exc,
        )
else:
    logger.warning(
        "GOOGLE_SHEETS_URL / GOOGLE_SERVICE_ACCOUNT_JSON no configurados: "
        "los prospectos calificados no se guardarán hasta que se configuren "
        "(ver README.md)."
    )


def _validate_twilio_request() -> bool:
    """Valida que la petición entrante realmente provenga de Twilio."""
    if not Config.VALIDATE_TWILIO_SIGNATURE:
        logger.warning("Validación de firma de Twilio DESACTIVADA (solo para pruebas).")
        return True

    signature = request.headers.get("X-Twilio-Signature", "")
    # Twilio firma sobre la URL pública exacta que invocó. Detrás de un
    # proxy (Replit, etc.) request.url puede venir como http://; se
    # reconstruye con el esquema original si Twilio lo indica en el header
    # estándar de proxy inverso.
    url = request.url
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    if forwarded_proto == "https" and url.startswith("http://"):
        url = "https://" + url[len("http://"):]

    is_valid = twilio_validator.validate(url, request.form.to_dict(), signature)
    if not is_valid:
        logger.warning("Firma de Twilio inválida para la petición a %s.", url)
    return is_valid


def _empty_twiml_response(status_code: int = 200) -> Response:
    """TwiML vacío: Twilio no reenvía ningún mensaje adicional al usuario."""
    return Response(str(MessagingResponse()), mimetype="application/xml", status=status_code)


@app.route("/health", methods=["GET"])
def health():
    """Endpoint de salud para monitoreo (UptimeRobot, Replit Deployments, etc.)."""
    return {
        "status": "ok",
        "sheets_connected": sheets_client is not None,
    }, 200


@app.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook():
    try:
        if not _validate_twilio_request():
            return _empty_twiml_response(status_code=403)

        incoming_body = (request.form.get("Body") or "").strip()
        from_number = (request.form.get("From") or "").replace("whatsapp:", "").strip()
        profile_name = (request.form.get("ProfileName") or "").strip() or "Desconocido"
        message_sid = request.form.get("MessageSid", "sin-sid")

        logger.info(
            "Mensaje entrante | sid=%s | de=%s | nombre=%s | cuerpo=%r",
            message_sid, from_number, profile_name, incoming_body[:200],
        )

        if not incoming_body:
            logger.info("Mensaje sin texto (posible media); se ignora la clasificación/IA.")
            return _empty_twiml_response()

        # --- 1. Clasificación de prospecto ---
        try:
            classification_result = classify_message(incoming_body, PROSPECT_KEYWORDS)
        except Exception:
            logger.exception("Error al clasificar el mensaje; se continúa sin clasificar.")
            classification_result = {"is_prospect": False, "classification": None, "matched_keywords": []}

        if classification_result["is_prospect"]:
            logger.info(
                "Prospecto calificado detectado | sid=%s | clasificación=%s | keywords=%s",
                message_sid, classification_result["classification"], classification_result["matched_keywords"],
            )
            if sheets_client is not None:
                try:
                    sheets_client.append_prospect(
                        nombre=profile_name,
                        telefono=from_number,
                        mensaje=incoming_body,
                        clasificacion=classification_result["classification"],
                    )
                except SheetsClientError:
                    logger.exception(
                        "No se pudo guardar el prospecto en Google Sheets (sid=%s).", message_sid
                    )
            else:
                logger.warning(
                    "Prospecto calificado pero Google Sheets no está configurado/disponible; "
                    "no se guardó (sid=%s).", message_sid,
                )
        else:
            logger.info("Mensaje no calificado como prospecto | sid=%s", message_sid)

        # --- 2. Generación de respuesta con Claude ---
        reply_text = claude_generator.generate_reply(incoming_body)

        # --- 3. Respuesta TwiML ---
        twiml = MessagingResponse()
        twiml.message(reply_text)
        logger.info("Respuesta enviada | sid=%s | longitud=%d", message_sid, len(reply_text))
        return Response(str(twiml), mimetype="application/xml", status=200)

    except Exception:
        # Nunca se debe dejar caer el webhook: se registra el error y se
        # responde con TwiML vacío para que Twilio no reintente en bucle.
        logger.exception("Error no controlado procesando el webhook de WhatsApp.")
        return _empty_twiml_response(status_code=200)


@app.errorhandler(404)
def not_found(_error):
    return {"error": "not found"}, 404


@app.errorhandler(500)
def server_error(error):
    logger.exception("Error interno del servidor: %s", error)
    return {"error": "internal server error"}, 500


if __name__ == "__main__":
    logger.info("Iniciando servidor de desarrollo en el puerto %s.", Config.PORT)
    app.run(host="0.0.0.0", port=Config.PORT)
