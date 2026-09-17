"""Regressões do roteamento híbrido de narração."""

from __future__ import annotations

import base64
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid_tts import (
    ElevenLabsProvider,
    GoogleChirpProvider,
    HybridTTSRouter,
    TTSOutcome,
)
from mkt_agent_01 import MediaFactory


class FakeResponse:
    def __init__(self, status_code=200, content=b"", body=None):
        self.status_code = status_code
        self.content = content
        self._body = body or {}
        self.text = str(self._body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def make_router(session, *, mode="auto", fallback=True):
    return HybridTTSRouter(
        GoogleChirpProvider("google-key", session=session),
        ElevenLabsProvider("eleven-key", "voice-id", session=session),
        mode=mode,
        fallback_enabled=fallback,
    )


class TestHybridTTS(unittest.TestCase):
    def test_auto_prioriza_chirp_em_meta(self):
        router = make_router(FakeSession([]))

        self.assertEqual(
            router.provider_order({"preset_id": "meta_reels"}),
            ("chirp", "elevenlabs"),
        )

    def test_auto_prioriza_elevenlabs_em_shorts(self):
        router = make_router(FakeSession([]))

        self.assertEqual(
            router.provider_order({"preset_id": "shorts_urgente"}),
            ("elevenlabs", "chirp"),
        )

    def test_modo_fixo_sem_fallback_usa_apenas_provedor_escolhido(self):
        router = make_router(FakeSession([]), mode="chirp", fallback=False)

        self.assertEqual(router.provider_order({}), ("chirp",))

    def test_chirp_nao_envia_chave_na_url_nem_controle_incompativel(self):
        audio = b"a" * 1500
        session = FakeSession(
            [
                FakeResponse(
                    body={"audioContent": base64.b64encode(audio).decode("ascii")}
                )
            ]
        )
        provider = GoogleChirpProvider(
            "segredo-google",
            "pt-BR-Chirp3-HD-Aoede",
            session=session,
        )
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "voz.mp3")
            provider.synthesize("Proteja seu WhatsApp.", output, {})

            self.assertTrue(os.path.isfile(output))
            url, kwargs = session.calls[0]
            self.assertNotIn("segredo-google", url)
            self.assertEqual(kwargs["headers"]["X-Goog-Api-Key"], "segredo-google")
            self.assertNotIn("speakingRate", kwargs["json"]["audioConfig"])

    def test_fallback_para_elevenlabs_quando_chirp_falha(self):
        session = FakeSession(
            [
                FakeResponse(401, body={"error": {"message": "invalid key"}}),
                FakeResponse(200, content=b"m" * 1500),
            ]
        )
        router = make_router(session)
        with tempfile.TemporaryDirectory() as directory:
            outcome = router.synthesize(
                "Alerta Guardian AI.",
                os.path.join(directory, "voz.mp3"),
                {"preset_id": "meta_reels"},
            )

            self.assertEqual(outcome.provider, "elevenlabs")
            self.assertEqual(len(session.calls), 2)
            self.assertIn("Chirp", outcome.errors[0])

    def test_limite_de_caracteres_bloqueia_chamada_e_custo(self):
        session = FakeSession([])
        router = HybridTTSRouter(
            GoogleChirpProvider("google-key", session=session),
            ElevenLabsProvider("eleven-key", "voice-id", session=session),
            max_chars=10,
        )

        outcome = router.synthesize("texto acima do limite", "voz.mp3", {})

        self.assertFalse(outcome.provider)
        self.assertEqual(session.calls, [])
        self.assertIn("limite seguro", outcome.errors[0])

    def test_fabrica_registra_provedor_que_gerou_a_narracao(self):
        class StubRouter:
            @staticmethod
            def provider_order(_preset):
                return ("chirp", "elevenlabs")

            @staticmethod
            def synthesize(_text, output_path, _preset):
                with open(output_path, "wb") as file:
                    file.write(b"a" * 1500)
                return TTSOutcome(output_path, "chirp")

        with tempfile.TemporaryDirectory() as directory:
            factory = MediaFactory.__new__(MediaFactory)
            factory.work_dir = directory
            factory.preset_midia = {"preset_id": "meta_reels"}
            factory.tts_router = StubRouter()
            factory._audio_ok = lambda _path: True
            factory._get_audio_duration = lambda _path: 5.0

            output = factory._generate_audio(
                "Proteja seu WhatsApp.",
                os.path.join(directory, "voz.mp3"),
                factory.preset_midia,
            )

            self.assertTrue(os.path.isfile(output))
            self.assertEqual(factory.last_tts_provider, "chirp")


if __name__ == "__main__":
    unittest.main()
