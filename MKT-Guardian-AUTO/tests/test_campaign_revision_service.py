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

    def test_feedback_de_imagem_continua_regenerando_visual(self):
        self.assertFalse(
            CampaignRevisionService._is_layout_only_feedback(
                "Trocar o fundo e melhorar o rosto da personagem."
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


if __name__ == "__main__":
    unittest.main()
