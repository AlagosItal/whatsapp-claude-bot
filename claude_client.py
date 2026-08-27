"""
Wrapper sobre el SDK oficial de Anthropic para generar respuestas
automáticas a mensajes de WhatsApp.
"""

import logging

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_REPLY = (
    "Gracias por tu mensaje. En este momento no pudimos procesar tu consulta "
    "automáticamente, pero un miembro de nuestro equipo la revisará en breve."
)


class ClaudeReplyGenerator:
    """Genera respuestas de WhatsApp usando la API de Claude."""

    def __init__(self, api_key: str, model: str, business_name: str,
                 max_tokens: int = 1024, effort: str = "low"):
        self._client = anthropic.Anthropic(api_key=api_key, timeout=20.0, max_retries=2)
        self._model = model
        self._max_tokens = max_tokens
        self._effort = effort
        self._system_prompt = (
            f"Eres el asistente virtual de atención al cliente de {business_name} "
            "en WhatsApp. Respondes en español, de forma breve (máximo 4 frases), "
            "cordial y profesional. Si el cliente pregunta por precios, productos, "
            "servicios o quiere hacer una compra, responde con información general "
            "útil y explícale que un asesor humano se pondrá en contacto para "
            "brindarle más detalles. No inventes precios, políticas ni datos que no "
            "tengas certeza de conocer; en ese caso indica que un asesor lo "
            "confirmará."
        )

    def generate_reply(self, incoming_message: str) -> str:
        """Genera una respuesta para `incoming_message`.

        Si la llamada a la API falla por cualquier motivo, se registra el
        error y se devuelve una respuesta de repliegue (fallback) para que
        el usuario de WhatsApp siempre reciba una contestación.
        """
        message_preview = (incoming_message or "")[:120]
        logger.info("Solicitando respuesta a Claude para mensaje: %r", message_preview)

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._system_prompt,
                messages=[{"role": "user", "content": incoming_message or ""}],
                output_config={"effort": self._effort},
            )
        except anthropic.BadRequestError as exc:
            logger.error("Claude: solicitud inválida: %s", exc)
            return DEFAULT_FALLBACK_REPLY
        except anthropic.AuthenticationError:
            logger.error("Claude: ANTHROPIC_API_KEY inválida o ausente.")
            return DEFAULT_FALLBACK_REPLY
        except anthropic.PermissionDeniedError:
            logger.error("Claude: la API key no tiene permisos para este modelo/endpoint.")
            return DEFAULT_FALLBACK_REPLY
        except anthropic.NotFoundError:
            logger.error("Claude: modelo o endpoint no encontrado (revisa CLAUDE_MODEL).")
            return DEFAULT_FALLBACK_REPLY
        except anthropic.RateLimitError as exc:
            retry_after = exc.response.headers.get("retry-after", "desconocido") if exc.response else "desconocido"
            logger.warning("Claude: límite de tasa alcanzado. Retry-After=%s", retry_after)
            return DEFAULT_FALLBACK_REPLY
        except anthropic.APIConnectionError as exc:
            logger.error("Claude: error de conexión de red: %s", exc)
            return DEFAULT_FALLBACK_REPLY
        except anthropic.APIStatusError as exc:
            logger.error("Claude: error de API (status=%s): %s", exc.status_code, exc.message)
            return DEFAULT_FALLBACK_REPLY
        except Exception:
            logger.exception("Claude: error inesperado al generar la respuesta.")
            return DEFAULT_FALLBACK_REPLY

        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None) if response.stop_details else None
            logger.warning("Claude rechazó la solicitud por seguridad (categoría=%s).", category)
            return DEFAULT_FALLBACK_REPLY

        reply_text = next(
            (block.text for block in response.content if block.type == "text"), ""
        ).strip()

        if not reply_text:
            logger.warning("Claude devolvió una respuesta vacía; se usa el mensaje de repliegue.")
            return DEFAULT_FALLBACK_REPLY

        logger.info("Respuesta de Claude generada correctamente (%d caracteres).", len(reply_text))
        return reply_text
