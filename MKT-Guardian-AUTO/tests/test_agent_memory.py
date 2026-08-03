"""Testes das regras linguísticas globais da memória do agente."""

import os
import shutil
import tempfile
import unittest

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_memory import AgentMemory


class TestAgentMemoryLinguisticRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        source = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "contexto_negocio",
            "memoria",
            "regras_linguisticas.json",
        )
        target_dir = os.path.join(self.tmp, "contexto_negocio", "memoria")
        os.makedirs(target_dir, exist_ok=True)
        shutil.copy(source, os.path.join(target_dir, "regras_linguisticas.json"))
        self.memory = AgentMemory(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_regras_globais_aparecem_em_qualquer_combo(self):
        prompt = self.memory.format_for_prompt("idosos", "falso_investimento")
        self.assertIn("NÃO USAR: monitora conversas privadas", prompt)
        self.assertIn("chat do WhatsApp", prompt)

    def test_aprender_feedback_deduplica_regra_existente(self):
        feedback = "Nunca usar monitora conversas privadas; preferir detecta e alerta."
        self.assertEqual(self.memory.aprender_regra_de_feedback(feedback), [])

    def test_aprender_nova_regra_de_grupos(self):
        feedback = "Não usar monitora grupos nas campanhas."
        learned = self.memory.aprender_regra_de_feedback(feedback)
        self.assertEqual(learned, ["nao_monitora_grupos"])
        rules = self.memory.regras_linguisticas()
        self.assertTrue(any(r.get("id") == "nao_monitora_grupos" for r in rules))

    def test_regra_manual_e_deduplicada(self):
        self.assertTrue(
            self.memory.registrar_regra_linguistica(
                "sem_vigilancia", "proibida", "vigia suas mensagens", "detecta ameaças"
            )
        )
        self.assertFalse(
            self.memory.registrar_regra_linguistica(
                "sem_vigilancia", "proibida", "vigia suas mensagens", "detecta ameaças"
            )
        )


if __name__ == "__main__":
    unittest.main()
