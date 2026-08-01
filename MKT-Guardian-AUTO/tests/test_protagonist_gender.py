"""Testes — infer_protagonist_gender (coerência roteiro × casting visual)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_coherence import infer_protagonist_gender, is_gender_coherent, describe_protagonist


class TestProtagonistGender(unittest.TestCase):
    def test_homem_no_campo_personagem(self):
        data = {"genero_personagem_visual": "Idoso (Homem, 72 anos)"}
        self.assertEqual(infer_protagonist_gender(data), "masculino")

    def test_dona_helena_com_headline_seu_whatsapp(self):
        """Headline 'SEU WHATSAPP' não deve anular Dona Helena no roteiro."""
        data = {
            "genero_personagem_visual": "Idosa (68 anos)",
            "gancho_atencao_inicial": "GOLPISTA PEDIU APORTE URGENTE VIA PIX NO SEU WHATSAPP",
            "desenvolvimento_copy": (
                "Aos 68 anos, Dona Helena quase perdeu a economia de uma vida inteira. "
                "Um contato enviou promessa de lucro no privado do WhatsApp dela."
            ),
        }
        self.assertEqual(infer_protagonist_gender(data), "feminino")

    def test_roteiro_vence_campo_personagem_masculino(self):
        """Roteiro Dona Helena prevalece sobre personagem 'Idoso homem' errado do Gemini."""
        data = {
            "genero_personagem_visual": "Idoso (Homem, 68 anos)",
            "desenvolvimento_copy": "Aos 68 anos, Dona Helena quase perdeu tudo no WhatsApp dela.",
        }
        self.assertEqual(infer_protagonist_gender(data), "feminino")

    def test_is_gender_coherent_apos_finalize_simulado(self):
        data = {
            "genero_campanha": "feminino",
            "desenvolvimento_copy": "Dona Helena quase caiu no golpe.",
        }
        self.assertTrue(is_gender_coherent(data))
        data["genero_campanha"] = "masculino"
        self.assertFalse(is_gender_coherent(data))

    def test_describe_protagonist_dona(self):
        data = {"desenvolvimento_copy": "Aos 68 anos, Dona Helena quase perdeu a economia."}
        self.assertIn("Helena", describe_protagonist(data))
        self.assertIn("feminino", describe_protagonist(data))

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
