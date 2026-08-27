"""
Carga y valida la configuración del agente a partir de variables de entorno.

Todas las credenciales se leen exclusivamente de variables de entorno
(en Replit: pestaña "Secrets"). Nunca se deben escribir credenciales
directamente en el código fuente.
"""

import json
import logging
import os

from dotenv import load_dotenv

# En Replit las variables de entorno ya están inyectadas por la pestaña
# "Secrets", pero cargar un .env local es útil para desarrollo/pruebas.
load_dotenv()

logger = logging.getLogger(__name__)


class ConfigError(RuntimeError):
    """Se lanza cuando falta una variable de entorno obligatoria o es inválida."""


class Config:
    # --- Twilio ---
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()

    # --- Anthropic (Claude) ---
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5").strip()
    CLAUDE_MAX_TOKENS = int(os.environ.get("CLAUDE_MAX_TOKENS", "1024"))
    CLAUDE_EFFORT = os.environ.get("CLAUDE_EFFORT", "low").strip()

    # --- Google Sheets ---
    GOOGLE_SHEETS_URL = os.environ.get("GOOGLE_SHEETS_URL", "").strip()
    # Contenido completo del JSON de la cuenta de servicio de Google
    # (se pega tal cual en un Secret de Replit).
    GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

    # --- Negocio / prompt ---
    BUSINESS_NAME = os.environ.get("BUSINESS_NAME", "nuestra empresa").strip()

    # --- Seguridad ---
    # Permite desactivar la validación de firma de Twilio solo para pruebas
    # locales (nunca debe estar en "false" en producción).
    VALIDATE_TWILIO_SIGNATURE = os.environ.get(
        "VALIDATE_TWILIO_SIGNATURE", "true"
    ).strip().lower() not in ("false", "0", "no")

    # --- Servidor ---
    PORT = int(os.environ.get("PORT", "8080"))

    # --- Palabras clave para calificar prospectos ---
    # Se puede sobreescribir con la variable de entorno PROSPECT_KEYWORDS,
    # separando palabra:etiqueta con "=" y pares con ",".
    # Ejemplo: "precio=Consulta de Precio,demo=Solicitud de Demo"
    _DEFAULT_KEYWORDS = {
        "consulta": "Consulta General",
        "precio": "Consulta de Precio",
        "informacion": "Solicitud de Información",
        "venta": "Interés de Venta",
        "necesito": "Necesidad Expresada",
    }

    @classmethod
    def get_prospect_keywords(cls):
        raw = os.environ.get("PROSPECT_KEYWORDS", "").strip()
        if not raw:
            return dict(cls._DEFAULT_KEYWORDS)
        keywords = {}
        for pair in raw.split(","):
            if "=" not in pair:
                continue
            key, _, label = pair.partition("=")
            key = key.strip().lower()
            label = label.strip()
            if key and label:
                keywords[key] = label
        return keywords or dict(cls._DEFAULT_KEYWORDS)

    @classmethod
    def get_google_service_account_info(cls):
        """Parsea el JSON de la cuenta de servicio de Google. Lanza ConfigError si es inválido."""
        if not cls.GOOGLE_SERVICE_ACCOUNT_JSON:
            raise ConfigError(
                "Falta la variable de entorno GOOGLE_SERVICE_ACCOUNT_JSON "
                "(contenido del archivo JSON de la cuenta de servicio de Google)."
            )
        try:
            return json.loads(cls.GOOGLE_SERVICE_ACCOUNT_JSON)
        except json.JSONDecodeError as exc:
            raise ConfigError(
                f"GOOGLE_SERVICE_ACCOUNT_JSON no contiene JSON válido: {exc}"
            ) from exc

    @classmethod
    def validate(cls):
        """Valida que las variables de entorno estrictamente obligatorias
        para levantar el servidor estén presentes (Twilio + Anthropic).

        Google Sheets se valida por separado (ver `sheets_configured`) porque
        el bot puede operar en modo degradado (sin guardar prospectos) si
        aún no se configuró la hoja de cálculo.

        Lanza ConfigError con un mensaje claro sobre qué falta.
        """
        missing = []
        if not cls.TWILIO_ACCOUNT_SID:
            missing.append("TWILIO_ACCOUNT_SID")
        if not cls.TWILIO_AUTH_TOKEN:
            missing.append("TWILIO_AUTH_TOKEN")
        if not cls.ANTHROPIC_API_KEY:
            missing.append("ANTHROPIC_API_KEY")

        if missing:
            raise ConfigError(
                "Faltan variables de entorno obligatorias: " + ", ".join(missing) +
                ". Configúralas en la pestaña 'Secrets' de Replit (ver README.md)."
            )
        logger.info("Configuración validada correctamente.")

    @classmethod
    def sheets_configured(cls) -> bool:
        """True si hay suficiente configuración para intentar conectar con Google Sheets."""
        return bool(cls.GOOGLE_SHEETS_URL and cls.GOOGLE_SERVICE_ACCOUNT_JSON)
