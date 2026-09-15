"""Auditoria da matriz público × tipo de golpe."""

import os
import json
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_contract import CampaignContractCatalog, LEGACY_GOLPE_GROUPS
from campaign_history import CampaignHistory
from scam_library import ScamLibrary


class TestCampaignMatrix(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.catalog = CampaignContractCatalog(self.base_dir)
        self.library = ScamLibrary(self.base_dir, CampaignHistory(tempfile.mkdtemp()))
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


if __name__ == "__main__":
    unittest.main()
