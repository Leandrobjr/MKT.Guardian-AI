"""Testes da QA multimodal sem chamadas reais à API."""

import json
import os
import shutil
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from visual_quality_audit import GeminiVisualQualityAuditor


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeModels:
    def __init__(self, response: _FakeResponse):
        self.response = response
        self.calls = 0
        self.last_kwargs = {}

    def generate_content(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        return self.response


class _FakeClient:
    def __init__(self, response: _FakeResponse):
        self.models = _FakeModels(response)


def _checks(score: int = 9) -> dict:
    return {
        dimension: {"score": score, "ok": score >= 7, "reason": "Adequado."}
        for dimension in (
            "rosto", "maos", "celular", "texto", "logo", "contraste",
            "personagem", "cenario", "coerencia_publico",
            "coerencia_roteiro", "cta", "canal",
        )
    }


class TestVisualQualityAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.image = os.path.join(self.tmp, "campanha.jpg")
        Image.new("RGB", (1080, 1920), "white").save(self.image)
        self.creative = {
            "creative_brief": {
                "publico": "Pais",
                "golpe": "Falso parente",
                "personagem": "mãe brasileira",
                "cenario": "sala organizada",
            }
        }
        self.config = {
            "canal": "Meta Ads",
            "midia": "Vídeo Vertical Animado",
        }

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_aprova_resposta_multimodal_com_nota_alta(self):
        payload = {"overall_score": 9, "checks": _checks(9)}
        client = _FakeClient(_FakeResponse(json.dumps(payload)))
        auditor = GeminiVisualQualityAuditor(client)

        result = auditor.audit(
            self.creative,
            self.config,
            {"static_image_file": self.image},
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.recommended_stage, "")
        self.assertEqual(client.models.calls, 1)

    def test_prompt_reprova_celular_duplicado_ou_mockup(self):
        payload = {"overall_score": 9, "checks": _checks(9)}
        client = _FakeClient(_FakeResponse(json.dumps(payload)))
        auditor = GeminiVisualQualityAuditor(client)

        auditor.audit(
            self.creative,
            self.config,
            {"static_image_file": self.image},
        )

        prompt = client.models.last_kwargs["contents"][0]
        self.assertIn("exatamente um smartphone", prompt)
        self.assertIn("dois ou mais aparelhos", prompt)
        self.assertIn("mockup ampliado", prompt)
        self.assertIn("ok=false", prompt)
        self.assertIn("score no máximo 3", prompt)

    def test_rosto_deformado_direciona_para_imagem(self):
        checks = _checks(9)
        checks["rosto"] = {"score": 3, "ok": False, "reason": "Rosto deformado."}
        payload = {"overall_score": 5, "checks": checks}
        client = _FakeClient(_FakeResponse(json.dumps(payload)))
        auditor = GeminiVisualQualityAuditor(client)

        result = auditor.audit(
            self.creative,
            self.config,
            {"static_image_file": self.image},
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.recommended_stage, "imagem")
        self.assertIn("Rosto deformado", result.findings[0].reason)

    def test_celular_encoberto_tem_prioridade_sobre_layout(self):
        checks = _checks(9)
        checks["celular"] = {
            "score": 2,
            "ok": False,
            "reason": "Celular encoberto pelos cards.",
        }
        checks["texto"] = {
            "score": 5,
            "ok": False,
            "reason": "Headline com erro.",
        }
        payload = {"overall_score": 6, "checks": checks}
        client = _FakeClient(_FakeResponse(json.dumps(payload)))
        auditor = GeminiVisualQualityAuditor(client)

        result = auditor.audit(
            self.creative,
            self.config,
            {"static_image_file": self.image},
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.recommended_stage, "imagem")

    def test_qa_desativada_nao_chama_api(self):
        client = _FakeClient(_FakeResponse("{}"))
        auditor = GeminiVisualQualityAuditor(client, enabled=False)

        result = auditor.audit(
            self.creative,
            self.config,
            {"static_image_file": self.image},
        )

        self.assertTrue(result.skipped)
        self.assertTrue(result.passed)
        self.assertEqual(client.models.calls, 0)

    def test_qa_obrigatoria_reprova_quando_gemini_indisponivel(self):
        client = _FakeClient(_FakeResponse("{}"))
        auditor = GeminiVisualQualityAuditor(client, enabled=False, required=True)

        result = auditor.audit(
            self.creative,
            self.config,
            {"static_image_file": self.image},
        )

        self.assertTrue(result.skipped)
        self.assertFalse(result.passed)
        self.assertEqual(client.models.calls, 0)

    def test_prompt_reprova_texto_inventado_na_cena_base(self):
        payload = {"overall_score": 9, "checks": _checks(9)}
        client = _FakeClient(_FakeResponse(json.dumps(payload)))
        auditor = GeminiVisualQualityAuditor(client)

        auditor.audit(
            self.creative,
            self.config,
            {"static_image_file": self.image},
        )

        prompt = client.models.last_kwargs["contents"][0]
        self.assertIn("texto", prompt)
        self.assertIn("inventado pela IA", prompt)
        self.assertIn("bolha de conversa", prompt)


if __name__ == "__main__":
    unittest.main()
