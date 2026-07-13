"""
Motor de contexto de campanha — Guardian AI

Resolve narrativa, ganchos, cena e CTA por combinação público × golpe,
evitando que o LLM e o pós-processamento repitam histórias parentais
em campanhas institucionais (ex.: escolas + grooming).
"""

from __future__ import annotations

import json
import os
from typing import Any


class CampaignContextEngine:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self._matrix: dict = {}
        self._load_matrix()

    def _load_matrix(self) -> None:
        path = os.path.join(self.base_dir, "contexto_negocio", "campanha_context_matrix.json")
        try:
            with open(path, encoding="utf-8") as f:
                self._matrix = json.load(f)
        except Exception as e:
            print(f"⚠️ Matriz de contexto não carregada ({path}): {e}")
            self._matrix = {}

    def _lookup_icp(self, publico_slug: str, context_data: dict) -> dict:
        icps = context_data.get("ICP_PUBLICOS", [])
        slug_to_id = {
            "idosos": "idosos",
            "pais": "pais",
            "empresarios": "profissionais",
            "escolas": "escolas",
        }
        icp_id = slug_to_id.get(publico_slug, publico_slug)
        for icp in icps:
            if icp.get("id") == icp_id:
                return icp
        return {}

    def _merge_layer(self, *layers: dict) -> dict:
        out: dict[str, Any] = {}
        for layer in layers:
            if not layer:
                continue
            for key, val in layer.items():
                if key.startswith("_"):
                    continue
                if isinstance(val, list) and key in out and isinstance(out[key], list):
                    out[key] = list(out[key]) + [v for v in val if v not in out[key]]
                else:
                    out[key] = val
        return out

    def resolve(
        self,
        publico_slug: str,
        golpe_id: str,
        golpe_obj: dict,
        context_data: dict,
    ) -> dict:
        icp = self._lookup_icp(publico_slug, context_data)
        por_publico = self._matrix.get(publico_slug, {})
        global_golpe = self._matrix.get("_defaults", {}).get(golpe_id, {})
        combo = por_publico.get(golpe_id, {})
        publico_default = por_publico.get("_default", {})

        merged = self._merge_layer(publico_default, global_golpe, combo)

        ganchos = merged.get("ganchos") or golpe_obj.get("ganchos", [])
        if isinstance(ganchos, str):
            ganchos = [ganchos]

        ctx = {
            "publico_slug": publico_slug,
            "golpe_id": golpe_id,
            "combo_key": f"{publico_slug}+{golpe_id}",
            "protagonista": merged.get("protagonista", icp.get("protagonista_padrao", "")),
            "angulo_narrativa": merged.get("angulo_narrativa", icp.get("angulo_padrao", "")),
            "dores": merged.get("dores") or icp.get("dores_principais", []),
            "gatilhos": merged.get("gatilhos") or icp.get("gatilhos_emocionais", []),
            "ganchos": ganchos,
            "gancho_modelo": merged.get("gancho_modelo") or golpe_obj.get("gancho_modelo", ""),
            "frase_golpista": merged.get("frase_golpista") or golpe_obj.get("frase_golpista", ""),
            "direcao_arte_emocional": merged.get("direcao_arte_emocional", ""),
            "cta_template": merged.get("cta_template", ""),
            "proibicoes_narrativa": merged.get("proibicoes_narrativa", []),
            "obrigacoes_narrativa": merged.get("obrigacoes_narrativa", []),
            "narrativa_parental": merged.get("narrativa_parental", publico_slug == "pais"),
            "persona_visual": merged.get("persona_visual", icp.get("persona_visual_padrao", "")),
            "icp_nome": icp.get("nome", publico_slug),
        }
        return ctx

    def format_for_prompt(self, ctx: dict) -> str:
        lines = [
            "CONTEXTO NARRATIVO OBRIGATÓRIO (público × golpe — NÃO misture com outros ICPs):",
            f"- Combo: {ctx['combo_key']}",
            f"- ICP: {ctx['icp_nome']}",
            f"- Protagonista: {ctx['protagonista'] or 'conforme ICP selecionado'}",
            f"- Ângulo da história: {ctx['angulo_narrativa'] or 'dor específica do ICP + golpe escolhido'}",
        ]
        if ctx.get("dores"):
            lines.append("- Dores a explorar: " + "; ".join(ctx["dores"][:5]))
        if ctx.get("gatilhos"):
            lines.append("- Gatilhos emocionais: " + ", ".join(ctx["gatilhos"][:4]))
        if ctx.get("ganchos"):
            lines.append(
                "- Ganchos para ESTE combo (inspire-se, não copie literalmente): "
                + " | ".join(ctx["ganchos"][:4])
            )
        if ctx.get("obrigacoes_narrativa"):
            lines.append("- OBRIGATÓRIO na copy:")
            for o in ctx["obrigacoes_narrativa"]:
                lines.append(f"  • {o}")
        if ctx.get("proibicoes_narrativa"):
            lines.append("- PROIBIDO na copy (violação = campanha inválida):")
            for p in ctx["proibicoes_narrativa"]:
                lines.append(f"  • {p}")
        if not ctx.get("narrativa_parental"):
            lines.append(
                "- Esta campanha NÃO é para pais em casa: NÃO use 'seu filho', 'sua filha', "
                "'proteja seus filhos' como eixo central."
            )
        return "\n".join(lines)

    def summary_line(self, ctx: dict) -> str:
        return (
            f"📌 Contexto: {ctx['combo_key']} | "
            f"{ctx['protagonista'][:60] + '…' if len(ctx.get('protagonista', '')) > 60 else ctx.get('protagonista', 'ICP padrão')}"
        )
