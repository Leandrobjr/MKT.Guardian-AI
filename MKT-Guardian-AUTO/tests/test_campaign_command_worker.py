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
        self.recovered = []

    def list_pending_commands(self, _limit):
        return self.commands

    def claim_pending_commands(self, _limit):
        self.claimed += 1
        return [{**command, "status": "CLAIMED"} for command in self.commands]

    def recover_stale_commands(self, **kwargs):
        self.recovered.append(kwargs)
        return []

    def get_campaign(self, _campaign_id):
        return self.campaign

    def validate_local_asset(self, asset_path):
        if not os.path.isfile(asset_path):
            raise RuntimeError("asset ausente")
        return os.path.realpath(asset_path)

    def update_campaign_publication(self, campaign_id, status, **kwargs):
        self.updates.append((campaign_id, status, kwargs))

    def update_campaign_editorial(self, campaign_id, status, **kwargs):
        self.updates.append((campaign_id, status, kwargs))
        self.campaign = {**self.campaign, "status": status}

    def complete_command(self, command_id, **kwargs):
        self.completed.append((command_id, kwargs))


class FakePublisher:
    def postar_asset(self, _asset_path, _caption, *, qa_evidence=None):
        assert qa_evidence and qa_evidence.get("multimodal_passed") is True
        return {"ok": True, "post_id": "media-123"}


class FakeRevisionService:
    def __init__(self, _base_dir, *, catalog, bridge):
        self.catalog = catalog
        self.bridge = bridge

    def apply(self, campaign, current, feedback):
        assert campaign["campaign_id"] == "camp_worker"
        assert current["campaign_id"] == "camp_worker"
        assert feedback == "Corrigir o enquadramento."
        return {
            "status": "AGUARDANDO_APROVACAO_FINAL",
            "campaign_id": "camp_worker",
            "version": 2,
            "provider": "gemini",
            "qa_score": 9,
        }


class OneCycleEvent:
    def __init__(self):
        self.wait_calls = 0

    def is_set(self):
        return self.wait_calls > 0

    def wait(self, _timeout):
        self.wait_calls += 1


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
            {
                "commercial_video_file": self.asset,
                "qa_evidence": {
                    "multimodal_available": True,
                    "multimodal_passed": True,
                    "overall_score": 9,
                    "model": "fake",
                },
            },
            actor="human",
        )
        self.remote = {
            "campaign_id": "camp_worker",
            "status": "APROVADA",
            "aprovado_por": "11111111-1111-1111-1111-111111111111",
            "canal": "Meta Instagram",
            "legenda": "Alerta.",
            "metadata": {
                "qa": {
                    "multimodal_available": True,
                    "multimodal_passed": True,
                    "overall_score": 9,
                    "model": "fake",
                }
            },
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
            revision_service_factory=FakeRevisionService,
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
            revision_service_factory=FakeRevisionService,
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

    def test_bloqueia_publicacao_sem_qa_multimodal(self):
        self.bridge.campaign = {**self.remote, "metadata": {}}
        worker = CampaignCommandWorker(
            self.tmp,
            bridge=self.bridge,
            catalog=self.catalog,
            publisher_factory=FakePublisher,
        )

        result = worker.run_once(dry_run=False)

        self.assertFalse(result[0]["ok"])
        self.assertIn("QA multimodal", result[0]["error"])
        self.assertEqual(self.bridge.claimed, 1)

    def test_bloqueia_publicacao_sem_aprovacao_humana(self):
        self.bridge.campaign = {
            **self.remote,
            "status": "PRONTA_PARA_PUBLICAR",
        }
        worker = CampaignCommandWorker(
            self.tmp,
            bridge=self.bridge,
            catalog=self.catalog,
            publisher_factory=FakePublisher,
        )

        result = worker.run_once(dry_run=False)

        self.assertFalse(result[0]["ok"])
        self.assertIn("Status remoto", result[0]["error"])

    def test_processa_aprovacao_editorial(self):
        self.bridge.campaign = {
            **self.remote,
            "status": "AGUARDANDO_APROVACAO_FINAL",
        }
        self.bridge.commands = [
            {
                "id": "cmd-approval",
                "campaign_id": "camp_worker",
                "action": "APPROVE",
                "requested_by": "11111111-1111-1111-1111-111111111111",
                "payload": {"confirmed": True, "version": 1},
            }
        ]
        worker = CampaignCommandWorker(
            self.tmp,
            bridge=self.bridge,
            catalog=self.catalog,
            publisher_factory=FakePublisher,
        )

        result = worker.run_once(dry_run=False)

        self.assertTrue(result[0]["ok"])
        self.assertEqual(self.bridge.campaign["status"], "APROVADA")
        self.assertTrue(self.bridge.completed[0][1]["success"])

    def test_solicita_ajuste_editorial_com_motivo(self):
        self.bridge.campaign = {
            **self.remote,
            "status": "AGUARDANDO_APROVACAO_FINAL",
        }
        self.bridge.commands = [
            {
                "id": "cmd-revision",
                "campaign_id": "camp_worker",
                "action": "REQUEST_REVISION",
                "requested_by": "11111111-1111-1111-1111-111111111111",
                "payload": {"confirmed": True, "feedback": "Corrigir o enquadramento."},
            }
        ]
        worker = CampaignCommandWorker(
            self.tmp,
            bridge=self.bridge,
            catalog=self.catalog,
            revision_service_factory=FakeRevisionService,
            publisher_factory=FakePublisher,
        )

        result = worker.run_once(dry_run=False)

        self.assertTrue(result[0]["ok"])
        self.assertEqual(
            self.bridge.completed[0][1]["result"]["status"],
            "AGUARDANDO_APROVACAO_FINAL",
        )

    def test_worker_continuo_recupera_e_consulta_a_fila(self):
        event = OneCycleEvent()
        worker = CampaignCommandWorker(
            self.tmp,
            bridge=self.bridge,
            catalog=self.catalog,
            publisher_factory=FakePublisher,
        )

        worker.run_forever(
            limit=3,
            poll_seconds=0,
            claim_timeout_seconds=60,
            stop_event=event,
        )

        self.assertEqual(len(self.bridge.recovered), 1)
        self.assertEqual(self.bridge.recovered[0]["stale_after_seconds"], 60)
        self.assertEqual(self.bridge.claimed, 1)


if __name__ == "__main__":
    unittest.main()
