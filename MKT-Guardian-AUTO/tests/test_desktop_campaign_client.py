"""Testes locais do cliente Desktop sem credenciais ou rede."""

import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from desktop_campaign_client import DesktopCampaignClient, DesktopCampaignClientError


class FakeQuery:
    def __init__(self, data):
        self.data = data
        self.inserted = None

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args):
        return self

    def insert(self, payload):
        self.inserted = payload
        return self

    def execute(self):
        return SimpleNamespace(data=self.data if self.inserted is None else [self.inserted])


class FakeStorageBucket:
    def create_signed_url(self, _path, _expires):
        return {"signedURL": "https://signed.example/asset?token=temp"}


class FakeStorage:
    def from_(self, _bucket):
        return FakeStorageBucket()


class FakeAuth:
    def get_user(self):
        return SimpleNamespace(
            user=SimpleNamespace(id="11111111-1111-1111-1111-111111111111")
        )


class FakeClient:
    def __init__(self):
        self.auth = FakeAuth()
        self.storage = FakeStorage()
        self.tables = {
            "mkt_campaigns": FakeQuery(
                [
                    {
                        "campaign_id": "camp_desktop",
                        "status": "APROVADA",
                        "canal": "Meta Instagram",
                        "storage_bucket": "mkt-campaign-assets",
                        "storage_path": "camp_desktop/v1/video.mp4",
                    }
                ]
            ),
            "mkt_campaign_commands": FakeQuery([]),
        }

    def table(self, name):
        return self.tables[name]


class TestDesktopCampaignClient(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.desktop = DesktopCampaignClient(client=self.client)

    def test_exige_confirmacao_explicita(self):
        with self.assertRaises(DesktopCampaignClientError):
            self.desktop.request_publication("camp_desktop")

    def test_cria_comando_com_usuario_da_sessao(self):
        result = self.desktop.request_publication(
            "camp_desktop",
            confirmed=True,
        )

        self.assertEqual(result["campaign_id"], "camp_desktop")
        self.assertEqual(
            result["requested_by"],
            "11111111-1111-1111-1111-111111111111",
        )
        self.assertEqual(result["action"], "PUBLISH")
        self.assertTrue(result["payload"]["confirmed"])

    def test_cria_decisao_editorial_de_aprovacao(self):
        self.client.tables["mkt_campaigns"].data[0]["status"] = (
            "AGUARDANDO_APROVACAO_FINAL"
        )

        result = self.desktop.request_editorial_decision(
            "camp_desktop",
            "approve",
            confirmed=True,
        )

        self.assertEqual(result["action"], "APPROVE")
        self.assertEqual(result["payload"]["version"], 0)

    def test_exige_motivo_para_solicitar_ajuste(self):
        self.client.tables["mkt_campaigns"].data[0]["status"] = (
            "AGUARDANDO_APROVACAO_FINAL"
        )

        with self.assertRaisesRegex(DesktopCampaignClientError, "motivo"):
            self.desktop.request_editorial_decision(
                "camp_desktop",
                "request_revision",
                confirmed=True,
            )

    def test_gera_url_temporaria_do_asset(self):
        url = self.desktop.create_asset_url("camp_desktop")

        self.assertTrue(url.startswith("https://signed.example/"))

    def test_bloqueia_tiktok_automatico(self):
        self.client.tables["mkt_campaigns"] = FakeQuery(
            [
                {
                    "campaign_id": "camp_tiktok",
                    "status": "APROVADA",
                    "canal": "TikTok",
                }
            ]
        )

        with self.assertRaisesRegex(DesktopCampaignClientError, "manual"):
            self.desktop.request_publication("camp_tiktok", confirmed=True)


if __name__ == "__main__":
    unittest.main()
