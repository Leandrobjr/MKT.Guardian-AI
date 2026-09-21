"""Testes locais do preflight e das validações Meta."""

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_publisher import MetaPublisher


class TestMetaPublisher(unittest.TestCase):
    def _publisher(self) -> MetaPublisher:
        publisher = MetaPublisher.__new__(MetaPublisher)
        publisher.token = "token-de-teste"
        publisher.ig_user = "ig-user"
        publisher.imgbb_key = ""
        return publisher

    @staticmethod
    def _response(payload: dict, ok: bool = True) -> Mock:
        response = Mock()
        response.ok = ok
        response.status_code = 200 if ok else 403
        response.text = ""
        response.json.return_value = payload
        return response

    def test_preflight_exige_token_permissoes_e_conta_profissional(self):
        publisher = self._publisher()
        token = self._response(
            {
                "data": {
                    "is_valid": True,
                    "expires_at": 4_000_000_000,
                    "scopes": ["instagram_basic", "instagram_content_publish"],
                }
            }
        )
        account = self._response(
            {"id": "ig-user", "username": "guardian", "account_type": "BUSINESS"}
        )
        with patch("meta_publisher.requests.get", side_effect=[token, account]):
            result = publisher.preflight()
        self.assertTrue(result["ok"])

    def test_preflight_falha_fechado_em_erro_de_rede(self):
        publisher = self._publisher()
        with patch("meta_publisher.requests.get", side_effect=OSError("offline")):
            result = publisher.preflight()
        self.assertFalse(result["ok"])
        self.assertIn("validar o token", result["erro"])

    def test_asset_invalido_e_bloqueado_antes_da_api(self):
        publisher = self._publisher()
        publisher.preflight = Mock(return_value={"ok": True})
        with tempfile.NamedTemporaryFile(suffix=".txt") as file:
            result = publisher.postar_asset(file.name, "legenda")
        self.assertFalse(result["ok"])
        self.assertIn("Extensão", result["erro"])
        publisher.preflight.assert_not_called()

    def test_publicacao_valida_exige_qa_multimodal(self):
        publisher = self._publisher()
        publisher.preflight = Mock(return_value={"ok": True})
        with tempfile.NamedTemporaryFile(suffix=".mp4") as file:
            result = publisher.postar_asset(file.name, "legenda")
        self.assertFalse(result["ok"])
        self.assertIn("QA multimodal", result["erro"])
        publisher.preflight.assert_not_called()


if __name__ == "__main__":
    unittest.main()
