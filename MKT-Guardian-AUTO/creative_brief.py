"""
Brief criativo — rotação de headlines e validação de diversidade.

Fase 2 do plano de criatividade: HeadlineRotator + similaridade Jaccard.
"""

from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING

from campaign_history import CampaignHistory, headline_hash

if TYPE_CHECKING:
    pass

_WORD_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)


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
            r"conversa privada[^.!?]{0,25}no privado",
            r"chat privado[^.!?]{0,25}no privado",
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
