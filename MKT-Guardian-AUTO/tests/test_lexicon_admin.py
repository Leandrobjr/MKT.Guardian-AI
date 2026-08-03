"""Testes da CLI de administração do léxico."""

import json
import os
import shutil
import tempfile
import unittest

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copy_lexicon import CopyLexicon
from lexicon_admin import main


class TestLexiconAdmin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "contexto_negocio", "memoria"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_adiciona_regra_proibida(self):
        result = main(
            [
                "--base-dir",
                self.tmp,
                "add-proibida",
                "vigia suas mensagens",
                "--usar",
                "detecta ameaças",
            ]
        )
        self.assertEqual(result, 0)
        path = os.path.join(
            self.tmp, "contexto_negocio", "memoria", "regras_linguisticas.json"
        )
        with open(path, encoding="utf-8") as f:
            rules = json.load(f)
        self.assertEqual(rules[0]["tipo"], "proibida")

        lexicon = CopyLexicon(self.tmp)
        violations = lexicon.scan_violations("O app vigia suas mensagens.")
        self.assertTrue(violations)

    def test_regra_duplicada_nao_cria_segunda_entrada(self):
        args = ["--base-dir", self.tmp, "add-sugerida", "detecta ameaças"]
        self.assertEqual(main(args), 0)
        self.assertEqual(main(args), 0)
        path = os.path.join(
            self.tmp, "contexto_negocio", "memoria", "regras_linguisticas.json"
        )
        with open(path, encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)), 1)


if __name__ == "__main__":
    unittest.main()
