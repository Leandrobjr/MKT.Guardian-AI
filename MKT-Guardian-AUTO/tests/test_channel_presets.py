"""Testes — validação de canal, mídia e metadados técnicos."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_presets import validate_channel_media


class TestChannelPresets(unittest.TestCase):
    def test_imagem_quadrada_meta_e_valida(self):
        result = validate_channel_media(
            "Meta Ads (Instagram/Facebook)",
            "Imagem Estática Square (1080x1080)",
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.preset["preset_id"], "feed_quadrado")
        self.assertEqual(result.metadata["resolucao"], "1080x1080")
        self.assertEqual(result.metadata["proporcao"], "1:1")
        self.assertEqual(result.metadata["template_id"], "guardian_feed_quadrado_v1")
        self.assertEqual(result.metadata["posicao_logo"], "top_left")
        self.assertEqual(len(result.preset["composition_template"]["card_regions"]), 3)

    def test_video_vertical_shorts_e_valido(self):
        result = validate_channel_media(
            "TikTok / YouTube Shorts",
            "Vídeo Vertical Animado",
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.preset["preset_id"], "shorts_urgente")
        self.assertEqual(result.metadata["proporcao"], "9:16")
        self.assertEqual(
            result.preset["composition_template"]["animation"],
            "zoom_sutil_e_ritmo_urgente",
        )

    def test_imagem_no_tiktok_e_bloqueada(self):
        result = validate_channel_media(
            "TikTok / YouTube Shorts",
            "Imagem Estática Square (1080x1080)",
        )

        self.assertFalse(result.valid)
        self.assertTrue(any("Imagem estática" in error for error in result.errors))

    def test_video_em_canal_desconhecido_e_bloqueado(self):
        result = validate_channel_media(
            "Pinterest",
            "Vídeo Vertical Animado",
        )

        self.assertFalse(result.valid)
        self.assertTrue(result.errors)


if __name__ == "__main__":
    unittest.main()
