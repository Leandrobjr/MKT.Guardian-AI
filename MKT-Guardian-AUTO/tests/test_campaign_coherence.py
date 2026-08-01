"""Testes — campaign_coherence.py (nexo card/roteiro/headline)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_coherence import is_coherent, pick_coherent_gancho, theme_overlap


class TestCampaignCoherence(unittest.TestCase):
    def test_incoherent_cadastro_vs_brinde(self):
        roteiro = (
            "Você clica no link de atualização de cadastro do fornecedor no WhatsApp Business."
        )
        frase = "Parabéns! Você foi selecionado. Clique aqui para resgatar: bit.ly/brinde-2026"
        self.assertFalse(is_coherent(roteiro, frase))

    def test_coherent_fornecedor(self):
        roteiro = (
            "O golpista manda link de atualização de cadastro de fornecedor no WhatsApp Business."
        )
        frase = (
            "Olá, sou do cadastro de fornecedores. Atualize seus dados pelo link urgente: "
            "bit.ly/cadastro-fornecedor"
        )
        self.assertTrue(is_coherent(roteiro, frase))

    def test_pick_coherent_gancho_empresarios(self):
        ganchos = [
            "LINK FALSO DE FORNECEDOR NO WHATSAPP BUSINESS — LOJA CLICOU!",
            "PROMOÇÃO FALSA NO 1:1 ROUBOU DADOS DO NEGÓCIO.",
        ]
        frase = (
            "Olá, sou do cadastro de fornecedores. Atualize seus dados pelo link urgente: "
            "bit.ly/cadastro-fornecedor"
        )
        gancho, _ = pick_coherent_gancho(ganchos, frase)
        self.assertIn("FORNECEDOR", gancho)

    def test_theme_overlap_brinde_cadastro_low(self):
        self.assertLess(
            theme_overlap(
                "atualização de cadastro de fornecedor",
                "parabéns resgatar brinde prêmio",
            ),
            0.3,
        )


if __name__ == "__main__":
    unittest.main()
