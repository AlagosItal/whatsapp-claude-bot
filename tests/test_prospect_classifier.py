import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prospect_classifier import classify_message

KEYWORDS = {
    "consulta": "Consulta General",
    "precio": "Consulta de Precio",
    "informacion": "Solicitud de Información",
    "venta": "Interés de Venta",
    "necesito": "Necesidad Expresada",
}


class ProspectClassifierTests(unittest.TestCase):
    def test_matches_keyword_with_accents_and_case(self):
        result = classify_message("Quisiera más INFORMACIÓN sobre sus servicios", KEYWORDS)
        self.assertTrue(result["is_prospect"])
        self.assertEqual(result["classification"], "Solicitud de Información")

    def test_matches_price_keyword(self):
        result = classify_message("¿Cuál es el precio del producto X?", KEYWORDS)
        self.assertTrue(result["is_prospect"])
        self.assertEqual(result["classification"], "Consulta de Precio")

    def test_no_match_returns_not_prospect(self):
        result = classify_message("Hola, ¿cómo estás?", KEYWORDS)
        self.assertFalse(result["is_prospect"])
        self.assertIsNone(result["classification"])

    def test_avoids_partial_word_false_positive(self):
        # "precioso" no debe matchear la palabra clave "precio" (match de palabra completa)
        result = classify_message("Qué día tan precioso hace hoy", KEYWORDS)
        self.assertFalse(result["is_prospect"])

    def test_multiple_keywords_combines_labels(self):
        result = classify_message("Necesito una consulta sobre el precio", KEYWORDS)
        self.assertTrue(result["is_prospect"])
        for label in ("Necesidad Expresada", "Consulta General", "Consulta de Precio"):
            self.assertIn(label, result["classification"])

    def test_empty_message(self):
        result = classify_message("", KEYWORDS)
        self.assertFalse(result["is_prospect"])


if __name__ == "__main__":
    unittest.main()
