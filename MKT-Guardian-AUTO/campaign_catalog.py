"""Catálogo oficial append-only de campanhas e versões."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any


CAMPAIGN_STATUSES = (
    "GERANDO",
    "AGUARDANDO_APROVACAO_HISTORIA",
    "PRODUZIDA",
    "AGUARDANDO_APROVACAO_FINAL",
    "AJUSTE_SOLICITADO",
    "APROVADA",
    "PRONTA_PARA_PUBLICAR",
    "PUBLICANDO",
    "PUBLICADA",
    "ERRO_PUBLICACAO",
    "REJEITADA",
)
_PUBLISHING_STATUSES = {"PUBLICANDO", "PUBLICADA"}
_ALLOWED_PUBLISH_SOURCES = {"APROVADA"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_text(value: Any, limit: int = 4000) -> str:
    return str(value or "").strip()[:limit]


class CampaignCatalog:
    """Mantém estado atual e versões sem sobrescrever registros anteriores."""

    def __init__(self, base_dir: str):
        self.memory_dir = os.path.join(base_dir, "contexto_negocio", "memoria")
        os.makedirs(self.memory_dir, exist_ok=True)
        self.path = os.path.join(self.memory_dir, "catalogo_campanhas.jsonl")

    def _append(self, record: dict[str, Any]) -> None:
        with open(self.path, "a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _load(self) -> list[dict[str, Any]]:
        if not os.path.isfile(self.path):
            return []
        rows: list[dict[str, Any]] = []
        with open(self.path, encoding="utf-8") as file:
            for line in file:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
        return rows

    def _current(self, campaign_id: str) -> dict[str, Any] | None:
        rows = [row for row in self._load() if row.get("campaign_id") == campaign_id]
        return rows[-1] if rows else None

    def _asset_path(self, assets: dict, config: dict) -> str:
        candidates = (
            assets.get("commercial_video_file"),
            assets.get("static_image_file"),
            assets.get("base_image_file"),
        )
        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            if candidate.upper() in {"N/A", "FALHOU", "NÃO SOLICITADO", "NÃO SOLICITADA"}:
                continue
            return os.path.abspath(candidate)
        return ""

    def _record(
        self,
        campaign_id: str,
        status: str,
        config: dict,
        creative_data: dict,
        assets: dict,
        *,
        current: dict | None = None,
        revision: int | None = None,
        platform: str = "",
        returned_id: str = "",
        error_message: str = "",
        actor: str = "orchestrator",
    ) -> dict[str, Any]:
        if status not in CAMPAIGN_STATUSES:
            raise ValueError(f"Status de campanha inválido: {status}")
        previous = current or {}
        now = _now()
        created_at = previous.get("data_criacao") or now
        approved_at = previous.get("data_aprovacao", "")
        published_at = previous.get("data_publicacao", "")
        approved_by = _safe_text(
            config.get("_approved_by") or previous.get("aprovado_por")
        )
        if status in {
            "GERANDO",
            "AGUARDANDO_APROVACAO_HISTORIA",
            "AGUARDANDO_APROVACAO_FINAL",
            "AJUSTE_SOLICITADO",
            "REJEITADA",
        }:
            approved_at = ""
            approved_by = ""
        if status == "APROVADA":
            approved_at = now
        if status == "PUBLICADA":
            published_at = now
        version = (
            int(previous.get("version", 0)) + 1
            if revision is None
            else max(int(previous.get("version", 0)), revision)
        )
        preset = config.get("preset_midia") or creative_data.get("preset_midia") or {}
        qa_evidence = assets.get("qa_evidence") or {}
        caption = (
            creative_data.get("caption")
            or config.get("_caption")
            or creative_data.get("legenda")
            or ""
        )
        return {
            "tipo": "catalogo_campanha",
            "campaign_id": campaign_id,
            "version": version,
            "status": status,
            "publico": _safe_text(config.get("publico_slug") or config.get("publico_id")),
            "golpe": _safe_text(config.get("golpe_id") or config.get("golpe")),
            "canal": _safe_text(config.get("canal")),
            "midia": _safe_text(config.get("midia") or creative_data.get("tipo_midia_selecionada")),
            "asset_path": self._asset_path(assets, config),
            "legenda": _safe_text(caption, 2000),
            "roteiro": _safe_text(creative_data.get("desenvolvimento_copy"), 4000),
            "preset": {
                "preset_id": _safe_text(preset.get("preset_id")),
                "resolucao": _safe_text(
                    f"{preset.get('width', '')}x{preset.get('height', '')}"
                ),
                "proporcao": _safe_text(preset.get("aspect_ratio")),
                "template_id": _safe_text(
                    (preset.get("composition_template") or {}).get("template_id")
                ),
            },
            "data_criacao": created_at,
            "data_aprovacao": approved_at,
            "aprovado_por": approved_by,
            "data_publicacao": published_at,
            "plataforma": _safe_text(platform or previous.get("plataforma")),
            "id_retornado": _safe_text(returned_id or previous.get("id_retornado")),
            "mensagem_erro": _safe_text(error_message or previous.get("mensagem_erro")),
            "headline": _safe_text(creative_data.get("gancho_atencao_inicial"), 500),
            "revisao": int(revision if revision is not None else config.get("_revision", 0)),
            "ator": _safe_text(actor, 120),
            "qa": {
                "multimodal_available": bool(qa_evidence.get("multimodal_available")),
                "multimodal_passed": bool(qa_evidence.get("multimodal_passed")),
                "overall_score": qa_evidence.get("overall_score"),
                "model": _safe_text(qa_evidence.get("model"), 120),
            },
            "atualizado_em": now,
        }

    def create(self, config: dict) -> str:
        campaign_id = _safe_text(config.get("_campaign_id")) or (
            f"camp_{uuid.uuid4().hex[:16]}"
        )
        config["_campaign_id"] = campaign_id
        self._append(
            self._record(campaign_id, "GERANDO", config, {}, {}, revision=0)
        )
        return campaign_id

    def update(
        self,
        campaign_id: str,
        status: str,
        config: dict,
        creative_data: dict | None = None,
        assets: dict | None = None,
        *,
        revision: int | None = None,
        platform: str = "",
        returned_id: str = "",
        error_message: str = "",
        actor: str = "orchestrator",
    ) -> dict[str, Any]:
        current = self._current(campaign_id)
        if current and status in _PUBLISHING_STATUSES:
            if current.get("status") == "PUBLICADA":
                raise ValueError("Publicação duplicada bloqueada pelo catálogo.")
            if status == "PUBLICANDO" and current.get("status") not in _ALLOWED_PUBLISH_SOURCES:
                raise ValueError(
                    f"Campanha não está pronta para publicação: {current.get('status')}"
                )
            if status == "PUBLICADA" and current.get("status") != "PUBLICANDO":
                raise ValueError(
                    "Campanha precisa estar em PUBLICANDO antes de PUBLICADA."
                )
        record = self._record(
            campaign_id,
            status,
            config,
            creative_data or {},
            assets or {},
            current=current,
            revision=revision,
            platform=platform,
            returned_id=returned_id,
            error_message=error_message,
            actor=actor,
        )
        self._append(record)
        return record

    def get(self, campaign_id: str) -> dict[str, Any] | None:
        return self._current(campaign_id)

    def versions(self, campaign_id: str) -> list[dict[str, Any]]:
        return [
            row for row in self._load()
            if row.get("campaign_id") == campaign_id
        ]

    def list_current(self, status: str = "") -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for row in self._load():
            campaign_id = row.get("campaign_id")
            if campaign_id:
                latest[campaign_id] = row
        values = list(latest.values())
        return [row for row in values if not status or row.get("status") == status]

    def can_publish(self, campaign_id: str) -> bool:
        current = self.get(campaign_id)
        return bool(
            current
            and current.get("status") == "APROVADA"
            and (
                bool(current.get("aprovado_por"))
                or current.get("ator") == "human"
            )
        )
