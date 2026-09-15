"""Testes — campaign_coherence.py (nexo card/roteiro/headline)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_coherence import (
    infer_recipient_gender,
    is_ambiguous_pix_headline,
    is_coherent,
    is_coherent_for_campaign,
    is_recipient_role_coherent,
    pick_coherent_gancho,
    theme_overlap,
)


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

    def test_voz_clonada_e_coerente_com_pix(self):
        self.assertTrue(
            is_coherent_for_campaign(
                "Uma voz clonada pediu um PIX urgente pelo WhatsApp.",
                "Mãe, sou eu. Preciso de PIX urgente — ouviu meu áudio?",
                "VOZ CLONADA PODE PEDIR PIX EM SEU NOME",
                "voz_clonada",
            )
        )

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

    def test_bloqueia_headline_ambigua_de_pix(self):
        self.assertTrue(
            is_ambiguous_pix_headline("O PIX QUE VOCÊ FIZER HOJE PODE SER UM GOLPE")
        )
        self.assertTrue(
            is_ambiguous_pix_headline(
                "O PIX QUE VOCÊ FIZER HOJE PODE CAIR NA CONTA DE UM GOLPISTA"
            )
        )

    def test_aceita_headline_com_sujeito_do_golpe(self):
        self.assertFalse(
            is_ambiguous_pix_headline(
                "UM GOLPISTA PODE DESVIAR O PIX PEDIDO NO WHATSAPP"
            )
        )

    def test_vocativo_mae_indica_protagonista_feminina(self):
        self.assertEqual(
            infer_recipient_gender("Mãe, salva esse número. Preciso de um PIX."),
            "feminino",
        )
        self.assertEqual(
            infer_recipient_gender("Amigo, pode fazer um PIX?"),
            "masculino",
        )
        self.assertEqual(
            infer_recipient_gender("Vó, é o neto. Preciso de dinheiro agora."),
            "feminino",
        )
        self.assertEqual(
            infer_recipient_gender("Vô, sou eu. Preciso de dinheiro agora."),
            "masculino",
        )

    def test_vocativo_de_avo_nao_e_coerente_com_pais(self):
        self.assertFalse(
            is_recipient_role_coherent(
                "Vó, é o neto. Estou preso e preciso de dinheiro agora.",
                "pais",
                "falso_parente",
            )
        )
        self.assertTrue(
            is_recipient_role_coherent(
                "Vó, é o neto. Estou preso e preciso de dinheiro agora.",
                "idosos",
                "falso_parente",
            )
        )
        self.assertFalse(
            is_recipient_role_coherent(
                "Chefe, sou o João. Faça um PIX para o fornecedor.",
                "idosos",
                "falso_parente",
            )
        )
        self.assertTrue(
            is_recipient_role_coherent(
                "Chefe, sou o João. Faça um PIX para o fornecedor.",
                "empresarios",
                "falso_parente",
            )
        )


if __name__ == "__main__":
    unittest.main()
