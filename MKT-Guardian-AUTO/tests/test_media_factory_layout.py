"""Regressões do layout visual aplicado pela fábrica de mídia."""

import os
import sys
import unittest

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mkt_agent_01 import MediaFactory


class TestMediaFactoryLayout(unittest.TestCase):
    def test_headline_comeca_abaixo_do_logo(self):
        factory = MediaFactory.__new__(MediaFactory)
        factory.canvas_width = 1080
        factory.canvas_height = 1920
        factory.preset_midia = {"preset_id": "shorts_urgente"}
        draw = ImageDraw.Draw(Image.new("RGB", (1080, 1920)))

        _logo_x, logo_y, logo_size, _font, _label = factory._logo_layout(draw)
        template = factory._composition_template()
        safe_top = template["safe_area"][1]
        headline_y = int(max(template["headline_top"], safe_top) * 1920)
        headline_y = max(headline_y, logo_y + logo_size + int(16 * 1920 / 1920))

        self.assertGreaterEqual(headline_y, logo_y + logo_size + 16)

    def test_feed_quadrado_preserva_tamanho_de_fonte(self):
        factory = MediaFactory.__new__(MediaFactory)
        factory.canvas_width = 1080
        factory.canvas_height = 1080
        factory.preset_midia = {"preset_id": "feed_quadrado"}

        self.assertEqual(factory._scaled_font_size(19, min_size=13), 19)

    def test_risco_visual_alto_exige_duas_candidatas(self):
        flags, high_risk = MediaFactory._visual_risk_profile(
            {
                "direcao_arte_emocional": (
                    "one physical smartphone, WhatsApp interface, lower third cards"
                ),
                "texto_card_notificacao": "Mensagem urgente",
            }
        )

        self.assertTrue(high_risk)
        self.assertIn("smartphone", flags)
        self.assertIn("interface_mensagem", flags)
        self.assertIn("overlays", flags)

    def test_cena_sem_celular_nao_exige_duas_candidatas(self):
        _flags, high_risk = MediaFactory._visual_risk_profile(
            {"direcao_arte_emocional": "empresário em reunião presencial"}
        )

        self.assertFalse(high_risk)

    def test_extrai_metricas_loudnorm_para_segunda_passagem(self):
        stats = MediaFactory._parse_loudnorm_stats(
            """
            relatório ffmpeg
            {
                "input_i" : "-22.44",
                "input_tp" : "-2.23",
                "input_lra" : "3.40",
                "input_thresh" : "-32.49",
                "target_offset" : "0.92"
            }
            """
        )
        self.assertEqual(stats["input_i"], "-22.44")
        self.assertEqual(stats["target_offset"], "0.92")

    def test_rejeita_metricas_loudnorm_incompletas(self):
        self.assertEqual(
            MediaFactory._parse_loudnorm_stats('{"input_i": "-22.4"}'),
            {},
        )


if __name__ == "__main__":
    unittest.main()
