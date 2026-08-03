"""Testes do guardião lexical da copy."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copy_lexicon import CopyLexicon


class TestCopyLexicon(unittest.TestCase):
    def setUp(self):
        self.lexicon = CopyLexicon(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

    def test_detecta_expressao_proibida(self):
        violations = self.lexicon.scan_violations(
            "O Guardian AI monitora conversas privadas no WhatsApp."
        )
        self.assertTrue(violations)
        self.assertEqual(violations[0]["id"], "monitora_conversas")

    def test_substitui_chat_privado(self):
        text = self.lexicon.apply_substitutions("Golpe em chat privado.")
        self.assertEqual(text, "Golpe em chat do WhatsApp.")

    def test_sanitiza_todos_os_campos(self):
        creative = {
            "desenvolvimento_copy": (
                "O Guardian AI monitora suas conversas privadas e age no chat privado."
            ),
            "gancho_atencao_inicial": "Golpe no chat privado",
        }
        result, violations = self.lexicon.sanitize_creative(creative)
        self.assertEqual(violations, [])
        self.assertNotIn("monitora suas conversas privadas", result["desenvolvimento_copy"].lower())
        self.assertNotIn("chat privado", result["gancho_atencao_inicial"].lower())

    def test_copy_limpa_e_compliant(self):
        creative = {
            "desenvolvimento_copy": (
                "O Guardian AI detecta ameaças e envia um alerta imediato no chat do WhatsApp."
            )
        }
        self.assertTrue(self.lexicon.is_compliant(creative))

    def test_prompt_contem_guia(self):
        prompt = self.lexicon.format_for_prompt()
        self.assertIn("EXPRESSÕES PROIBIDAS", prompt)
        self.assertIn("chat privado", prompt)
        self.assertIn("chat do WhatsApp", prompt)


if __name__ == "__main__":
    unittest.main()
