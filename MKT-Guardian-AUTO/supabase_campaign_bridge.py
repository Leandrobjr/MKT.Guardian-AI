"""Ponte segura de campanhas entre o Linux e o Desktop via Supabase.

Este módulo é somente backend: exige SUPABASE_SERVICE_ROLE_KEY e nunca deve
ser importado por uma interface que rode no navegador.
"""

from __future__ import annotations

import mimetypes
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from env_loader import load_project_env

BUCKET_DEFAULT = "mkt-campaign-assets"
MAX_ASSET_BYTES_DEFAULT = 1024 * 1024 * 1024
ALLOWED_ASSETS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".mp4": "video/mp4",
}
CAMPAIGN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


class SupabaseBridgeError(RuntimeError):
    """Erro operacional da ponte Linux ↔ Desktop."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean(value: Any, limit: int = 4000) -> str:
    return str(value or "").strip()[:limit]


class SupabaseCampaignBridge:
    """Sincroniza campanhas e comandos usando credencial exclusiva do backend."""

    def __init__(
        self,
        base_dir: str,
        *,
        client: Any | None = None,
        bucket: str | None = None,
        max_asset_bytes: int | None = None,
    ):
        load_project_env()
        self.base_dir = os.path.realpath(base_dir)
        self.bucket = bucket or os.getenv("SUPABASE_CAMPAIGN_BUCKET", BUCKET_DEFAULT)
        self.max_asset_bytes = max_asset_bytes or int(
            os.getenv("SUPABASE_MAX_ASSET_BYTES", str(MAX_ASSET_BYTES_DEFAULT))
        )
        self.client = client or self._build_client()

    @classmethod
    def from_env(cls, base_dir: str) -> "SupabaseCampaignBridge | None":
        """Inicializa a ponte somente quando o operador a habilita explicitamente."""
        load_project_env()
        enabled = os.getenv("SUPABASE_CAMPAIGN_SYNC", "").strip().lower()
        if enabled not in {"1", "true", "yes", "on"}:
            return None
        return cls(base_dir)

    @staticmethod
    def _build_client() -> Any:
        url = os.getenv("SUPABASE_URL", "").strip()
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not service_key:
            raise SupabaseBridgeError(
                "SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY são obrigatórios "
                "para sincronizar campanhas no backend."
            )
        try:
            from supabase import create_client
        except ImportError as exc:
            raise SupabaseBridgeError(
                "Dependência supabase não instalada. Instale requirements.txt."
            ) from exc
        return create_client(url, service_key)

    def _validate_campaign_id(self, campaign_id: str) -> str:
        campaign_id = _clean(campaign_id, 100)
        if not CAMPAIGN_ID_PATTERN.fullmatch(campaign_id):
            raise SupabaseBridgeError("campaign_id inválido para o Storage.")
        return campaign_id

    def _validate_asset(self, asset_path: str) -> tuple[str, str]:
        if not isinstance(asset_path, str) or not asset_path.strip():
            raise SupabaseBridgeError("Asset vazio.")
        normalized = os.path.realpath(asset_path)
        try:
            if os.path.commonpath((self.base_dir, normalized)) != self.base_dir:
                raise SupabaseBridgeError("Asset fora do diretório permitido.")
        except ValueError as exc:
            raise SupabaseBridgeError("Caminho de asset inválido.") from exc
        path = Path(normalized)
        extension = path.suffix.lower()
        content_type = ALLOWED_ASSETS.get(extension) or mimetypes.guess_type(
            normalized
        )[0]
        if extension not in ALLOWED_ASSETS or content_type not in set(ALLOWED_ASSETS.values()):
            raise SupabaseBridgeError("Extensão de asset não permitida.")
        if not path.is_file():
            raise SupabaseBridgeError("Asset não encontrado.")
        if path.stat().st_size > self.max_asset_bytes:
            raise SupabaseBridgeError("Asset excede o tamanho máximo configurado.")
        return normalized, content_type

    def _storage_path(self, campaign_id: str, asset_path: str, version: int) -> str:
        campaign_id = self._validate_campaign_id(campaign_id)
        basename = os.path.basename(asset_path)
        if not basename or basename in {".", ".."} or "/" in basename or "\\" in basename:
            raise SupabaseBridgeError("Nome de asset inválido.")
        return f"{campaign_id}/v{max(0, int(version))}/{basename}"

    def upload_asset(
        self, campaign_id: str, asset_path: str, *, version: int = 0
    ) -> dict[str, str]:
        """Faz upload idempotente de um asset aprovado para bucket privado."""
        normalized, content_type = self._validate_asset(asset_path)
        storage_path = self._storage_path(campaign_id, normalized, version)
        try:
            with open(normalized, "rb") as file:
                self.client.storage.from_(self.bucket).upload(
                    storage_path,
                    file,
                    {"content-type": content_type, "upsert": "true"},
                )
        except Exception as exc:
            raise SupabaseBridgeError(f"Falha no upload do asset: {exc}") from exc
        return {
            "bucket": self.bucket,
            "storage_path": storage_path,
            "content_type": content_type,
            "basename": os.path.basename(normalized),
        }

    def sync_campaign(self, record: dict[str, Any]) -> dict[str, Any]:
        """Publica metadata segura e, quando existente, o asset no Supabase."""
        campaign_id = self._validate_campaign_id(record.get("campaign_id", ""))
        asset_path = record.get("asset_path") or ""
        storage = {
            "bucket": self.bucket,
            "storage_path": "",
            "basename": _clean(os.path.basename(asset_path), 255),
        }
        if asset_path:
            storage = self.upload_asset(
                campaign_id,
                asset_path,
                version=int(record.get("version", 0)),
            )

        payload = {
            "campaign_id": campaign_id,
            "version": max(0, int(record.get("version", 0))),
            "status": _clean(record.get("status"), 80),
            "publico": _clean(record.get("publico"), 120),
            "golpe": _clean(record.get("golpe"), 120),
            "canal": _clean(record.get("canal"), 80),
            "midia": _clean(record.get("midia"), 80),
            "basename": storage["basename"],
            "storage_bucket": storage["bucket"],
            "storage_path": storage["storage_path"],
            "legenda": _clean(record.get("legenda"), 2200),
            "roteiro": _clean(record.get("roteiro"), 4000),
            "preset": record.get("preset") or {},
            "metadata": {
                "headline": _clean(record.get("headline"), 500),
                "revisao": int(record.get("revisao", 0)),
                "ator": _clean(record.get("ator"), 120),
                "asset_available": bool(asset_path),
            },
            "plataforma": _clean(record.get("plataforma"), 80),
            "id_retornado": _clean(record.get("id_retornado"), 300),
            "mensagem_erro": _clean(record.get("mensagem_erro"), 1000),
            "data_criacao": record.get("data_criacao") or _now(),
            "data_aprovacao": record.get("data_aprovacao") or None,
            "data_publicacao": record.get("data_publicacao") or None,
            "atualizado_em": record.get("atualizado_em") or _now(),
        }
        try:
            response = (
                self.client.table("mkt_campaigns")
                .upsert(payload, on_conflict="campaign_id")
                .execute()
            )
        except Exception as exc:
            raise SupabaseBridgeError(
                f"Falha ao gravar metadata da campanha: {exc}"
            ) from exc
        return {
            "campaign_id": campaign_id,
            "status": payload["status"],
            "storage_path": storage["storage_path"],
            "data": response.data or [],
        }

    def claim_pending_commands(self, limit: int = 10) -> list[dict[str, Any]]:
        """Reivindica comandos pendentes sem permitir dupla execução concorrente."""
        bounded_limit = max(1, min(int(limit), 50))
        response = self._list_pending_commands(bounded_limit)

        claimed: list[dict[str, Any]] = []
        for command in response:
            command_id = command.get("id")
            if not command_id:
                continue
            try:
                result = (
                    self.client.table("mkt_campaign_commands")
                    .update({"status": "CLAIMED", "claimed_at": _now()})
                    .eq("id", command_id)
                    .eq("status", "PENDING")
                    .execute()
                )
            except Exception as exc:
                raise SupabaseBridgeError(
                    f"Falha ao reivindicar comando {command_id}: {exc}"
                ) from exc
            if result.data:
                claimed.append({**command, "status": "CLAIMED"})
        return claimed

    def list_pending_commands(self, limit: int = 10) -> list[dict[str, Any]]:
        """Lista comandos sem alterar estados; usado exclusivamente no dry-run."""
        bounded_limit = max(1, min(int(limit), 50))
        return self._list_pending_commands(bounded_limit)

    def _list_pending_commands(self, limit: int) -> list[dict[str, Any]]:
        try:
            response = (
                self.client.table("mkt_campaign_commands")
                .select("*")
                .eq("status", "PENDING")
                .order("created_at")
                .limit(limit)
                .execute()
            )
        except Exception as exc:
            raise SupabaseBridgeError(f"Falha ao consultar comandos: {exc}") from exc
        return response.data or []

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        """Obtém uma campanha pelo ID, sem retornar credenciais."""
        campaign_id = self._validate_campaign_id(campaign_id)
        try:
            response = (
                self.client.table("mkt_campaigns")
                .select("*")
                .eq("campaign_id", campaign_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise SupabaseBridgeError(
                f"Falha ao consultar campanha {campaign_id}: {exc}"
            ) from exc
        return (response.data or [None])[0]

    def validate_local_asset(self, asset_path: str) -> str:
        """Valida e normaliza asset local antes de qualquer publicação."""
        return self._validate_asset(asset_path)[0]

    def update_campaign_publication(
        self,
        campaign_id: str,
        status: str,
        *,
        platform: str = "",
        returned_id: str = "",
        error_message: str = "",
        approved_by: str = "",
    ) -> None:
        """Atualiza apenas o estado de publicação no backend."""
        if status not in {"PUBLICANDO", "PUBLICADA", "ERRO_PUBLICACAO"}:
            raise SupabaseBridgeError("Status de publicação inválido.")
        campaign_id = self._validate_campaign_id(campaign_id)
        payload: dict[str, Any] = {
            "status": status,
            "plataforma": _clean(platform, 80),
            "id_retornado": _clean(returned_id, 300),
            "mensagem_erro": _clean(error_message, 1000),
            "atualizado_em": _now(),
        }
        if status == "PUBLICADA":
            payload["data_publicacao"] = _now()
        if approved_by and status == "PUBLICANDO":
            payload["aprovado_por"] = approved_by
        try:
            self.client.table("mkt_campaigns").update(payload).eq(
                "campaign_id", campaign_id
            ).execute()
        except Exception as exc:
            raise SupabaseBridgeError(
                f"Falha ao atualizar publicação {campaign_id}: {exc}"
            ) from exc

    def complete_command(
        self,
        command_id: str,
        *,
        success: bool,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        """Registra resultado sem persistir tokens ou respostas brutas de APIs."""
        safe_result = {
            key: value
            for key, value in (result or {}).items()
            if key in {
                "status",
                "platform",
                "returned_id",
                "campaign_id",
                "executor",
            }
        }
        if error:
            safe_result["error"] = _clean(error, 1000)
        payload = {
            "status": "SUCCEEDED" if success else "FAILED",
            "result": safe_result,
            "completed_at": _now(),
        }
        try:
            self.client.table("mkt_campaign_commands").update(payload).eq(
                "id", command_id
            ).eq("status", "CLAIMED").execute()
        except Exception as exc:
            raise SupabaseBridgeError(
                f"Falha ao registrar resultado do comando: {exc}"
            ) from exc
