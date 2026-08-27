"""
Wrapper sobre gspread para guardar prospectos calificados en Google Sheets.

Columnas escritas en la hoja "Prospectos": Fecha, Nombre, Teléfono, Mensaje,
Clasificación. Si la hoja de cálculo aún no tiene esa pestaña o no tiene los
encabezados, este módulo los crea automáticamente en el primer uso.
"""

import logging
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

WORKSHEET_NAME = "Prospectos"
HEADERS = ["Fecha", "Nombre", "Teléfono", "Mensaje", "Clasificación"]


class SheetsClientError(RuntimeError):
    """Error irrecuperable al inicializar o usar Google Sheets."""


class SheetsClient:
    """Cliente para agregar filas de prospectos a una Google Sheet existente."""

    def __init__(self, sheet_url: str, service_account_info: dict):
        try:
            credentials = Credentials.from_service_account_info(
                service_account_info, scopes=SCOPES
            )
            self._gc = gspread.authorize(credentials)
            self._spreadsheet = self._gc.open_by_url(sheet_url)
        except gspread.exceptions.APIError as exc:
            raise SheetsClientError(
                f"No se pudo abrir la hoja de cálculo (revisa que la cuenta de "
                f"servicio tenga acceso de Editor a la hoja): {exc}"
            ) from exc
        except Exception as exc:
            raise SheetsClientError(f"No se pudo inicializar el cliente de Google Sheets: {exc}") from exc

        self._worksheet = self._get_or_create_worksheet()
        logger.info("Cliente de Google Sheets inicializado correctamente sobre hoja '%s'.", WORKSHEET_NAME)

    def _get_or_create_worksheet(self):
        try:
            worksheet = self._spreadsheet.worksheet(WORKSHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            logger.info("La pestaña '%s' no existe; creándola.", WORKSHEET_NAME)
            worksheet = self._spreadsheet.add_worksheet(
                title=WORKSHEET_NAME, rows=1000, cols=len(HEADERS)
            )

        try:
            first_row = worksheet.row_values(1)
        except gspread.exceptions.APIError as exc:
            raise SheetsClientError(f"No se pudo leer la primera fila de la hoja: {exc}") from exc

        if first_row != HEADERS:
            worksheet.update("A1", [HEADERS])
            logger.info("Encabezados %s escritos en la pestaña '%s'.", HEADERS, WORKSHEET_NAME)

        return worksheet

    def append_prospect(self, nombre: str, telefono: str, mensaje: str, clasificacion: str) -> None:
        """Agrega una fila con los datos del prospecto calificado.

        Lanza SheetsClientError si la escritura falla, para que el llamador
        decida cómo manejarlo (registrar y continuar, típicamente).
        """
        fecha = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        row = [fecha, nombre or "Desconocido", telefono or "", mensaje or "", clasificacion or ""]

        try:
            self._worksheet.append_row(row, value_input_option="USER_ENTERED")
        except gspread.exceptions.APIError as exc:
            raise SheetsClientError(f"Error de la API de Google Sheets al agregar fila: {exc}") from exc
        except Exception as exc:
            raise SheetsClientError(f"Error inesperado al agregar fila a Google Sheets: {exc}") from exc

        logger.info(
            "Prospecto guardado en Google Sheets | tel=%s | clasificación=%s | fecha=%s",
            telefono, clasificacion, fecha,
        )
