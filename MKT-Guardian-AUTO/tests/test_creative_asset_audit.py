"""Testes da QA automática dos criativos finais."""

import os
import shutil
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from creative_asset_audit import audit_creative_assets
from visual_quality_audit import QualityFinding, VisualQualityResult


class _FailedVisualAuditor:
    def audit(self, creative_data, config, assets):
        return VisualQualityResult(
            enabled=True,
            skipped=False,
            provider="fake",
            model="fake",
            overall_score=5.0,
            passed=False,
            findings=[
                QualityFinding(
                    "texto", 4.0, False, "Texto cortado.", "layout"
                )
            ],
        )


class TestCreativeAssetAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.image = os.path.join(self.tmp, "campanha.jpg")
        Image.new("RGB", (1080, 1080), "white").save(self.image)
        self.config = {
            "publico_slug": "pais",
            "golpe_id": "falso_parente",
            "midia": "Imagem Estática Square (1080x1080)",
        }
        self.creative = {
            "gancho_atencao_inicial": "PIX URGENTE DO FILHO?",
            "desenvolvimento_copy": "Seu filho recebeu uma mensagem urgente no WhatsApp.",
            "texto_card_notificacao": "Deposite agora para iniciar a cirurgia.",
            "texto_botao_conversao": "TESTE GRÁTIS — PROTEJA SEU WHATSAPP AGORA!",
            "preset_midia": {"width": 1080, "height": 1080},
        }

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_aprova_imagem_completa(self):
        result = audit_creative_assets(
            self.creative,
            self.config,
            {"basename": "campanha", "static_image_file": self.image},
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.metrics["image_dimensions"], {"width": 1080, "height": 1080})

    def test_bloqueia_cta_incoerente_e_gramaticalmente_invalido(self):
        creative = {
            **self.creative,
            "texto_botao_conversao": "PROTEJA O WHATSAPP DOS SUA FILHA",
        }

        result = audit_creative_assets(
            creative,
            self.config,
            {"basename": "campanha", "static_image_file": self.image},
        )

        codes = {issue.code for issue in result.blocking}
        self.assertFalse(result.ok)
        self.assertIn("cta_gramatica", codes)
        self.assertIn("cta_publico_incoerente", codes)

    def test_bloqueia_video_sem_audio_e_arquivo_principal(self):
        config = {**self.config, "midia": "Vídeo Vertical Animado"}

        result = audit_creative_assets(
            self.creative,
            config,
            {"basename": "campanha"},
        )

        codes = {issue.code for issue in result.blocking}
        self.assertIn("asset_ausente", codes)
        self.assertIn("audio_ausente", codes)

    def test_qa_multimodal_reprova_e_indica_layout(self):
        result = audit_creative_assets(
            self.creative,
            self.config,
            {"basename": "campanha", "static_image_file": self.image},
            visual_auditor=_FailedVisualAuditor(),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.recommended_stage, "layout")
        self.assertIn("qa_visual_abaixo_minimo", {issue.code for issue in result.blocking})


if __name__ == "__main__":
    unittest.main()
