"""Testes do contrato canônico de campanha."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_contract import (
    CampaignContractCatalog,
    CampaignContractError,
    CampaignContract,
    LEGACY_GOLPE_GROUPS,
    validate_creative_contract,
)


class TestCampaignContract(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.catalog = CampaignContractCatalog(self.base_dir)

    def test_catalogo_canonico_tem_vinte_tipos(self):
        self.assertEqual(self.catalog.validate_catalog(), [])
        self.assertEqual(len(self.catalog._types), 20)
        self.assertEqual(len(self.catalog._variant_to_type), 26)

    def test_tipos_financeiros_declaram_mecanismo_e_consequencia(self):
        required_ids = {
            item["id"]
            for item in self.catalog._types.values()
            if item.get("familia") == "fraude_financeira"
        } | {"falso_suporte_bancario", "engenharia_social_urgencia"}

        for canonical_id in required_ids:
            canonical = self.catalog._types[canonical_id]
            self.assertTrue(canonical.get("mecanismo"), canonical_id)
            self.assertTrue(canonical.get("consequencia"), canonical_id)

    def test_urgencia_bancaria_pertence_a_falsa_central(self):
        self.assertNotIn(
            "engenharia_social_urgencia",
            LEGACY_GOLPE_GROUPS["pix_fantasma"],
        )
        self.assertIn(
            "engenharia_social_urgencia",
            LEGACY_GOLPE_GROUPS["falsa_central"],
        )

    def test_constroi_contrato_para_variante_compativel(self):
        contract = self.catalog.build(
            {"publico_slug": "idosos", "golpe_id": "falso_parente"},
            {
                "scam_variant_id": "falso_pix_numero_novo",
                "frase_golpista": "Oi, troquei de número. Preciso de PIX urgente.",
            },
            protagonista_gender="masculino",
        )
        self.assertEqual(contract.canonical_type_id, "falso_pix_familiar")
        self.assertEqual(contract.combo_key, "idosos+falso_parente")

    def test_voz_clonada_com_pix_tem_consequencia_limitada(self):
        contract = self.catalog.build(
            {"publico_slug": "idosos", "golpe_id": "falso_parente"},
            {
                "scam_variant_id": "ia_voz_clonada",
                "frase_golpista": "Mãe, sou eu. Troquei de número e preciso de PIX.",
            },
            protagonista_gender="feminino",
        )
        self.assertEqual(contract.mecanismo, "transferencia_pix_autorizada")
        self.assertIn("somente o valor", contract.consequencia)

    def test_rejeita_casting_masculino_para_card_enderecado_a_mae(self):
        with self.assertRaises(CampaignContractError):
            self.catalog.build(
                {"publico_slug": "idosos", "golpe_id": "falso_parente"},
                {
                    "scam_variant_id": "falso_pix_numero_novo",
                    "frase_golpista": "Mãe, salva esse número e faça um PIX.",
                },
                protagonista_gender="masculino",
            )

    def test_rejeita_card_de_avo_para_publico_pais(self):
        with self.assertRaises(CampaignContractError):
            self.catalog.build(
                {"publico_slug": "pais", "golpe_id": "falso_parente"},
                {
                    "scam_variant_id": "ia_voz_clonada",
                    "frase_golpista": "Vó, é o neto. Preciso de dinheiro agora.",
                },
                protagonista_gender="feminino",
            )

    def test_rejeita_card_de_chefe_para_idosos(self):
        with self.assertRaises(CampaignContractError):
            self.catalog.build(
                {"publico_slug": "idosos", "golpe_id": "falso_parente"},
                {
                    "scam_variant_id": "ia_voz_clonada",
                    "frase_golpista": "Chefe, sou o João. Faça um PIX agora.",
                },
                protagonista_gender="masculino",
            )

    def test_rejeita_publico_geral(self):
        with self.assertRaises(CampaignContractError):
            self.catalog.build(
                {"publico_slug": "geral", "golpe_id": "pix_fantasma"},
                {
                    "scam_variant_id": "falso_pix_numero_novo",
                    "frase_golpista": "Oi mãe, preciso de PIX.",
                },
            )

    def test_rejeita_publico_id_divergente(self):
        with self.assertRaises(CampaignContractError):
            self.catalog.build(
                {
                    "publico_slug": "idosos",
                    "publico_id": "pais",
                    "golpe_id": "falso_parente",
                },
                {
                    "scam_variant_id": "falso_pix_numero_novo",
                    "frase_golpista": "Mãe, faça um PIX urgente.",
                },
            )

    def test_rejeita_variante_de_outro_subtipo(self):
        with self.assertRaises(CampaignContractError):
            self.catalog.build(
                {"publico_slug": "pais", "golpe_id": "grooming"},
                {
                    "scam_variant_id": "falso_medico_hospital",
                    "frase_golpista": "Hospital: seu filho precisa de PIX urgente.",
                },
            )

    def test_grooming_nao_inclui_sextorsao(self):
        variants = self.catalog.variant_ids_for_golpe("grooming")
        self.assertIn("grooming_romantico", variants)
        self.assertNotIn("sextorsao_ameaca", variants)
        self.assertNotIn("grooming_familiar_falso_filho", variants)
        self.assertIn(
            "grooming_familiar_falso_filho",
            self.catalog.variant_ids_for_golpe("falso_parente"),
        )

    def test_rejeita_headline_feminina_para_protagonista_masculino(self):
        contract = CampaignContract(
            publico_slug="idosos",
            golpe_id="falso_parente",
            variant_id="falso_pix_numero_novo",
            canonical_type_id="falso_pix_familiar",
            frase_golpista="Oi mãe, troquei de número. Preciso de PIX urgente.",
            allowed_publicos=frozenset({"idosos"}),
            protagonista_gender="masculino",
        )
        errors = validate_creative_contract(
            {
                "gancho_atencao_inicial": "ELA PERDEU A APOSENTADORIA",
                "desenvolvimento_copy": "Seu Carlos recebeu uma mensagem pedindo PIX urgente.",
                "texto_card_notificacao": contract.frase_golpista,
                "genero_personagem_visual": "Idoso (Carlos, 68 anos)",
                "protagonista_nome": "Carlos",
                "protagonista_genero": "masculino",
            },
            contract,
            expected_persona={"nome": "Carlos", "idade": 68},
        )
        self.assertIn("headline", " ".join(errors))

    def test_nao_confunde_pai_mencionado_na_fala_com_protagonista(self):
        contract = CampaignContract(
            publico_slug="idosos",
            golpe_id="falso_parente",
            variant_id="ia_voz_clonada",
            canonical_type_id="voz_clonada",
            frase_golpista="Vó, é o neto. Preciso de dinheiro agora.",
            allowed_publicos=frozenset({"idosos"}),
            protagonista_gender="feminino",
        )
        errors = validate_creative_contract(
            {
                "gancho_atencao_inicial": "NÃO CONTA PRO MEU PAI",
                "desenvolvimento_copy": "Dona Ruth recebeu uma mensagem urgente.",
                "texto_card_notificacao": contract.frase_golpista,
                "genero_personagem_visual": "Idosa (Ruth, 69 anos)",
                "protagonista_nome": "Ruth",
                "protagonista_genero": "feminino",
            },
            contract,
            expected_gender="feminino",
            expected_persona={"nome": "Ruth", "idade": 69},
        )
        self.assertNotIn("Gênero indicado na headline", " ".join(errors))

    def test_rejeita_roubo_da_conta_em_pix_autorizado(self):
        contract = self.catalog.build(
            {"publico_slug": "idosos", "golpe_id": "falso_parente"},
            {
                "scam_variant_id": "falso_pix_numero_novo",
                "frase_golpista": "Oi, troquei de número. Faça um PIX e devolvo amanhã.",
            },
        )
        errors = validate_creative_contract(
            {
                "gancho_atencao_inicial": "UM GOLPISTA PEDIU PIX",
                "desenvolvimento_copy": (
                    "O falso amigo esvaziou a conta de José e roubou toda sua aposentadoria."
                ),
                "texto_card_notificacao": contract.frase_golpista,
            },
            contract,
        )
        self.assertTrue(any("consequência incorreta" in error for error in errors))

    def test_aceita_nome_composto_do_casting(self):
        contract = self.catalog.build(
            {"publico_slug": "idosos", "golpe_id": "falso_parente"},
            {
                "scam_variant_id": "falso_pix_numero_novo",
                "frase_golpista": "Oi, troquei de número. Faça um PIX e devolvo amanhã.",
            },
            protagonista_gender="feminino",
        )
        errors = validate_creative_contract(
            {
                "gancho_atencao_inicial": "PIX PEDIDO POR AMIGO NO WHATSAPP PODE SER GOLPE",
                "desenvolvimento_copy": (
                    "Dona Maria Aparecida recebeu um pedido de PIX no WhatsApp."
                ),
                "texto_card_notificacao": contract.frase_golpista,
                "protagonista_nome": "Maria Aparecida",
                "protagonista_genero": "feminino",
                "genero_personagem_visual": "Idosa (Maria Aparecida)",
                "persona_visual": {"genero": "feminino"},
            },
            contract,
            expected_gender="feminino",
            expected_persona={
                "nome": "Maria Aparecida",
                "persona_id": "",
            },
        )
        self.assertNotIn(
            "Nome declarado do protagonista diverge do casting contratado.",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
