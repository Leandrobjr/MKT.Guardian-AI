"""Biblioteca de golpes WhatsApp — variantes rotativas por golpe_id × público."""

from __future__ import annotations

import json
import os
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from campaign_history import CampaignHistory


class ScamLibrary:
    """Seleciona variantes de mensagem golpista evitando repetição recente."""

    def __init__(self, base_dir: str, history: CampaignHistory | None = None):
        self.base_dir = base_dir
        self.mem_dir = os.path.join(base_dir, "contexto_negocio", "memoria")
        os.makedirs(self.mem_dir, exist_ok=True)
        self.rotacao_path = os.path.join(self.mem_dir, "scam_rotacao.json")
        self._history = history
        self._data = self._load_library()

    def _get_history(self) -> CampaignHistory:
        if self._history is None:
            from campaign_history import CampaignHistory
            self._history = CampaignHistory(self.base_dir)
        return self._history

    def _load_library(self) -> dict:
        path = os.path.join(self.base_dir, "contexto_negocio", "golpes_whatsapp.json")
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"⚠️ Biblioteca de golpes não carregada ({path}): {e}")
            return {"variantes": []}

    def _load_rotacao(self) -> dict:
        if not os.path.isfile(self.rotacao_path):
            return {}
        try:
            with open(self.rotacao_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_rotacao(self, state: dict) -> None:
        try:
            with open(self.rotacao_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _norm_frase(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())

    def _recent_frases(self, golpe_id: str, publico_slug: str, limit: int = 8) -> set[str]:
        used: set[str] = set()
        for row in self._get_history().get_recent(publico_slug, golpe_id, limit=limit * 2):
            frase = row.get("frase_golpista") or ""
            if frase:
                used.add(self._norm_frase(frase))
            vid = row.get("scam_variant_id") or ""
            if vid:
                used.add(f"variant:{vid}")
        return used

    def _variant_pool(
        self,
        golpe_id: str,
        publico_slug: str,
        allowed_variant_ids: set[str] | frozenset[str] | None = None,
    ) -> list[dict]:
        variantes = self._data.get("variantes") or []
        if allowed_variant_ids:
            pool = [v for v in variantes if v.get("variant_id") in allowed_variant_ids]
        else:
            pool = [v for v in variantes if v.get("golpe_id") == golpe_id]
        if not pool:
            return []
        if publico_slug == "geral":
            return []
        if publico_slug:
            preferidos = [
                v for v in pool
                if publico_slug in (v.get("publicos") or [])
            ]
            if preferidos:
                return preferidos
            # ICP específico: não usar variantes de outro público (ex.: brinde/massa em empresários)
            neutros = [v for v in pool if not v.get("publicos")]
            if neutros:
                return neutros
            return []
        return pool

    def _phrase_allowed_for_publico(
        self,
        frase: str,
        publico_slug: str,
        golpe_id: str,
    ) -> bool:
        from campaign_coherence import is_recipient_role_coherent

        return is_recipient_role_coherent(frase, publico_slug, golpe_id)

    def _pick_frase(
        self,
        variant: dict,
        used: set[str],
        publico_slug: str,
        golpe_id: str,
    ) -> str:
        frases = variant.get("frases_golpista") or []
        if not frases:
            return ""
        elegiveis = [
            f
            for f in frases
            if self._phrase_allowed_for_publico(f, publico_slug, golpe_id)
        ]
        if not elegiveis:
            return ""
        fresh = [f for f in elegiveis if self._norm_frase(f) not in used]
        pool = fresh if fresh else elegiveis
        return random.choice(pool)

    def pick_variant(
        self,
        golpe_id: str,
        publico_slug: str = "",
        allowed_variant_ids: set[str] | frozenset[str] | None = None,
    ) -> dict | None:
        """Retorna variante com frase_golpista rotativa para o combo."""
        pool = self._variant_pool(golpe_id, publico_slug, allowed_variant_ids)
        if not pool:
            return None

        used = self._recent_frases(golpe_id, publico_slug)
        state = self._load_rotacao()
        combo_key = f"{publico_slug or 'geral'}|{golpe_id}"
        last_idx = int(state.get(combo_key, -1))

        ordered = list(pool)
        if len(ordered) > 1:
            start = (last_idx + 1) % len(ordered)
            ordered = ordered[start:] + ordered[:start]

        for variant in ordered:
            vid = variant.get("variant_id", "")
            if vid and f"variant:{vid}" in used:
                continue
            frase = self._pick_frase(variant, used, publico_slug, golpe_id)
            if not frase:
                continue
            if last_idx >= 0:
                for i, v in enumerate(pool):
                    if v.get("variant_id") == vid:
                        state[combo_key] = i
                        break
            else:
                state[combo_key] = 0
            self._save_rotacao(state)
            return {
                "variant_id": vid,
                "golpe_id": golpe_id,
                "titulo": variant.get("titulo", ""),
                "frase_golpista": frase,
                "ordem_md": variant.get("ordem_md"),
            }

        variant = random.choice(pool)
        frase = self._pick_frase(variant, used, publico_slug, golpe_id)
        if not frase:
            return None
        return {
            "variant_id": variant.get("variant_id", ""),
            "golpe_id": golpe_id,
            "titulo": variant.get("titulo", ""),
            "frase_golpista": frase,
            "ordem_md": variant.get("ordem_md"),
        }

    def has_compatible_variant(
        self,
        golpe_id: str,
        publico_slug: str,
        allowed_variant_ids: set[str] | frozenset[str] | None = None,
    ) -> bool:
        return bool(self._variant_pool(golpe_id, publico_slug, allowed_variant_ids))

    def apply_to_context(
        self,
        campaign_ctx: dict,
        golpe_id: str,
        publico_slug: str,
        allowed_variant_ids: set[str] | frozenset[str] | None = None,
    ) -> dict:
        """Enriquece campaign_ctx com frase rotativa da biblioteca."""
        picked = self.pick_variant(golpe_id, publico_slug, allowed_variant_ids)
        if not picked:
            return campaign_ctx
        ctx = dict(campaign_ctx)
        ctx["frase_golpista"] = picked["frase_golpista"]
        ctx["scam_variant_id"] = picked["variant_id"]
        ctx["scam_variant_titulo"] = picked.get("titulo", "")
        ctx["angulo_golpe"] = picked.get("titulo", "")
        return ctx

    def count_variants(self, golpe_id: str = "") -> int:
        variantes = self._data.get("variantes") or []
        if golpe_id:
            return sum(1 for v in variantes if v.get("golpe_id") == golpe_id)
        return len(variantes)
