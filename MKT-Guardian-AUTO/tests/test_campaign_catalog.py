"""Testes do catálogo oficial de campanhas."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_catalog import CampaignCatalog


class TestCampaignCatalog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.catalog = CampaignCatalog(self.tmp)
        self.config = {
            "publico_slug": "pais",
            "golpe_id": "falso_parente",
            "canal": "Meta Ads",
            "midia": "Vídeo Vertical Animado",
            "preset_midia": {
                "preset_id": "meta_reels",
                "width": 1080,
                "height": 1920,
                "aspect_ratio": "9:16",
                "composition_template": {"template_id": "guardian_meta_reels_v1"},
            },
        }
        self.creative = {
            "gancho_atencao_inicial": "ALERTA NO WHATSAPP",
            "desenvolvimento_copy": "Não clique no link suspeito.",
            "legenda": "Alerta para sua família.",
        }

    def test_cria_e_mantem_historico_de_versoes(self):
        campaign_id = self.catalog.create(self.config)
        self.catalog.update(campaign_id, "PRODUZIDA", self.config, self.creative)
        approved = self.catalog.update(
            campaign_id, "APROVADA", self.config, self.creative, actor="human"
        )

        current = self.catalog.get(campaign_id)
        self.assertEqual(current["status"], "APROVADA")
        self.assertEqual(current["campaign_id"], campaign_id)
        self.assertEqual(current["legenda"], "Alerta para sua família.")
        self.assertEqual(current["preset"]["template_id"], "guardian_meta_reels_v1")
        self.assertEqual(current["data_aprovacao"], approved["data_aprovacao"])
        self.assertGreaterEqual(len(self.catalog.versions(campaign_id)), 3)
        self.assertTrue(self.catalog.can_publish(campaign_id))

    def test_bloqueia_publicacao_duplicada(self):
        campaign_id = self.catalog.create(self.config)
        self.catalog.update(campaign_id, "APROVADA", self.config, self.creative)
        self.catalog.update(campaign_id, "PUBLICANDO", self.config, self.creative)
        self.catalog.update(
            campaign_id,
            "PUBLICADA",
            self.config,
            self.creative,
            platform="Instagram",
            returned_id="media-123",
        )

        with self.assertRaises(ValueError):
            self.catalog.update(campaign_id, "PUBLICANDO", self.config, self.creative)

        self.assertFalse(self.catalog.can_publish(campaign_id))
        self.assertEqual(self.catalog.get(campaign_id)["id_retornado"], "media-123")

    def test_status_invalido_e_rejeitado(self):
        campaign_id = self.catalog.create(self.config)
        with self.assertRaises(ValueError):
            self.catalog.update(campaign_id, "INVALIDO", self.config)
        rejected = self.catalog.update(
            campaign_id,
            "REJEITADA",
            self.config,
            self.creative,
            error_message="rejeitada pelo responsável",
        )
        self.assertEqual(rejected["status"], "REJEITADA")
        self.assertEqual(rejected["mensagem_erro"], "rejeitada pelo responsável")


if __name__ == "__main__":
    unittest.main()
