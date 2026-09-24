import unittest

from campaign_revision_service import CampaignRevisionService


class TestCampaignRevisionService(unittest.TestCase):
    def test_feedback_de_card_nao_regenera_a_cena(self):
        feedback = (
            "No card onde contém a mensagem final, ajuste a grafia e o tamanho "
            "da fonte do endereço do site. Não alterar a cena."
        )
        self.assertTrue(
            CampaignRevisionService._is_layout_only_feedback(feedback)
        )

    def test_feedback_de_headline_e_pronome_recompoe_overlay(self):
        self.assertTrue(
            CampaignRevisionService._is_layout_only_feedback(
                "Corrigir a headline e o pronome para concordar com o roteiro."
            )
        )

    def test_feedback_de_imagem_continua_regenerando_visual(self):
        self.assertFalse(
            CampaignRevisionService._is_layout_only_feedback(
                "Trocar o fundo e melhorar o rosto da personagem."
            )
        )

    def test_feedback_de_expressao_continua_regenerando_visual(self):
        self.assertFalse(
            CampaignRevisionService._is_layout_only_feedback(
                "Manter a cena, mas corrigir a expressão: personagem preocupada, séria e sem sorriso."
            )
        )

    def test_caption_recebe_cta_corrigido(self):
        caption = {
            "legenda": "Headline\n\nTESTE GRÁTIS — CTA anterior — https://guardian-ai.app"
        }
        result = CampaignRevisionService._caption_with_cta(
            caption,
            "TESTE GRÁTIS! PROTEJA O WHATSAPP DO SEU FILHO AGORA!",
            "https://guardian-ai.app",
        )
        self.assertIn(
            "TESTE GRÁTIS! PROTEJA O WHATSAPP DO SEU FILHO AGORA! — "
            "https://guardian-ai.app",
            result,
        )

    def test_prioriza_headline_editorial_do_historico(self):
        result = CampaignRevisionService._resolve_headline(
            {"metadata": {"headline": "HEADLINE GENÉRICA"}},
            {"headline": "HEADLINE DA VERSÃO ATUAL"},
            {
                "headline": "HEADLINE ANTIGA GENÉRICA",
                "headline_escolhida": "ELE CONFIOU NO ATENDENTE. PERDEU TUDO.",
            },
        )
        self.assertEqual(
            result,
            "ELE CONFIOU NO ATENDENTE. PERDEU TUDO.",
        )

    def test_corrige_genero_da_headline_recuperada_do_historico(self):
        result = CampaignRevisionService._resolve_headline(
            {
                "roteiro": "Dona Maria recebeu uma mensagem da central do banco.",
                "metadata": {"headline": "HEADLINE GENÉRICA"},
            },
            {},
            {
                "headline_escolhida": "ELE CONFIOU NO ATENDENTE. PERDEU TUDO.",
            },
        )
        self.assertEqual(
            result,
            "ELA CONFIOU NO ATENDENTE. PERDEU TUDO.",
        )

    def test_caption_atualiza_headline_e_preserva_roteiro(self):
        result = CampaignRevisionService._caption_with_headline(
            {
                "legenda": (
                    "HEADLINE GENÉRICA\n\n"
                    "Roteiro da campanha.\n\n"
                    "TESTE GRÁTIS — CTA anterior — https://guardian-ai.app"
                )
            },
            "HEADLINE ESPECÍFICA DO ROTEIRO",
            "TESTE GRÁTIS — PROTEJA SEU WHATSAPP AGORA!",
            "https://guardian-ai.app",
        )
        self.assertTrue(result.startswith("HEADLINE ESPECÍFICA DO ROTEIRO\n\n"))
        self.assertIn("Roteiro da campanha.", result)
        self.assertIn("guardian-ai.app", result)


if __name__ == "__main__":
    unittest.main()
