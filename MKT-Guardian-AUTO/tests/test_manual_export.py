"""Testes da exportação local para upload manual no TikTok."""

import os
import shutil
import tempfile
import unittest

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from manual_export import export_tiktok_package


class TestManualExport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        output = os.path.join(self.tmp, "output_campanha")
        os.makedirs(output)
        self.video = os.path.join(output, "campanha.mp4")
        self.image = os.path.join(output, "campanha.jpg")
        with open(self.video, "wb") as f:
            f.write(b"fake mp4")
        with open(self.image, "wb") as f:
            f.write(b"fake jpg")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cria_pacote_com_video_capa_legenda_e_checklist(self):
        result = export_tiktok_package(
            self.tmp,
            {
                "basename": "campanha",
                "commercial_video_file": self.video,
                "static_image_file": self.image,
            },
            {
                "gancho_atencao_inicial": "GOLPE NO WHATSAPP",
                "desenvolvimento_copy": "O Guardian AI detecta ameaças.",
                "chamada_para_acao_cta": "PROTEJA-SE",
                "link_conversao": "https://guardian-ai.app",
            },
            open_browser=False,
        )
        self.assertTrue(result["ok"])
        self.assertTrue(os.path.isfile(result["video"]))
        self.assertTrue(os.path.isfile(result["thumbnail"]))
        self.assertTrue(os.path.isfile(result["caption"]))
        self.assertTrue(os.path.isfile(result["checklist"]))
        with open(result["caption"], encoding="utf-8") as f:
            self.assertIn("GOLPE NO WHATSAPP", f.read())

    def test_falha_sem_video(self):
        result = export_tiktok_package(
            self.tmp,
            {"basename": "sem_video"},
            {},
            open_browser=False,
        )
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
