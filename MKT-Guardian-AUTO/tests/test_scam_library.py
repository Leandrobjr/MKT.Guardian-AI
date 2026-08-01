"""Testes — scam_library.py (Biblioteca de golpes Fase 4)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_history import CampaignHistory
from scam_library import ScamLibrary


class TestScamLibrary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.history = CampaignHistory(self.tmp)
        repo_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.library = ScamLibrary(repo_base, self.history)

    def test_count_variants_loaded(self):
        total = self.library.count_variants()
        self.assertGreaterEqual(total, 20)

    def test_pick_variant_returns_frase(self):
        picked = self.library.pick_variant("pix_fantasma", "idosos")
        self.assertIsNotNone(picked)
        self.assertTrue(picked.get("frase_golpista"))
        self.assertEqual(picked.get("golpe_id"), "pix_fantasma")

    def test_pick_variant_new_golpes(self):
        for golpe in ("link_malicioso", "falso_emprego", "falso_investimento"):
            picked = self.library.pick_variant(golpe, "massa")
            self.assertIsNotNone(picked, golpe)
            self.assertTrue(picked.get("variant_id"))

    def test_avoids_recent_frase(self):
        cfg = {"publico_slug": "pais", "golpe_id": "grooming"}
        first = self.library.pick_variant("grooming", "pais")
        self.assertIsNotNone(first)
        self.history.registrar_campanha(
            {
                "gancho_atencao_inicial": "X",
                "desenvolvimento_copy": "y",
                "direcao_arte_emocional": "cena",
                "texto_card_notificacao": first["frase_golpista"],
            },
            cfg,
            {"basename": "t1"},
        )
        second = self.library.pick_variant("grooming", "pais")
        self.assertIsNotNone(second)
        self.assertNotEqual(
            second["frase_golpista"].strip().lower(),
            first["frase_golpista"].strip().lower(),
        )

    def test_apply_to_context(self):
        ctx = {"frase_golpista": "frase antiga", "combo_key": "massa|phishing"}
        enriched = self.library.apply_to_context(ctx, "phishing", "massa")
        self.assertIn("scam_variant_id", enriched)
        self.assertNotEqual(enriched.get("frase_golpista"), "frase antiga")


if __name__ == "__main__":
    unittest.main()
