"""Testes — visual_variety.py (VisualCastingDirector / Fase 3)."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_history import CampaignHistory
from visual_variety import VisualVarietyEngine


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
        self.assertTrue(result["direcao_arte_emocional"].startswith("Base scene"))


if __name__ == "__main__":
    unittest.main()
