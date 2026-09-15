"""Testes do worker Linux sem chamadas Supabase ou Meta."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_catalog import CampaignCatalog
from campaign_command_worker import CampaignCommandWorker


class FakeBridge:
    def __init__(self, base_dir, campaign):
        self.base_dir = base_dir
        self.campaign = campaign
        self.commands = []
        self.completed = []
        self.updates = []
        self.claimed = 0

    def list_pending_commands(self, _limit):
        return self.commands

    def claim_pending_commands(self, _limit):
        self.claimed += 1
        return [{**command, "status": "CLAIMED"} for command in self.commands]

    def get_campaign(self, _campaign_id):
        return self.campaign

    def validate_local_asset(self, asset_path):
        if not os.path.isfile(asset_path):
            raise RuntimeError("asset ausente")
        return os.path.realpath(asset_path)

    def update_campaign_publication(self, campaign_id, status, **kwargs):
        self.updates.append((campaign_id, status, kwargs))

    def complete_command(self, command_id, **kwargs):
        self.completed.append((command_id, kwargs))


class FakePublisher:
    def postar_asset(self, _asset_path, _caption):
        return {"ok": True, "post_id": "media-123"}


class TestCampaignCommandWorker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.catalog = CampaignCatalog(self.tmp)
        self.asset = os.path.join(self.tmp, "criativo.mp4")
        with open(self.asset, "wb") as file:
            file.write(b"mp4")
        config = {
            "_campaign_id": "camp_worker",
            "publico_slug": "pais",
            "golpe_id": "falso_parente",
            "canal": "Meta Instagram",
            "midia": "Reels",
            "preset_midia": {"preset_id": "meta_reels"},
        }
        creative = {
            "gancho_atencao_inicial": "ALERTA",
            "desenvolvimento_copy": "Não clique.",
            "legenda": "Alerta.",
        }
        self.catalog.create(config)
        self.catalog.update(
            "camp_worker",
            "APROVADA",
            config,
            creative,
            {"commercial_video_file": self.asset},
        )
        self.remote = {
            "campaign_id": "camp_worker",
            "status": "APROVADA",
            "canal": "Meta Instagram",
            "legenda": "Alerta.",
        }
        self.bridge = FakeBridge(self.tmp, self.remote)
        self.bridge.commands = [
            {
                "id": "cmd-1",
                "campaign_id": "camp_worker",
                "action": "PUBLISH",
                "requested_by": "11111111-1111-1111-1111-111111111111",
            }
        ]

    def test_dry_run_nao_reivindica_nem_publica(self):
        worker = CampaignCommandWorker(
            self.tmp,
            bridge=self.bridge,
            catalog=self.catalog,
            publisher_factory=FakePublisher,
        )

        result = worker.run_once(dry_run=True)

        self.assertTrue(result[0]["ok"])
        self.assertTrue(result[0]["dry_run"])
        self.assertEqual(self.bridge.claimed, 0)
        self.assertEqual(self.bridge.completed, [])
        self.assertEqual(self.bridge.updates, [])

    def test_execucao_registra_publicacao_e_resultado(self):
        worker = CampaignCommandWorker(
            self.tmp,
            bridge=self.bridge,
            catalog=self.catalog,
            publisher_factory=FakePublisher,
        )

        result = worker.run_once(dry_run=False)

        self.assertTrue(result[0]["ok"])
        self.assertEqual(self.bridge.claimed, 1)
        self.assertEqual([item[1] for item in self.bridge.updates], ["PUBLICANDO", "PUBLICADA"])
        self.assertEqual(self.bridge.completed[0][1]["success"], True)
        self.assertEqual(self.catalog.get("camp_worker")["status"], "PUBLICADA")

    def test_bloqueia_publicacao_duplicada(self):
        self.bridge.campaign = {**self.remote, "status": "PUBLICADA"}
        worker = CampaignCommandWorker(
            self.tmp,
            bridge=self.bridge,
            catalog=self.catalog,
            publisher_factory=FakePublisher,
        )

        result = worker.run_once(dry_run=False)

        self.assertFalse(result[0]["ok"])
        self.assertIn("duplicada", result[0]["error"])
        self.assertEqual(self.bridge.completed[0][1]["success"], False)
        self.assertEqual(self.bridge.updates, [])

    def test_tiktok_continua_manual(self):
        self.bridge.campaign = {**self.remote, "canal": "TikTok"}
        worker = CampaignCommandWorker(
            self.tmp,
            bridge=self.bridge,
            catalog=self.catalog,
            publisher_factory=FakePublisher,
        )

        result = worker.run_once(dry_run=True)

        self.assertFalse(result[0]["ok"])
        self.assertIn("manual", result[0]["error"])


if __name__ == "__main__":
    unittest.main()
