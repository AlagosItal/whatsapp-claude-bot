"""
Clasificador de prospectos basado en palabras clave.

Un mensaje entrante se considera un "prospecto calificado" si contiene
alguna de las palabras clave configuradas (por defecto: "consulta",
"precio", "información", "venta", "necesito"). La comparación ignora
mayúsculas/minúsculas y acentos, y solo hace match de palabra completa
(para evitar falsos positivos como "precioso" al buscar "precio").
"""

import re
import unicodedata


def _normalize(text: str) -> str:
    """Minúsculas y sin acentos, para comparar de forma robusta."""
    text = (text or "").lower().strip()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def classify_message(message: str, keywords: dict) -> dict:
    """Clasifica un mensaje según las palabras clave configuradas.

    Args:
        message: texto del mensaje de WhatsApp.
        keywords: dict {palabra_clave: etiqueta_de_clasificación}.

    Returns:
        dict con:
            is_prospect (bool): True si el mensaje califica como prospecto.
            classification (str | None): etiqueta a guardar en la hoja.
            matched_keywords (list[str]): palabras clave encontradas.
    """
    normalized = _normalize(message)
    matched = []

    for keyword, label in keywords.items():
        keyword_norm = _normalize(keyword)
        if not keyword_norm:
            continue
        pattern = r"\b" + re.escape(keyword_norm) + r"\b"
        if re.search(pattern, normalized):
            matched.append((keyword, label))

    if not matched:
        return {"is_prospect": False, "classification": None, "matched_keywords": []}

    # Si varias palabras clave distintas coinciden, se combinan las etiquetas
    # únicas en un solo valor de clasificación, preservando el orden.
    unique_labels = list(dict.fromkeys(label for _, label in matched))
    classification = unique_labels[0] if len(unique_labels) == 1 else " / ".join(unique_labels)

    return {
        "is_prospect": True,
        "classification": classification,
        "matched_keywords": [kw for kw, _ in matched],
    }
