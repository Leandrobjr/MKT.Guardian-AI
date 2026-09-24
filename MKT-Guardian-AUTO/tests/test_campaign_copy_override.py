"""Regressões para preservar edição explícita da fala do card."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_orchestrator import CampaignOrchestrator
from copy_lexicon import CopyLexicon


class TestCampaignCopyOverride(unittest.TestCase):
    def setUp(self):
        self.orchestrator = CampaignOrchestrator.__new__(CampaignOrchestrator)

    def test_exact_card_edit_wins_over_variant(self):
        creative = {"texto_card_notificacao": "Oi, troquei de número."}
        config = {
            "_card_message_override": (
                "Oi Mãe! Troquei de número! Preciso urgente de R$ 1.000,00."
            )
        }
        result = self.orchestrator._align_card_message(
            creative,
            config,
            {"frase_golpista": "Oi, troquei de número."},
            {"frase_golpista": "Oi, troquei de número."},
        )
        self.assertEqual(
            result["texto_card_notificacao"],
            "Oi Mãe! Troquei de número! Preciso urgente de R$ 1.000,00.",
        )

    def test_prefix_edit_preserves_generated_card(self):
        creative = {"texto_card_notificacao": "Oi, Mãe!!! Troquei de número!"}
        result = self.orchestrator._align_card_message(
            creative,
            {"_preserve_card_message": True},
            {"frase_golpista": "Oi, troquei de número."},
            {"frase_golpista": "Oi, troquei de número."},
        )
        self.assertEqual(result["texto_card_notificacao"], "Oi, Mãe!!! Troquei de número!")

    def test_card_real_do_golpe_nao_e_sanitizado_como_promessa_do_produto(self):
        self.orchestrator.lexicon_guard = CopyLexicon(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        card = "Sua conta será bloqueada. Aja agora ou perderá todo o saldo."
        result = self.orchestrator._enforce_product_truth(
            {
                "texto_card_notificacao": card,
                "desenvolvimento_copy": "O Guardian AI detecta a ameaça e envia um alerta.",
            }
        )
        self.assertEqual(result["texto_card_notificacao"], card)

    def test_headline_pix_ambigua_e_substituida(self):
        result = self.orchestrator._sanitize_headline_semantics(
            {
                "gancho_atencao_inicial": "O PIX QUE VOCÊ FIZER HOJE PODE SER UM GOLPE"
            },
            {"frase_golpista": "Amigo, tô sem acesso ao banco. Pode fazer um PIX?"},
        )
        self.assertEqual(
            result["gancho_atencao_inicial"],
            "PIX PEDIDO POR AMIGO NO WHATSAPP PODE SER GOLPE",
        )

    def test_headline_respeita_genero_do_protagonista_no_roteiro(self):
        result = self.orchestrator._sanitize_headline_semantics(
            {"gancho_atencao_inicial": "ELE CONFIOU NO ATENDENTE. PERDEU TUDO."},
            {
                "frase_golpista": (
                    "Central de segurança: detectamos invasão na sua conta. "
                    "Envie o código SMS."
                )
            },
            {},
        )
        self.assertEqual(
            result["gancho_atencao_inicial"],
            "ELE CONFIOU NO ATENDENTE. PERDEU TUDO.",
        )

        result = self.orchestrator._sanitize_headline_semantics(
            {
                "gancho_atencao_inicial": "ELE CONFIOU NO ATENDENTE. PERDEU TUDO.",
                "desenvolvimento_copy": (
                    "Dona Maria recebeu uma mensagem da central de segurança."
                ),
            },
            {
                "frase_golpista": (
                    "Central de segurança: detectamos invasão na sua conta. "
                    "Envie o código SMS."
                )
            },
            {},
        )
        self.assertEqual(
            result["gancho_atencao_inicial"],
            "ELA CONFIOU NO ATENDENTE. PERDEU TUDO.",
        )

    def test_headline_de_voz_clonada_preserva_o_pretexto(self):
        result = self.orchestrator._sanitize_headline_semantics(
            {
                "gancho_atencao_inicial": (
                    "NOVO NÚMERO SALVO. CONFIRME ANTES DE FAZER O PIX."
                )
            },
            {
                "frase_golpista": (
                    "Mãe, sou eu. Troquei de número e preciso de PIX urgente — "
                    "ouviu meu áudio?"
                ),
            },
            {
                "_campaign_contract": {
                    "mecanismo": "transferencia_pix_autorizada",
                    "canonical_type_id": "voz_clonada",
                },
                "publico_slug": "pais",
            },
        )
        self.assertEqual(
            result["gancho_atencao_inicial"],
            "VOZ CLONADA PODE PEDIR PIX EM NOME DE SEU FILHO!",
        )

    def test_headline_pix_recebido_e_substituida_por_formula_clara(self):
        result = self.orchestrator._sanitize_headline_semantics(
            {
                "gancho_atencao_inicial": (
                    "CUIDADO: O PIX QUE VOCÊ RECEBER PODE fazer você perder apenas o valor enviado!"
                )
            },
            {"frase_golpista": "Oi, troquei de número. Preciso de um PIX urgente."},
            {
                "_campaign_contract": {
                    "mecanismo": "transferencia_pix_autorizada",
                }
            },
        )
        self.assertEqual(
            result["gancho_atencao_inicial"],
            "PEDIDO DE PIX NO WHATSAPP PODE SER GOLPE",
        )

    def test_headline_de_qr_code_preserva_pretexto_financeiro(self):
        result = self.orchestrator._sanitize_headline_semantics(
            {
                "gancho_atencao_inicial": (
                    "'FINANCEIRO' PEDIU PIX DE VOLTA — ERA FRAUDE."
                )
            },
            {
                "frase_golpista": (
                    "Fornecedor: use este QR Code para pagamento com desconto — válido só hoje."
                )
            },
            {
                "_campaign_contract": {
                    "mecanismo": "transferencia_pix_autorizada",
                    "canonical_type_id": "qr_code_pix",
                }
            },
        )
        self.assertEqual(
            result["gancho_atencao_inicial"],
            "QR CODE FALSO PODE DESVIAR SEU PAGAMENTO",
        )

    def test_pix_autorizado_nao_e_descrita_como_roubo_da_conta(self):
        result = self.orchestrator._sanitize_mechanism_claims(
            {
                "desenvolvimento_copy": (
                    "O falso amigo pode roubar sua economia pelo WhatsApp."
                )
            },
            {
                "_campaign_contract": {
                    "mecanismo": "transferencia_pix_autorizada",
                }
            },
        )
        self.assertEqual(
            result["desenvolvimento_copy"],
            "O falso amigo pode fazer você perder apenas o valor enviado pelo WhatsApp.",
        )

    def test_perder_economias_e_permitido_em_golpe_de_credenciais(self):
        original = {
            "desenvolvimento_copy": (
                "Ao clicar no link falso, a vítima pode perder suas economias."
            )
        }
        result = self.orchestrator._sanitize_mechanism_claims(
            original,
            {"_campaign_contract": {"mecanismo": "link_ou_credencial"}},
        )
        self.assertEqual(result, original)

    def test_qr_falso_nao_drena_capital_de_giro_ou_faturamento(self):
        result = self.orchestrator._sanitize_mechanism_claims(
            {
                "desenvolvimento_copy": (
                    "O golpista drena seu capital de giro. "
                    "Não deixe seu faturamento cair em mãos erradas. "
                    "Verifique antes de qualquer clique."
                )
            },
            {
                "_campaign_contract": {
                    "mecanismo": "transferencia_pix_autorizada",
                }
            },
        )
        self.assertEqual(
            result["desenvolvimento_copy"],
            (
                "O golpista faz você perder o valor pago. "
                "Não envie valores sem confirmar o destinatário. "
                "Verifique antes de qualquer pagamento."
            ),
        )

    def test_cena_visual_respeita_amigo_do_card(self):
        result = self.orchestrator._align_visual_relationship(
            {
                "direcao_arte_emocional": (
                    "Senior man reading a message pretending to be a relative."
                )
            },
            {"frase_golpista": "Amigo, tô sem acesso ao banco. Faça um PIX."},
        )
        self.assertIn("pretending to be a friend", result["direcao_arte_emocional"])

    def test_cena_de_idoso_respeita_falso_investimento(self):
        scene = self.orchestrator._build_publico_scene(
            "idosos",
            "falso_investimento",
            "masculino",
        )
        self.assertIn("investment or cryptocurrency offer", scene)
        self.assertNotIn("pretending to be a relative", scene)

    def test_tela_do_celular_nao_pede_texto_gerado_pela_ia(self):
        result = self.orchestrator._inject_phone_message_in_scene(
            {"texto_card_notificacao": "Mãe, faça um PIX urgente."},
            {},
            {},
        )
        clause = result["phone_screen_clause"].lower()
        self.assertIn("softly defocused whatsapp-style interface", clause)
        self.assertIn("exactly one physical smartphone", clause)
        self.assertIn("screen fully inside the frame", clause)
        self.assertIn("never cropped", clause)
        self.assertIn("upper 60 percent", clause)
        self.assertIn("above all lower-third graphics", clause)
        self.assertIn("no readable words", clause)
        self.assertIn("duplicated device", clause)
        self.assertIn("picture-in-picture", clause)
        self.assertIn("compositor", clause)
        self.assertNotIn("mãe, faça um pix urgente", clause)

    def test_nome_do_protagonista_recebe_marcador_de_genero(self):
        result = self.orchestrator._ensure_protagonist_gender_cue(
            {"desenvolvimento_copy": "Helena recebe uma mensagem urgente no WhatsApp."},
            {
                "_protagonist_gender": "feminino",
                "_protagonist_persona": {"nome": "Helena"},
            },
        )
        self.assertTrue(result["desenvolvimento_copy"].startswith("Dona Helena"))

    def test_cena_de_pais_respeita_protagonista_masculino(self):
        result = self.orchestrator._align_parent_visual_gender(
            {
                "direcao_arte_emocional": (
                    "Documentary photo of a Brazilian mother checking her teenage "
                    "daughter's smartphone, worried mother expression."
                ),
                "desenvolvimento_copy": "O filho recebeu uma mensagem privada.",
            },
            {"publico_slug": "pais", "_protagonist_gender": "masculino"},
        )
        self.assertIn("Brazilian father", result["direcao_arte_emocional"])
        self.assertIn("teenage son's smartphone", result["direcao_arte_emocional"])
        self.assertIn("worried father", result["direcao_arte_emocional"])

    def test_corrige_concordancia_do_cta_dos_seu(self):
        self.assertEqual(
            self.orchestrator._fix_pt_artifacts(
                "PROTEJA o WhatsApp dos SEU FILHO, AGORA!"
            ),
            "PROTEJA O WhatsApp do SEU FILHO, AGORA!",
        )

    def test_corrige_artefato_alerta_seu_acesso(self):
        self.assertEqual(
            self.orchestrator._fix_pt_artifacts(
                "O aplicativo falso assume sua conta, alerta seu acesso e limpa seu caixa."
            ),
            (
                "O aplicativo falso assume sua conta, obtém acesso indevido "
                "e limpa seu caixa."
            ),
        )

    def test_cta_de_pais_mantem_caixa_alta(self):
        cta = self.orchestrator._build_cta_button(
            {"publico_slug": "pais"},
            campaign_ctx={
                "cta_template": "TESTE GRÁTIS — PROTEJA o WhatsApp dos SEUS FILHOS, AGORA!",
            },
        )
        self.assertEqual(
            cta,
            "TESTE GRÁTIS — PROTEJA O WhatsApp dos SEUS FILHOS, AGORA!",
        )

    def test_pix_nao_e_tratado_como_perda_absoluta(self):
        result = self.orchestrator._sanitize_mechanism_claims(
            {
                "desenvolvimento_copy": (
                    "Você pode enviar um PIX que não volta mais."
                )
            },
            {
                "_campaign_contract": {
                    "mecanismo": "transferencia_pix_autorizada",
                }
            },
        )
        self.assertEqual(
            result["desenvolvimento_copy"],
            "Você pode enviar um PIX que pode ser difícil de recuperar.",
        )

    def test_pix_nao_pode_levar_a_economia_inteira(self):
        result = self.orchestrator._sanitize_mechanism_claims(
            {
                "desenvolvimento_copy": (
                    "O golpista pede PIX e pode levar sua economia."
                )
            },
            {
                "_campaign_contract": {
                    "mecanismo": "transferencia_pix_autorizada",
                }
            },
        )
        self.assertEqual(
            result["desenvolvimento_copy"],
            "O golpista pede PIX e pode fazer você perder apenas o valor enviado.",
        )

    def test_voz_clonada_com_pix_nao_promete_perda_da_aposentadoria(self):
        result = self.orchestrator._sanitize_mechanism_claims(
            {
                "gancho_atencao_inicial": (
                    "R$ 12 MIL DA APOSENTADORIA SUMIRAM EM UM PIX URGENTE."
                ),
                "desenvolvimento_copy": (
                    "A economia de uma vida inteira estava em risco."
                ),
            },
            {
                "_campaign_contract": {
                    "mecanismo": "transferencia_pix_autorizada",
                }
            },
        )
        self.assertNotIn("aposentadoria sumiram", result["gancho_atencao_inicial"].lower())
        self.assertNotIn("economia de uma vida inteira", result["desenvolvimento_copy"].lower())

    def test_headline_pix_complementada_e_normalizada(self):
        result = self.orchestrator._sanitize_headline_semantics(
            {
                "gancho_atencao_inicial": (
                    "ELA ENVIOU UM PIX. PERDEU O VALOR TRANSFERIDO AGORA!"
                )
            },
            {"frase_golpista": "Amigo, faça um PIX urgente."},
            {
                "_campaign_contract": {
                    "mecanismo": "transferencia_pix_autorizada",
                }
            },
        )
        self.assertEqual(
            result["gancho_atencao_inicial"],
            "PIX ENVIADO AO GOLPISTA PODE SER DIFÍCIL DE RECUPERAR",
        )

    def test_pix_nao_promete_proteger_a_aposentadoria_inteira(self):
        result = self.orchestrator._sanitize_mechanism_claims(
            {
                "desenvolvimento_copy": (
                    "Confirme antes de enviar. Proteja sua aposentadoria."
                )
            },
            {
                "_campaign_contract": {
                    "mecanismo": "transferencia_pix_autorizada",
                }
            },
        )
        self.assertEqual(
            result["desenvolvimento_copy"],
            "Confirme antes de enviar. proteja o valor antes de enviar.",
        )

    def test_pix_nao_promete_proteger_a_poupanca_inteira(self):
        result = self.orchestrator._sanitize_mechanism_claims(
            {
                "desenvolvimento_copy": (
                    "Confirme o pedido. Proteja sua poupança."
                )
            },
            {
                "_campaign_contract": {
                    "mecanismo": "transferencia_pix_autorizada",
                }
            },
        )
        self.assertEqual(
            result["desenvolvimento_copy"],
            "Confirme o pedido. confirme o pedido antes de fazer o PIX.",
        )


if __name__ == "__main__":
    unittest.main()
