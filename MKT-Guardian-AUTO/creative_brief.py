"""
Brief criativo — rotação de headlines e validação de diversidade.

Fase 2 do plano de criatividade: HeadlineRotator + similaridade Jaccard.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from campaign_history import CampaignHistory, headline_hash

if TYPE_CHECKING:
    pass

_WORD_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)


@dataclass(frozen=True)
class CreativeBrief:
    """Fonte única de verdade compartilhada pelos agentes da campanha."""

    objetivo: str
    publico: str
    publico_slug: str
    golpe: str
    golpe_id: str
    variante_golpe: str
    mensagem_golpista: str
    dor_principal: str
    promessa: str
    personagem: str
    cenario: str
    emocao: str
    estilo_visual: str
    canal: str
    duracao: str
    formato: dict
    textos_pos_producao: tuple[str, ...]
    restricoes: tuple[str, ...]
    chamada_para_acao: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["textos_pos_producao"] = list(self.textos_pos_producao)
        data["restricoes"] = list(self.restricoes)
        return data

    def to_prompt_block(self) -> str:
        """Formata o brief sem incluir instruções específicas de um único agente."""
        formato = self.formato
        linhas = [
            "BRIEF CRIATIVO ÚNICO — FONTE DE VERDADE DA CAMPANHA:",
            f"- Objetivo: {self.objetivo}",
            f"- Público: {self.publico} ({self.publico_slug})",
            f"- Golpe: {self.golpe} ({self.golpe_id})",
            f"- Variante: {self.variante_golpe or 'não definida'}",
            f"- Mensagem do golpista: {self.mensagem_golpista or 'não definida'}",
            f"- Dor principal: {self.dor_principal}",
            f"- Promessa: {self.promessa}",
            f"- Personagem: {self.personagem}",
            f"- Cenário: {self.cenario}",
            f"- Emoção: {self.emocao}",
            f"- Estilo visual: {self.estilo_visual}",
            f"- Canal: {self.canal}",
            f"- Duração da narração: {self.duracao}",
            f"- Formato: {formato.get('width')}x{formato.get('height')} ({formato.get('aspect_ratio')}) "
            f"| template {formato.get('template_id', 'não definido')}",
            f"- CTA obrigatório: {self.chamada_para_acao}",
            "- Textos inseridos somente na pós-produção: "
            + "; ".join(self.textos_pos_producao),
        ]
        if self.restricoes:
            linhas.append("- Restrições obrigatórias:")
            linhas.extend(f"  • {item}" for item in self.restricoes)
        linhas.append(
            "Todos os agentes devem respeitar este brief. Não invente outro público, golpe, "
            "cenário, promessa ou CTA."
        )
        return "\n".join(linhas)


def _first_text(values: object, fallback: str) -> str:
    if isinstance(values, list):
        for value in values:
            if str(value).strip():
                return str(value).strip()
    if isinstance(values, str) and values.strip():
        return values.strip()
    return fallback


def _default_cta(publico_slug: str, ctx: dict) -> str:
    if ctx.get("cta_template"):
        return str(ctx["cta_template"]).strip()
    if publico_slug == "escolas":
        return "PROTEJA SEUS ALUNOS COM GUARDIAN AI"
    if publico_slug == "empresarios":
        return "TESTE GRÁTIS — PROTEJA SEU WHATSAPP BUSINESS AGORA!"
    if publico_slug == "pais":
        return "TESTE GRÁTIS — PROTEJA O WHATSAPP DOS SEUS FILHOS!"
    return "TESTE GRÁTIS — PROTEJA SEU WHATSAPP AGORA!"


def build_creative_brief(
    config: dict,
    campaign_ctx: dict,
    golpe_obj: dict,
    preset: dict,
    context_data: dict | None = None,
) -> CreativeBrief:
    """Constrói o brief antes da geração de copy e assets."""
    context_data = context_data or {}
    produto = context_data.get("PRODUTO_E_POSICIONAMENTO", {})
    visual = context_data.get("DIRETRIZES_VISUAIS", {})
    capacidades = produto.get("capacidades_reais", {})
    restricoes = list(campaign_ctx.get("proibicoes_narrativa") or [])
    restricoes.extend(campaign_ctx.get("obrigacoes_narrativa") or [])
    restricoes.extend(
        [
            "Não inserir texto essencial dentro da imagem/vídeo gerado por IA.",
            "Não incluir URL na narração; URL e CTA entram na pós-produção.",
            "Mostrar o golpe e o alerta em conversa direta 1:1 no WhatsApp.",
        ]
    )
    restricoes.extend(capacidades.get("nao_faz") or [])

    dores = campaign_ctx.get("dores") or []
    gatilhos = campaign_ctx.get("gatilhos") or []
    estilo = visual.get(
        "estilo_fotografico",
        "Fotografia documental realista, cotidiano brasileiro bem cuidado.",
    )
    cenario = campaign_ctx.get("direcao_arte_emocional") or campaign_ctx.get(
        "persona_visual", "Ambiente cotidiano brasileiro organizado."
    )
    promessa = (
        produto.get("proposta_unica_de_valor")
        or "Detectar ameaças no WhatsApp e enviar um alerta imediato."
    )
    golpe = golpe_obj.get("nome") or config.get("golpe", "Golpe no WhatsApp")
    variante = campaign_ctx.get("scam_variant_titulo") or campaign_ctx.get(
        "scam_variant_id", ""
    )
    formato = {
        "width": preset.get("width", 1080),
        "height": preset.get("height", 1080),
        "aspect_ratio": preset.get("aspect_ratio", "1:1"),
        "preset_id": preset.get("preset_id", ""),
        "template_id": (preset.get("composition_template") or {}).get("template_id", ""),
        "target_narration_seconds": preset.get("target_narration_seconds"),
    }
    return CreativeBrief(
        objetivo=str(config.get("objetivo") or "Gerar instalação ou lead qualificado."),
        publico=str(config.get("publico") or campaign_ctx.get("icp_nome") or "Público selecionado"),
        publico_slug=str(config.get("publico_slug") or "geral"),
        golpe=str(golpe),
        golpe_id=str(config.get("golpe_id") or campaign_ctx.get("golpe_id") or ""),
        variante_golpe=str(variante),
        mensagem_golpista=str(campaign_ctx.get("frase_golpista") or golpe_obj.get("frase_golpista") or ""),
        dor_principal=_first_text(dores, "Medo de cair em um golpe recebido no WhatsApp."),
        promessa=str(promessa),
        personagem=str(
            campaign_ctx.get("protagonista")
            or campaign_ctx.get("persona_visual")
            or "Pessoa brasileira do público selecionado."
        ),
        cenario=str(cenario),
        emocao=", ".join(str(item) for item in gatilhos[:4]) or "urgência e proteção",
        estilo_visual=str(estilo),
        canal=str(config.get("canal") or "Canal não definido"),
        duracao=str(preset.get("copy_duration") or "Duração não definida"),
        formato=formato,
        textos_pos_producao=(
            "headline",
            "mensagem do card do golpe",
            "card de solução",
            "CTA",
            "URL",
        ),
        restricoes=tuple(dict.fromkeys(str(item).strip() for item in restricoes if str(item).strip())),
        chamada_para_acao=_default_cta(str(config.get("publico_slug") or ""), campaign_ctx),
    )


def tokenize_headline(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text or "") if len(w) > 1}


def jaccard_similarity(a: str, b: str) -> float:
    sa, sb = tokenize_headline(a), tokenize_headline(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


class HeadlineRotator:
    """Sorteia gancho do combo excluindo headlines já usadas no histórico."""

    SIMILARITY_THRESHOLD = 0.70

    def __init__(self, base_dir: str, history: CampaignHistory | None = None):
        self.base_dir = base_dir
        self.history = history or CampaignHistory(base_dir)
        self.state_path = os.path.join(
            base_dir, "contexto_negocio", "memoria", "ganchos_rotacao.json"
        )

    def _combo_key(self, config: dict) -> str:
        return f"{config.get('publico_slug', '')}:{config.get('golpe_id', '')}"

    def _load_state(self) -> dict:
        if not os.path.isfile(self.state_path):
            return {}
        try:
            with open(self.state_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self, state: dict) -> None:
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _used_hashes(self, publico: str, golpe: str) -> set[str]:
        return {
            r["headline_hash"]
            for r in self.history.get_recent(publico, golpe, limit=50)
            if r.get("headline_hash")
        }

    def last_headline(self, publico: str, golpe: str) -> str:
        recent = self.history.get_recent(publico, golpe, limit=1)
        return (recent[-1].get("headline") or "").strip() if recent else ""

    def similarity_to_last(self, headline: str, publico: str, golpe: str) -> float:
        last = self.last_headline(publico, golpe)
        if not last:
            return 0.0
        return jaccard_similarity(headline, last)

    def pick_gancho(
        self,
        campaign_ctx: dict,
        config: dict,
        advance: bool = True,
    ) -> tuple[str | None, int]:
        cached = config.get("_gancho_rotativo")
        if cached:
            return cached, int(config.get("_gancho_rotativo_idx", -1))

        ganchos = [g.strip() for g in (campaign_ctx.get("ganchos") or []) if g and str(g).strip()]
        if not ganchos:
            return None, -1

        publico = config.get("publico_slug", "")
        golpe = config.get("golpe_id", "")
        used = self._used_hashes(publico, golpe)
        combo = self._combo_key(config)
        state = self._load_state()
        last_idx = int(state.get(combo, -1))

        chosen_idx = -1
        chosen_gancho: str | None = None

        for offset in range(len(ganchos)):
            idx = (last_idx + 1 + offset) % len(ganchos)
            g = ganchos[idx]
            if headline_hash(g) not in used:
                chosen_idx, chosen_gancho = idx, g
                break

        if chosen_gancho is None:
            chosen_idx = (last_idx + 1) % len(ganchos)
            chosen_gancho = ganchos[chosen_idx]

        if advance:
            state[combo] = chosen_idx
            self._save_state(state)
            config["_gancho_rotativo"] = chosen_gancho
            config["_gancho_rotativo_idx"] = chosen_idx

        return chosen_gancho, chosen_idx

    def pick_fallback_gancho(
        self,
        campaign_ctx: dict,
        config: dict,
        avoid_similar_to: str = "",
    ) -> str | None:
        """Próximo gancho com baixa similaridade (fallback pós-Gemini)."""
        ganchos = [g.strip() for g in (campaign_ctx.get("ganchos") or []) if g and str(g).strip()]
        if not ganchos:
            return None

        publico = config.get("publico_slug", "")
        golpe = config.get("golpe_id", "")
        used = self._used_hashes(publico, golpe)
        ref = avoid_similar_to or self.last_headline(publico, golpe)

        best: str | None = None
        best_score = 1.0
        for g in ganchos:
            if headline_hash(g) in used:
                continue
            score = jaccard_similarity(g, ref) if ref else 0.0
            if score < best_score:
                best_score = score
                best = g
            if score < self.SIMILARITY_THRESHOLD:
                return g

        if best and best_score < self.SIMILARITY_THRESHOLD:
            return best

        for g in ganchos:
            if headline_hash(g) not in used:
                return g
        return ganchos[0] if ganchos else None

    def apply_headline_diversity(
        self,
        creative_data: dict,
        campaign_ctx: dict,
        config: dict,
    ) -> dict:
        """Corrige manchete quebrada ou >70% similar à última do combo."""
        headline = (creative_data.get("gancho_atencao_inicial") or "").strip()
        broken = [
            r"privad[oa][^.!?]{0,30}privad[oa]",
            r"conversa no WhatsApp[^.!?]{0,25}no privado",
            r"chat do WhatsApp[^.!?]{0,25}no privado",
            r"não acontece[^.!?]{0,40}no privado",
        ]
        publico = config.get("publico_slug", "")
        golpe = config.get("golpe_id", "")
        needs_replace = any(re.search(p, headline, re.IGNORECASE) for p in broken)
        sim = self.similarity_to_last(headline, publico, golpe)

        if not needs_replace and sim < self.SIMILARITY_THRESHOLD:
            if config.get("_gancho_rotativo"):
                creative_data.setdefault("headline_escolhida", config["_gancho_rotativo"])
            return creative_data

        reason = "contraditória" if needs_replace else f"similar ({sim:.0%}) à anterior"
        fallback = self.pick_fallback_gancho(campaign_ctx, config, avoid_similar_to=headline)
        if not fallback:
            gancho, _ = self.pick_gancho(campaign_ctx, config, advance=False)
            fallback = gancho

        if fallback:
            creative_data["gancho_atencao_inicial"] = fallback.upper()
            creative_data["headline_escolhida"] = fallback
            print(
                f"[!] Manchete {reason} -> substituida por gancho rotativo: "
                f"{creative_data['gancho_atencao_inicial'][:70]}"
            )
        return creative_data
