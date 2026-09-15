"""Testes — creative_brief.py (HeadlineRotator + Jaccard)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_history import CampaignHistory
from creative_brief import HeadlineRotator, build_creative_brief, jaccard_similarity


class TestCreativeBrief(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.history = CampaignHistory(self.tmp)
        self.rotator = HeadlineRotator(self.tmp, self.history)

    def test_jaccard_identical(self):
        self.assertEqual(jaccard_similarity("GOLPE NO WHATSAPP PRIVADO", "golpe no whatsapp privado"), 1.0)

    def test_jaccard_different(self):
        score = jaccard_similarity("GOLPE NO WHATSAPP", "ESCOLA ALERTA PAIS")
        self.assertLess(score, 0.3)

    def test_pick_gancho_excludes_used(self):
        ctx = {
            "ganchos": [
                "HEADLINE A NO WHATSAPP",
                "HEADLINE B NO PRIVADO",
                "HEADLINE C URGENTE",
            ]
        }
        cfg = {"publico_slug": "pais", "golpe_id": "grooming"}
        self.history.registrar_campanha(
            {"gancho_atencao_inicial": "HEADLINE A NO WHATSAPP", "desenvolvimento_copy": "x",
             "direcao_arte_emocional": "cena", "texto_card_notificacao": "oi"},
            cfg,
            {"basename": "t1"},
        )
        gancho, idx = self.rotator.pick_gancho(ctx, cfg, advance=True)
        self.assertNotEqual(gancho, "HEADLINE A NO WHATSAPP")
        self.assertIn(gancho, ctx["ganchos"])

    def test_apply_diversity_replaces_similar(self):
        cfg = {"publico_slug": "pais", "golpe_id": "grooming"}
        self.history.registrar_campanha(
            {
                "gancho_atencao_inicial": "GOLPE NO WHATSAPP PRIVADO DO FILHO",
                "desenvolvimento_copy": "x",
                "direcao_arte_emocional": "cena",
                "texto_card_notificacao": "oi",
            },
            cfg,
            {"basename": "t1"},
        )
        ctx = {
            "ganchos": [
                "GOLPE NO WHATSAPP PRIVADO DO FILHO",
                "ESTRANHO MANDOU LINK NO CHAT SECRETO",
                "PREDADOR PEDIU FOTO NO PRIVADO",
            ]
        }
        creative = {"gancho_atencao_inicial": "GOLPE NO WHATSAPP PRIVADO DO SEU FILHO AGORA"}
        result = self.rotator.apply_headline_diversity(creative, ctx, cfg)
        self.assertNotEqual(
            result["gancho_atencao_inicial"],
            "GOLPE NO WHATSAPP PRIVADO DO SEU FILHO AGORA",
        )
        self.assertTrue(result.get("headline_escolhida"))

    def test_builds_single_brief_for_all_agents(self):
        brief = build_creative_brief(
            {
                "objetivo": "Geração de leads",
                "publico": "Pais e responsáveis",
                "publico_slug": "pais",
                "golpe": "Falso parente",
                "golpe_id": "falso_parente",
                "canal": "TikTok / YouTube Shorts",
                "midia": "Vídeo Vertical Animado",
            },
            {
                "icp_nome": "Pais e Responsáveis",
                "protagonista": "Mãe brasileira",
                "direcao_arte_emocional": "Sala organizada com celular em destaque",
                "dores": ["Medo de transferir dinheiro por urgência falsa"],
                "gatilhos": ["proteção familiar", "urgência"],
                "frase_golpista": "Seu filho sofreu um acidente. Faça um PIX.",
                "scam_variant_titulo": "Falso médico do hospital",
                "cta_template": "PROTEJA O WHATSAPP DOS SEUS FILHOS",
                "proibicoes_narrativa": ["Não usar grupos como origem do alerta."],
            },
            {
                "nome": "Golpe do falso parente",
                "frase_golpista": "Seu filho sofreu um acidente. Faça um PIX.",
            },
            {
                "preset_id": "shorts_urgente",
                "width": 1080,
                "height": 1920,
                "aspect_ratio": "9:16",
                "copy_duration": "12-18 segundos",
            },
            {
                "PRODUTO_E_POSICIONAMENTO": {
                    "proposta_unica_de_valor": "Detecta ameaças e envia alertas.",
                    "capacidades_reais": {"nao_faz": ["Não bloqueia mensagens."]},
                },
                "DIRETRIZES_VISUAIS": {
                    "estilo_fotografico": "Fotografia documental realista.",
                },
            },
        )

        data = brief.to_dict()
        prompt = brief.to_prompt_block()
        self.assertEqual(data["formato"]["aspect_ratio"], "9:16")
        self.assertEqual(data["variante_golpe"], "Falso médico do hospital")
        self.assertEqual(data["chamada_para_acao"], "PROTEJA O WHATSAPP DOS SEUS FILHOS")
        self.assertIn("BRIEF CRIATIVO ÚNICO", prompt)
        self.assertIn("Não inserir texto essencial", prompt)


if __name__ == "__main__":
    unittest.main()
