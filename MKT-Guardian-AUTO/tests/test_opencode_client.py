"""Testes do roteamento OpenCode/DeepSeek com fallback Gemini."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opencode_client import (
    AIResponse,
    HybridAIClient,
    OpenCodeClient,
    OpenCodeClientError,
)


class _FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _FakeGeminiModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text='{"overall_score": 9}')


class _FakeGeminiClient:
    def __init__(self):
        self.models = _FakeGeminiModels()


class _DisabledOpenCode:
    enabled = False


class _FailingOpenCode:
    enabled = True

    def complete(self, *_args, **_kwargs):
        raise OpenCodeClientError("indisponível")


class TestOpenCodeClient(unittest.TestCase):
    def test_envia_texto_e_imagem_em_formato_compatível(self):
        client = OpenCodeClient.__new__(OpenCodeClient)
        client.api_key = "secret"
        client.base_url = "https://opencode.example/v1/chat/completions"
        client.model = "deepseek-v4-flash-vision-exp"
        client.session_id = "test-session"
        client.timeout = 30

        with patch(
            "opencode_client.requests.post",
            return_value=_FakeHTTPResponse(
                {"choices": [{"message": {"content": '{"ok": true}'}}]}
            ),
        ) as post:
            result = client.complete(
                "Avalie a imagem.",
                images=[(b"image-bytes", "image/jpeg")],
            )

        self.assertEqual(result.provider, "opencode")
        self.assertEqual(result.text, '{"ok": true}')
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "deepseek-v4-flash-vision-exp")
        self.assertEqual(post.call_args.kwargs["headers"]["x-opencode-session"], "test-session")
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertTrue(
            payload["messages"][0]["content"][1]["image_url"]["url"].startswith(
                "data:image/jpeg;base64,"
            )
        )

    def test_fallback_gemini_quando_opencode_falha(self):
        gemini = _FakeGeminiClient()
        router = HybridAIClient(
            gemini,
            gemini_text_model="gemini-3.1-flash-lite",
            gemini_vision_model="gemini-3.6-flash",
            opencode_client=_FailingOpenCode(),
        )

        result = router.generate_vision("Avalie.", [(b"image", "image/jpeg")])

        self.assertEqual(result, AIResponse(
            text='{"overall_score": 9}',
            provider="gemini",
            model="gemini-3.6-flash",
        ))
        self.assertEqual(gemini.models.calls[0]["model"], "gemini-3.6-flash")

    def test_fallback_gemini_quando_opencode_nao_configurado(self):
        gemini = _FakeGeminiClient()
        router = HybridAIClient(
            gemini,
            gemini_text_model="gemini-3.1-flash-lite",
            gemini_vision_model="gemini-3.6-flash",
            opencode_client=_DisabledOpenCode(),
        )

        result = router.generate_text("Crie um JSON.", fallback_config=None)

        self.assertEqual(result.provider, "gemini")
        self.assertEqual(gemini.models.calls[0]["model"], "gemini-3.1-flash-lite")


if __name__ == "__main__":
    unittest.main()
