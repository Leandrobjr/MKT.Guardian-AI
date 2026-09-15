"""Testes — visual_variety.py (VisualCastingDirector / Fase 3)."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_history import CampaignHistory
from visual_variety import VisualVarietyEngine
from visual_reference import VisualReferenceCatalog, validate_visual_reference


MINIMAL_CONTEXT = {
    "PERSONAS_EXEMPLO": [
        {
            "persona_id": "ana_professora_bh",
            "nome": "Ana",
            "idade": 42,
            "profissao": "Professora",
            "cidade": "Belo Horizonte",
            "publico_id": "pais",
            "genero": "feminino",
            "estilo_vestuario": "blusa lisa",
            "ambiente_preferido": "sala_tv",
            "nivel_socioeconomico": "classe_media",
        },
        {
            "persona_id": "marcos_pai_curitiba",
            "nome": "Marcos",
            "idade": 45,
            "profissao": "Analista",
            "cidade": "Curitiba",
            "publico_id": "pais",
            "genero": "masculino",
            "estilo_vestuario": "polo escuro",
            "ambiente_preferido": "home_office",
            "nivel_socioeconomico": "classe_media",
        },
    ],
    "GUARDRAILS_PERSONAGENS": {
        "faixas_etarias": {
            "pais": {"min": 35, "max": 50},
            "idosos": {"min": 65, "max": 85},
        }
    },
}


class TestVisualCasting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.history = CampaignHistory(self.tmp)
        self.engine = VisualVarietyEngine(self.tmp, self.history)

    def test_pick_persona_avoids_recent(self):
        cfg = {"publico_slug": "pais", "golpe_id": "grooming"}
        self.history.registrar_campanha(
            {
                "persona_id": "ana_professora_bh",
                "gancho_atencao_inicial": "X",
                "desenvolvimento_copy": "y",
                "direcao_arte_emocional": "cena",
                "texto_card_notificacao": "oi",
            },
            cfg,
            {"basename": "t1"},
        )
        picked = self.engine.pick_persona(MINIMAL_CONTEXT, "pais", "pais")
        self.assertNotEqual(picked.get("persona_id"), "ana_professora_bh")

    def test_nao_faz_fallback_para_persona_de_outro_publico(self):
        with self.assertRaises(ValueError):
            self.engine.pick_persona(MINIMAL_CONTEXT, "idosos", "idosos")

    def test_aplica_faixa_etaria_para_escolas(self):
        persona = {
            "nome": "Ana",
            "idade": 28,
            "publico_id": "escolas",
        }
        result = self.engine._apply_age_guardrails(persona, "escolas", MINIMAL_CONTEXT)
        self.assertEqual(result["idade"], 40)

    def test_pick_ambiente_rotates(self):
        a = self.engine.pick_ambiente("pais")
        b = self.engine.pick_ambiente("pais")
        self.assertIsInstance(a, str)
        self.assertIsInstance(b, str)
        self.assertNotEqual(a, b)

    def test_hash_duplicate_detection(self):
        prompt = "Documentary photo Brazilian adult with phone showing WhatsApp"
        self.assertFalse(self.engine.is_duplicate_prompt(prompt))
        self.engine.register_generated(prompt, "test_asset", engine="gemini")
        self.assertTrue(self.engine.is_duplicate_prompt(prompt))

    def test_enquadramentos_mantem_celular_inteiro(self):
        self.assertTrue(
            all(
                "entire smartphone" in shot or "complete smartphone" in shot
                for shot in self.engine.SHOT_VARIANTS
            )
        )

    def test_register_returns_false_on_duplicate(self):
        prompt = "Unique prompt for duplicate test"
        first = self.engine.register_generated(prompt, "a1", engine="kling")
        second = self.engine.register_generated(prompt, "a2", engine="kling")
        self.assertTrue(first)
        self.assertFalse(second)

    def test_enrich_adds_casting_fields(self):
        creative = {"direcao_arte_emocional": "Base scene", "genero_campanha": "feminino"}
        config = {"publico_id": "pais", "publico_slug": "pais"}
        result = self.engine.enrich(creative, config, MINIMAL_CONTEXT)
        self.assertIn("persona_visual", result)
        self.assertIn("persona_id", result)
        self.assertIn("ambiente_cena", result)
        self.assertIn("visual_shot_variant", result)
        self.assertIn("visual_reference", result)
        self.assertTrue(result["visual_reference_id"].startswith("ref_"))
        self.assertEqual(validate_visual_reference(result["visual_reference"]), [])
        self.assertTrue(result["direcao_arte_emocional"].startswith("Base scene"))

    def test_catalog_avoids_recent_reference(self):
        persona = MINIMAL_CONTEXT["PERSONAS_EXEMPLO"][0]
        first = VisualReferenceCatalog(MINIMAL_CONTEXT).pick(
            "pais", persona, "sala brasileira organizada"
        )
        second = VisualReferenceCatalog(
            MINIMAL_CONTEXT, {first.reference_id}
        ).pick("pais", persona, "sala brasileira organizada")
        self.assertNotEqual(first.reference_id, second.reference_id)
        self.assertTrue(second.aceito)
        self.assertTrue(second.rejeitado)


if __name__ == "__main__":
    unittest.main()
