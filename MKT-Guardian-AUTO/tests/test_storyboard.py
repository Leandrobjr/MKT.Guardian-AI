"""Testes — storyboard estruturado para vídeos."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storyboard import (
    build_storyboard,
    format_storyboard_compact,
    format_storyboard_prompt,
)


class TestStoryboard(unittest.TestCase):
    def setUp(self):
        self.brief = {
            "personagem": "mãe brasileira",
            "cenario": "sala organizada",
            "mensagem_golpista": "Seu filho sofreu um acidente. Faça um PIX.",
            "emocao": "proteção familiar, urgência",
            "duracao": "12-18 segundos",
            "formato": {
                "target_narration_seconds": 18,
                "aspect_ratio": "9:16",
            },
        }

    def test_video_gera_cinco_cenas_e_respeita_duracao(self):
        storyboard = build_storyboard(
            self.brief,
            {"midia": "Vídeo Vertical Animado"},
            {},
        )

        self.assertEqual(len(storyboard), 5)
        self.assertEqual(sum(scene["duracao_segundos"] for scene in storyboard), 18)
        self.assertEqual(storyboard[1]["texto_permitido"], ["mensagem do card do golpe"])
        self.assertIn("pós-produção", format_storyboard_prompt(storyboard))

    def test_imagem_estatica_nao_cria_storyboard(self):
        storyboard = build_storyboard(
            self.brief,
            {"midia": "Imagem Estática Square (1080x1080)"},
            {},
        )

        self.assertEqual(storyboard, [])
        self.assertIn("mídia estática", format_storyboard_compact(storyboard))


if __name__ == "__main__":
    unittest.main()
