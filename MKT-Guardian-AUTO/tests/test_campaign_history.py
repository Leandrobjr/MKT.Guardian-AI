"""Testes — campaign_history.py"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_history import CampaignHistory, headline_hash, visual_hash


class TestCampaignHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.hist = CampaignHistory(self.tmp)

    def test_headline_hash_normaliza_espacos_e_case(self):
        a = headline_hash("  Olá   MUNDO  ")
        b = headline_hash("olá mundo")
        self.assertEqual(a, b)

    def test_visual_hash_muda_com_persona(self):
        a = visual_hash("cena sala tv limpa", "ana_prof")
        b = visual_hash("cena sala tv limpa", "bruno_pai")
        self.assertNotEqual(a, b)

    def test_get_recent_filtra_combo(self):
        creative = {
            "gancho_atencao_inicial": "HEADLINE A",
            "desenvolvimento_copy": "copy a" * 20,
            "direcao_arte_emocional": "sala tv",
            "texto_card_notificacao": "pix urgente",
        }
        cfg_pais = {"publico_slug": "pais", "golpe_id": "grooming", "canal": "Meta", "midia": "video"}
        cfg_idosos = {"publico_slug": "idosos", "golpe_id": "falso_parente", "canal": "Meta", "midia": "video"}
        assets = {"basename": "t1_pais_video_2026", "commercial_video_file": "/x/a.mp4"}

        self.hist.registrar_campanha(creative, cfg_pais, assets, status="gerado")
        self.hist.registrar_campanha(
            {**creative, "gancho_atencao_inicial": "HEADLINE B"},
            cfg_idosos,
            {**assets, "basename": "t2_idosos_video_2026"},
            status="gerado",
        )

        pais = self.hist.get_recent("pais", "grooming", limit=10)
        self.assertEqual(len(pais), 1)
        self.assertEqual(pais[0]["headline"], "HEADLINE A")

    def test_is_headline_used(self):
        creative = {
            "gancho_atencao_inicial": "GOLPE NO WHATSAPP AGORA",
            "desenvolvimento_copy": "texto",
            "direcao_arte_emocional": "cozinha",
            "texto_card_notificacao": "oi",
        }
        cfg = {"publico_slug": "massa", "golpe_id": "pix_fantasma", "canal": "Meta", "midia": "imagem"}
        assets = {"basename": "x", "static_image_file": "/x.jpg"}
        self.hist.registrar_campanha(creative, cfg, assets)

        self.assertTrue(
            self.hist.is_headline_used("golpe no whatsapp agora", "massa", "pix_fantasma")
        )
        self.assertFalse(
            self.hist.is_headline_used("OUTRA MANCHETE NOVA", "massa", "pix_fantasma")
        )

    def test_format_anti_repeticao_contem_headlines(self):
        creative = {
            "gancho_atencao_inicial": "MANCHETE TESTE XYZ",
            "desenvolvimento_copy": "hook do roteiro aqui",
            "direcao_arte_emocional": "varanda apartamento",
            "texto_card_notificacao": "mande pix",
        }
        cfg = {"publico_slug": "pais", "golpe_id": "grooming", "canal": "Meta", "midia": "video"}
        assets = {"basename": "b1", "commercial_video_file": "/b.mp4"}
        self.hist.registrar_campanha(creative, cfg, assets, status="aprovado")

        txt = self.hist.format_anti_repeticao("pais", "grooming")
        self.assertIn("ANTI-REPETIÇÃO", txt)
        self.assertIn("MANCHETE TESTE XYZ", txt)
        self.assertIn("NÃO REPETIR", txt)


if __name__ == "__main__":
    unittest.main()
