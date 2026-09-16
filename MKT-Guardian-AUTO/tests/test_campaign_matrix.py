"""Auditoria da matriz público × tipo de golpe."""

import os
import json
import sys
import tempfile
import unicodedata
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_contract import (
    CampaignContractCatalog,
    LEGACY_GOLPE_GROUPS,
    PUBLICO_ID_BY_SLUG,
    _gender_cues,
)
from campaign_history import CampaignHistory
from campaign_orchestrator import CampaignOrchestrator
from scam_library import ScamLibrary
from visual_variety import VisualVarietyEngine


def _normalize(text: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )


class TestCampaignMatrix(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.catalog = CampaignContractCatalog(self.base_dir)
        self.library = ScamLibrary(self.base_dir, CampaignHistory(tempfile.mkdtemp()))
        with open(
            os.path.join(self.base_dir, "contexto_negocio", "guardian_base.json"),
            encoding="utf-8",
        ) as file:
            self.context_data = json.load(file)
        self.types = {
            item["id"]: item
            for item in self.catalog._catalog.get("tipos", [])
        }

    def test_publicos_canonicos_possuem_variante_operacional_compativel(self):
        for golpe_id, canonical_ids in LEGACY_GOLPE_GROUPS.items():
            allowed_variant_ids = self.catalog.variant_ids_for_golpe(golpe_id)
            for publico in ("idosos", "pais", "empresarios", "escolas"):
                canonical_supported = any(
                    publico in self.types[canonical_id].get("publicos", [])
                    for canonical_id in canonical_ids
                    if canonical_id in self.types
                )
                operational_supported = self.library.has_compatible_variant(
                    golpe_id,
                    publico,
                    allowed_variant_ids,
                )
                self.assertEqual(
                    operational_supported,
                    canonical_supported,
                    f"{publico}+{golpe_id}: catálogo e biblioteca divergem",
                )

    def test_matriz_de_contexto_nao_declara_combinacao_invalida(self):
        with open(
            os.path.join(
                self.base_dir,
                "contexto_negocio",
                "campanha_context_matrix.json",
            ),
            encoding="utf-8",
        ) as file:
            matrix = json.load(file)

        for publico in ("idosos", "pais", "empresarios", "escolas"):
            for golpe_id in matrix.get(publico, {}):
                if golpe_id == "_default":
                    continue
                self.assertTrue(
                    self.library.has_compatible_variant(
                        golpe_id,
                        publico,
                        self.catalog.variant_ids_for_golpe(golpe_id),
                    ),
                    f"Matriz declara combinação inválida: {publico}+{golpe_id}",
                )

    def test_toda_variante_tem_frase_compativel_com_cada_publico_declarado(self):
        for golpe_id in LEGACY_GOLPE_GROUPS:
            allowed = self.catalog.variant_ids_for_golpe(golpe_id)
            for publico in ("idosos", "pais", "empresarios", "escolas"):
                for variant in self.library._variant_pool(golpe_id, publico, allowed):
                    frases = variant.get("frases_golpista") or []
                    compativeis = [
                        frase
                        for frase in frases
                        if self.library._phrase_allowed_for_publico(
                            frase,
                            publico,
                            golpe_id,
                        )
                    ]
                    self.assertTrue(
                        compativeis,
                        f"{publico}+{golpe_id}+{variant.get('variant_id')}: "
                        "nenhuma frase compatível",
                    )

    def test_ganchos_da_matriz_nao_fixam_genero_do_protagonista(self):
        with open(
            os.path.join(
                self.base_dir,
                "contexto_negocio",
                "campanha_context_matrix.json",
            ),
            encoding="utf-8",
        ) as file:
            matrix = json.load(file)

        for publico in ("idosos", "pais", "empresarios", "escolas"):
            for golpe_id, context in matrix.get(publico, {}).items():
                if golpe_id == "_default":
                    continue
                for gancho in context.get("ganchos", []):
                    self.assertFalse(
                        _gender_cues(gancho),
                        f"{publico}+{golpe_id}: gancho fixa gênero: {gancho}",
                    )

    def test_ganchos_nao_usam_claims_proibidos_pelo_mecanismo(self):
        with open(
            os.path.join(
                self.base_dir,
                "contexto_negocio",
                "campanha_context_matrix.json",
            ),
            encoding="utf-8",
        ) as file:
            matrix = json.load(file)

        for publico in ("idosos", "pais", "empresarios", "escolas"):
            for golpe_id, context in matrix.get(publico, {}).items():
                if golpe_id == "_default":
                    continue
                for canonical_id in LEGACY_GOLPE_GROUPS.get(golpe_id, set()):
                    canonical = self.types.get(canonical_id) or {}
                    if publico not in (canonical.get("publicos") or []):
                        continue
                    for gancho in context.get("ganchos", []):
                        normalized_hook = _normalize(gancho)
                        for forbidden in canonical.get("termos_proibidos", []):
                            self.assertNotIn(
                                _normalize(forbidden),
                                normalized_hook,
                                f"{publico}+{golpe_id}: claim proibido "
                                f"{forbidden!r} em {gancho!r}",
                            )

    def test_matriz_nao_exige_expressao_proibida_pelo_lexico(self):
        with open(
            os.path.join(
                self.base_dir,
                "contexto_negocio",
                "campanha_context_matrix.json",
            ),
            encoding="utf-8",
        ) as file:
            matrix = json.load(file)
        positive_texts = []
        for publico_data in matrix.values():
            if not isinstance(publico_data, dict):
                continue
            for context in publico_data.values():
                if not isinstance(context, dict):
                    continue
                for key, value in context.items():
                    if "proib" in key.casefold():
                        continue
                    if isinstance(value, str):
                        positive_texts.append(value)
                    elif isinstance(value, list):
                        positive_texts.extend(
                            item for item in value if isinstance(item, str)
                        )
        matrix_text = "\n".join(positive_texts).casefold()
        forbidden = (
            self.context_data.get("PRODUTO_E_POSICIONAMENTO", {})
            .get("tom_de_voz_obrigatorio", {})
            .get("palavras_proibidas", [])
        )
        for expression in forbidden:
            self.assertNotIn(
                expression.casefold(),
                matrix_text,
                f"Matriz exige expressão proibida pelo léxico: {expression}",
            )

    def test_personas_e_cenas_respeitam_cada_publico(self):
        temp_dir = tempfile.mkdtemp()
        history = CampaignHistory(temp_dir)
        variety = VisualVarietyEngine(self.base_dir, history)
        orchestrator = CampaignOrchestrator.__new__(CampaignOrchestrator)
        age_ranges = {
            "idosos": (65, 85),
            "pais": (35, 50),
            "empresarios": (35, 55),
            "escolas": (40, 55),
        }
        scene_markers = {
            "idosos": ("senior", "retired", "65-82"),
            "pais": ("parent", "mother", "father"),
            "empresarios": ("shop", "store", "office", "business", "commercial", "desk", "counter"),
            "escolas": ("school", "educational", "director", "coordinator"),
        }

        for publico, publico_id in PUBLICO_ID_BY_SLUG.items():
            if publico not in age_ranges:
                continue
            for genero in ("feminino", "masculino"):
                persona = variety.pick_persona(
                    self.context_data,
                    publico_id,
                    publico,
                    genero,
                )
                self.assertEqual(persona.get("genero"), genero)
                self.assertTrue(
                    age_ranges[publico][0]
                    <= int(persona["idade"])
                    <= age_ranges[publico][1]
                )

            for golpe_id in LEGACY_GOLPE_GROUPS:
                if not self.library.has_compatible_variant(
                    golpe_id,
                    publico,
                    self.catalog.variant_ids_for_golpe(golpe_id),
                ):
                    continue
                scene = orchestrator._build_publico_scene(
                    publico,
                    golpe_id,
                    "feminino",
                ).lower()
                self.assertTrue(
                    any(marker in scene for marker in scene_markers[publico]),
                    f"{publico}+{golpe_id}: cena fora do público: {scene}",
                )


if __name__ == "__main__":
    unittest.main()
