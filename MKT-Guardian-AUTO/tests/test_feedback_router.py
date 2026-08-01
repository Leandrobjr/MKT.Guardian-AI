"""Testes — feedback_router.py (Fase 5)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feedback_router import (
    classify_improvement,
    correction_tag,
    detect_narrative_override,
    describe_plan,
    format_menu_conflict,
)


class TestFeedbackRouter(unittest.TestCase):
    def test_narrative_not_visual_only(self):
        plan = classify_improvement("Quero estória de escola com diretor, não mãe em casa")
        self.assertTrue(plan["narrative"])
        self.assertFalse(plan.get("visual_only"))
        self.assertEqual(plan["primary_category"], "narrativa")

    def test_visual_only_pessoa(self):
        plan = classify_improvement("Trocar a pessoa da foto, aparência mais organizada")
        self.assertTrue(plan.get("visual_only"))

    def test_headline_only(self):
        plan = classify_improvement("Mudar só a manchete, headline mais urgente")
        self.assertTrue(plan.get("headline_only"))
        self.assertEqual(plan["primary_category"], "headline")

    def test_golpe_intent(self):
        plan = classify_improvement("Quero outro golpe, trocar a frase do PIX no card")
        self.assertTrue(plan.get("golpe"))
        self.assertEqual(plan["primary_category"], "golpe")

    def test_detect_override_escola(self):
        ov = detect_narrative_override("Quero estória de escola com diretor alertando pais")
        self.assertEqual(ov.get("publico_slug"), "escolas")

    def test_detect_override_idosos_golpe(self):
        ov = detect_narrative_override("Focar em idoso e golpe do falso parente pedindo PIX")
        self.assertEqual(ov.get("publico_slug"), "idosos")
        self.assertEqual(ov.get("golpe_id"), "falso_parente")

    def test_correction_tag(self):
        plan = classify_improvement("Mudar headline")
        self.assertEqual(correction_tag(plan), "[headline]")

    def test_menu_conflict_message(self):
        msg = format_menu_conflict(
            "pais",
            "grooming",
            {"publico_slug": "escolas", "golpe_id": "phishing"},
        )
        self.assertIn("CONFLITO", msg)
        self.assertIn("escolas", msg)

    def test_user_surgical_edit_no_override(self):
        """Regressão: editar frase/card não deve trocar combo para escolas+pix."""
        fb = (
            "No roteiro, altere a seguinte frase: O Guardian AI monitora essas conversas privadas "
            "e detecta padrões de aliciamento, enviando um alerta imediato para o seu celular. "
            "mude para: O Guardian-AI detecta padrões de aliciamento no WhatsApp, enviando alerta "
            "imediato no celular do responsável. Feita essa alteração lembre-se sempre em não citar "
            "nas campanhas que o Guardian-AI monitora conversas privadas. "
            "No card golpísta altere para Sei quem vc é! Manda o PIX agora ou posto no grupo da escola!"
        )
        plan = classify_improvement(fb)
        self.assertTrue(plan.get("surgical_copy"))
        self.assertFalse(plan.get("narrative"))
        self.assertEqual(plan.get("primary_category"), "copy")
        self.assertEqual(plan.get("narrative_override"), {})

    def test_explicit_escola_still_overrides(self):
        plan = classify_improvement("Quero estória de escola com diretor alertando pais")
        self.assertTrue(plan.get("narrative"))
        self.assertEqual(plan.get("narrative_override", {}).get("publico_slug"), "escolas")


if __name__ == "__main__":
    unittest.main()
