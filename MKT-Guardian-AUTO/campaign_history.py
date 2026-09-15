"""
Histórico de campanhas — anti-repetição de headlines, cenas e combos.

Arquivo append-only: contexto_negocio/memoria/campanhas_historico.jsonl
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime


def _norm_headline(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().upper())


def headline_hash(headline: str) -> str:
    return hashlib.sha256(_norm_headline(headline).encode("utf-8")).hexdigest()[:12]


def visual_hash(direcao_arte: str, persona_id: str = "") -> str:
    base = f"{persona_id}|{(direcao_arte or '')[:500].strip().lower()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:12]


def _persona_id(creative_data: dict) -> str:
    if creative_data.get("persona_id"):
        return str(creative_data["persona_id"])
    persona = creative_data.get("persona_visual") or {}
    if isinstance(persona, dict) and persona.get("nome"):
        prof = persona.get("profissao", "")
        return f"{persona['nome']}_{prof}".lower().replace(" ", "_")[:40]
    hint = (creative_data.get("genero_personagem_visual") or "").strip()
    if hint:
        return hashlib.sha256(hint.lower().encode()).hexdigest()[:12]
    return creative_data.get("visual_variation_id", "") or ""


class CampaignHistory:
    def __init__(self, base_dir: str):
        self.mem_dir = os.path.join(base_dir, "contexto_negocio", "memoria")
        os.makedirs(self.mem_dir, exist_ok=True)
        self.path = os.path.join(self.mem_dir, "campanhas_historico.jsonl")

    def _append(self, record: dict) -> None:
        record.setdefault("data", datetime.now().strftime("%Y-%m-%d %H:%M"))
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _load_all(self) -> list[dict]:
        if not os.path.isfile(self.path):
            return []
        rows: list[dict] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def _combo_key(self, publico: str, golpe: str) -> str:
        return f"{publico or 'geral'}|{golpe or 'geral'}"

    def _match_combo(self, row: dict, publico: str, golpe: str) -> bool:
        if publico and row.get("publico") != publico:
            return False
        if golpe and row.get("golpe") != golpe:
            return False
        return True

    def build_record(
        self,
        creative_data: dict,
        config: dict,
        assets_resultado: dict,
        status: str,
        revisao: int = 0,
        asset_path: str = "",
    ) -> dict:
        headline = (creative_data.get("gancho_atencao_inicial") or "").strip()
        copy = (creative_data.get("desenvolvimento_copy") or "").strip()
        cena = (creative_data.get("direcao_arte_emocional") or "").strip()
        pid = _persona_id(creative_data)
        publico = config.get("publico_slug") or config.get("publico_id") or "geral"
        golpe = config.get("golpe_id") or "geral"
        basename = assets_resultado.get("basename") or ""
        if not asset_path:
            asset_path = assets_resultado.get("commercial_video_file") or assets_resultado.get(
                "static_image_file", ""
            )
        ambiente = creative_data.get("ambiente_cena") or ""
        regras = creative_data.get("regras_visuais") or {}
        if isinstance(regras, dict):
            ambiente = ambiente or regras.get("ambiente") or regras.get("cenario") or ""
        preset_metadata = config.get("preset_metadata") or config.get("_channel_metadata") or {}
        preset = config.get("preset_midia") or creative_data.get("preset_midia") or {}

        return {
            "tipo": "campanha_historico",
            "campaign_id": config.get("_campaign_id", ""),
            "status": status,
            "basename": basename,
            "publico": publico,
            "golpe": golpe,
            "combo": self._combo_key(publico, golpe),
            "headline": headline,
            "headline_hash": headline_hash(headline),
            "headline_escolhida": (
                creative_data.get("headline_escolhida")
                or config.get("_gancho_rotativo")
                or ""
            )[:200],
            "copy_hook": copy[:200],
            "visual_hash": visual_hash(cena, pid),
            "persona_id": pid,
            "visual_reference_id": creative_data.get("visual_reference_id", ""),
            "visual_reference": creative_data.get("visual_reference") or {},
            "ambiente": ambiente,
            "frase_golpista": (creative_data.get("texto_card_notificacao") or "")[:160],
            "scam_variant_id": config.get("_campaign_context", {}).get("scam_variant_id", ""),
            "asset_path": asset_path if isinstance(asset_path, str) else "",
            "revisao": revisao,
            "canal": config.get("canal", ""),
            "midia": config.get("midia", ""),
            "preset_id": preset_metadata.get("preset_id") or preset.get("preset_id", ""),
            "resolucao": preset_metadata.get("resolucao")
            or f"{preset.get('width', '')}x{preset.get('height', '')}",
            "proporcao": preset_metadata.get("proporcao") or preset.get("aspect_ratio", ""),
            "duracao_copy": preset_metadata.get("duracao_copy") or preset.get("copy_duration", ""),
            "duracao_alvo_segundos": preset_metadata.get("duracao_alvo_segundos")
            or preset.get("target_narration_seconds"),
            "ritmo": preset_metadata.get("ritmo", ""),
            "tipo_trilha": preset_metadata.get("tipo_trilha") or preset.get("trilha_tipo", ""),
            "velocidade_narracao": preset_metadata.get("velocidade_narracao")
            or preset.get("eleven_speed"),
            "storyboard": creative_data.get("storyboard")
            or config.get("_storyboard")
            or [],
        }

    def registrar_campanha(
        self,
        creative_data: dict,
        config: dict,
        assets_resultado: dict,
        status: str = "gerado",
        revisao: int = 0,
        asset_path: str = "",
    ) -> dict:
        record = self.build_record(
            creative_data, config, assets_resultado, status, revisao, asset_path
        )
        self._append(record)
        return record

    def get_recent(
        self,
        publico: str = "",
        golpe: str = "",
        limit: int = 10,
    ) -> list[dict]:
        rows = self._load_all()
        if publico or golpe:
            rows = [r for r in rows if self._match_combo(r, publico, golpe)]
        return rows[-limit:]

    def is_headline_used(
        self,
        headline: str,
        publico: str = "",
        golpe: str = "",
    ) -> bool:
        h = headline_hash(headline)
        for row in reversed(self._load_all()):
            if not self._match_combo(row, publico, golpe):
                continue
            if row.get("headline_hash") == h:
                return True
        return False

    def is_visual_used(
        self,
        direcao_arte: str,
        persona_id: str = "",
        publico: str = "",
        golpe: str = "",
    ) -> bool:
        vh = visual_hash(direcao_arte, persona_id)
        for row in reversed(self._load_all()):
            if not self._match_combo(row, publico, golpe):
                continue
            if row.get("visual_hash") == vh:
                return True
        return False

    def format_anti_repeticao(
        self,
        publico: str = "",
        golpe: str = "",
        limit: int = 8,
    ) -> str:
        recent = self.get_recent(publico, golpe, limit=limit)
        if not recent:
            return ""

        headlines: list[str] = []
        cenas: list[str] = []
        frases: list[str] = []
        for row in recent:
            h = (row.get("headline") or "").strip()
            if h and h not in headlines:
                headlines.append(h[:100])
            hook = (row.get("copy_hook") or "").strip()
            if hook and hook not in cenas:
                cenas.append(hook[:80] + ("…" if len(hook) > 80 else ""))
            fg = (row.get("frase_golpista") or "").strip()
            if fg and fg not in frases:
                frases.append(fg[:80])

        partes = [f"ANTI-REPETIÇÃO — combo {publico}/{golpe} (últimas {len(recent)} campanhas):"]

        if headlines:
            partes.append("\nHEADLINES JÁ USADAS (NÃO REPETIR — crie manchete nova):")
            for h in headlines:
                partes.append(f"- {h}")

        if cenas:
            partes.append("\nÂNGULOS DE ROTEIRO JÁ EXPLORADOS (use abordagem diferente):")
            for c in cenas[:6]:
                partes.append(f"- {c}")

        if frases:
            partes.append("\nFRASES DE GOLPISTA JÁ USADAS NO CARD (varie a mensagem):")
            for fg in frases[:5]:
                partes.append(f"- {fg}")

        partes.append(
            "\nROTEIRO: escolha protagonista, cenário ou gancho emocional "
            "DIFERENTE dos listados acima."
        )
        return "\n".join(partes)

    def print_dashboard(self, limit: int = 10) -> None:
        rows = self.get_recent(limit=limit)
        if not rows:
            return
        print(f"\n📚 Últimas {len(rows)} campanhas no histórico:")
        for row in rows:
            st = row.get("status", "?")
            print(
                f"   [{st}] {row.get('data', '—')} | {row.get('combo', '—')} | "
                f"{(row.get('headline') or '')[:55]}"
            )
