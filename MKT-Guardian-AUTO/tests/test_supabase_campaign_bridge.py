"""Testes locais da ponte Supabase sem chamadas externas."""

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase_campaign_bridge import SupabaseBridgeError, SupabaseCampaignBridge


class FakeStorageBucket:
    def __init__(self):
        self.uploads = []

    def upload(self, path, file, options):
        self.uploads.append((path, file.read(), options))
        return {"path": path}


class FakeStorage:
    def __init__(self):
        self.bucket = FakeStorageBucket()

    def from_(self, bucket):
        self.bucket_name = bucket
        return self.bucket


class FakeTable:
    def __init__(self, name, response=None):
        self.name = name
        self.response = response or []
        self.payload = None
        self.filters = []

    def upsert(self, payload, on_conflict=None):
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def select(self, *_args):
        return self

    def eq(self, *args):
        self.filters.append(args)
        return self

    def order(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def execute(self):
        return SimpleNamespace(data=self.response)


class FakeClient:
    def __init__(self):
        self.storage = FakeStorage()
        self.tables = {}

    def table(self, name):
        self.tables.setdefault(name, FakeTable(name))
        return self.tables[name]


class TestSupabaseCampaignBridge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.client = FakeClient()
        self.bridge = SupabaseCampaignBridge(
            self.tmp,
            client=self.client,
            max_asset_bytes=1024,
        )

    def test_faz_upload_com_caminho_seguro_e_tipo_permitido(self):
        asset = os.path.join(self.tmp, "criativo.jpg")
        with open(asset, "wb") as file:
            file.write(b"jpeg")

        result = self.bridge.upload_asset("camp_abc123", asset, version=2)

        self.assertEqual(result["storage_path"], "camp_abc123/v2/criativo.jpg")
        self.assertEqual(self.client.storage.bucket_name, "mkt-campaign-assets")
        self.assertEqual(self.client.storage.bucket.uploads[0][2]["content-type"], "image/jpeg")

    def test_rejeita_asset_fora_do_projeto_e_extensao_invalida(self):
        outside = os.path.join(os.path.dirname(self.tmp), "fora.jpg")
        with open(outside, "wb") as file:
            file.write(b"jpeg")
        with self.assertRaises(SupabaseBridgeError):
            self.bridge.upload_asset("camp_abc123", outside)

        invalid = os.path.join(self.tmp, "criativo.pdf")
        with open(invalid, "wb") as file:
            file.write(b"pdf")
        with self.assertRaises(SupabaseBridgeError):
            self.bridge.upload_asset("camp_abc123", invalid)

    def test_sync_grava_metadata_sem_caminho_local_ou_token(self):
        record = {
            "campaign_id": "camp_abc123",
            "version": 1,
            "status": "APROVADA",
            "publico": "pais",
            "golpe": "falso_parente",
            "canal": "Meta",
            "midia": "Reels",
            "legenda": "Alerta",
            "roteiro": "Não clique.",
            "preset": {"preset_id": "meta_reels"},
            "headline": "GOLPE",
            "asset_path": "",
            "metadata": {"access_token": "não deve ser copiado"},
        }

        self.bridge.sync_campaign(record)

        payload = self.client.tables["mkt_campaigns"].payload
        self.assertEqual(payload["campaign_id"], "camp_abc123")
        self.assertNotIn("asset_path", payload)
        self.assertNotIn("access_token", str(payload))
        self.assertEqual(self.client.tables["mkt_campaigns"].on_conflict, "campaign_id")

    def test_resultado_de_comando_descarta_campos_sensiveis(self):
        self.bridge.complete_command(
            "cmd-1",
            success=False,
            result={
                "platform": "Instagram",
                "returned_id": "media-1",
                "access_token": "segredo",
            },
            error="Falha de rede",
        )

        payload = self.client.tables["mkt_campaign_commands"].payload
        self.assertEqual(payload["status"], "FAILED")
        self.assertNotIn("access_token", str(payload))
        self.assertEqual(payload["result"]["error"], "Falha de rede")


if __name__ == "__main__":
    unittest.main()
