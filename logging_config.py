"""
Configuración centralizada de logging para el agente.

Registra todas las acciones relevantes (mensajes entrantes, clasificación de
prospectos, llamadas a Claude, escrituras en Google Sheets, respuestas
enviadas y errores) tanto en consola (stdout, visible en la consola de
Replit) como en un archivo rotativo en disco.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.environ.get("LOG_DIR", "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging():
    """Configura el logger raíz. Debe llamarse una sola vez al iniciar la app."""
    os.makedirs(LOG_DIR, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # Evita handlers duplicados si setup_logging() se llama más de una vez
    # (por ejemplo, bajo el reloader de Flask en modo debug).
    if root_logger.handlers:
        return root_logger

    formatter = logging.Formatter(LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    try:
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except OSError:
        # En algunos entornos de solo lectura no se puede escribir a disco;
        # seguimos funcionando solo con el log de consola.
        root_logger.warning(
            "No se pudo crear el archivo de log en '%s'; se continúa solo con logging a consola.",
            LOG_FILE,
        )

    # Silenciar ruido excesivo de librerías HTTP de terceros.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    return root_logger
