"""Testes — infer_protagonist_gender (coerência roteiro × casting visual)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_coherence import infer_protagonist_gender


class TestProtagonistGender(unittest.TestCase):
    def test_homem_no_campo_personagem(self):
        data = {"genero_personagem_visual": "Idoso (Homem, 72 anos)"}
        self.assertEqual(infer_protagonist_gender(data), "masculino")

    def test_mulher_no_campo_personagem(self):
        data = {"genero_personagem_visual": "Idosa (Mulher, 68 anos)"}
        self.assertEqual(infer_protagonist_gender(data), "feminino")

    def test_seu_carlos_no_roteiro(self):
        data = {
            "desenvolvimento_copy": (
                "Aos 72 anos, o Seu Carlos viu a economia de uma vida inteira desaparecer em minutos."
            ),
        }
        self.assertEqual(infer_protagonist_gender(data), "masculino")

    def test_dona_maria_no_roteiro(self):
        data = {
            "desenvolvimento_copy": "Dona Maria quase caiu no golpe do PIX quando recebeu a mensagem.",
        }
        self.assertEqual(infer_protagonist_gender(data), "feminino")

    def test_mae_no_gancho(self):
        data = {"gancho_atencao_inicial": "SUA MÃE PODE PERDER TUDO COM UM PIX FALSO"}
        self.assertEqual(infer_protagonist_gender(data), "feminino")

    def test_neutro_sem_pistas(self):
        data = {"desenvolvimento_copy": "Golpistas usam WhatsApp para aplicar fraudes."}
        self.assertEqual(infer_protagonist_gender(data), "")


if __name__ == "__main__":
    unittest.main()
