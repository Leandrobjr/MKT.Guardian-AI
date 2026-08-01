"""Testes — creative_brief.py (HeadlineRotator + Jaccard)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_history import CampaignHistory
from creative_brief import HeadlineRotator, jaccard_similarity


class TestCreativeBrief(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.history = CampaignHistory(self.tmp)
        self.rotator = HeadlineRotator(self.tmp, self.history)

    def test_jaccard_identical(self):
        self.assertEqual(jaccard_similarity("GOLPE NO WHATSAPP PRIVADO", "golpe no whatsapp privado"), 1.0)

    def test_jaccard_different(self):
        score = jaccard_similarity("GOLPE NO WHATSAPP", "ESCOLA ALERTA PAIS")
        self.assertLess(score, 0.3)

    def test_pick_gancho_excludes_used(self):
        ctx = {
            "ganchos": [
                "HEADLINE A NO WHATSAPP",
                "HEADLINE B NO PRIVADO",
                "HEADLINE C URGENTE",
            ]
        }
        cfg = {"publico_slug": "pais", "golpe_id": "grooming"}
        self.history.registrar_campanha(
            {"gancho_atencao_inicial": "HEADLINE A NO WHATSAPP", "desenvolvimento_copy": "x",
             "direcao_arte_emocional": "cena", "texto_card_notificacao": "oi"},
            cfg,
            {"basename": "t1"},
        )
        gancho, idx = self.rotator.pick_gancho(ctx, cfg, advance=True)
        self.assertNotEqual(gancho, "HEADLINE A NO WHATSAPP")
        self.assertIn(gancho, ctx["ganchos"])

    def test_apply_diversity_replaces_similar(self):
        cfg = {"publico_slug": "pais", "golpe_id": "grooming"}
        self.history.registrar_campanha(
            {
                "gancho_atencao_inicial": "GOLPE NO WHATSAPP PRIVADO DO FILHO",
                "desenvolvimento_copy": "x",
                "direcao_arte_emocional": "cena",
                "texto_card_notificacao": "oi",
            },
            cfg,
            {"basename": "t1"},
        )
        ctx = {
            "ganchos": [
                "GOLPE NO WHATSAPP PRIVADO DO FILHO",
                "ESTRANHO MANDOU LINK NO CHAT SECRETO",
                "PREDADOR PEDIU FOTO NO PRIVADO",
            ]
        }
        creative = {"gancho_atencao_inicial": "GOLPE NO WHATSAPP PRIVADO DO SEU FILHO AGORA"}
        result = self.rotator.apply_headline_diversity(creative, ctx, cfg)
        self.assertNotEqual(
            result["gancho_atencao_inicial"],
            "GOLPE NO WHATSAPP PRIVADO DO SEU FILHO AGORA",
        )
        self.assertTrue(result.get("headline_escolhida"))


if __name__ == "__main__":
    unittest.main()
