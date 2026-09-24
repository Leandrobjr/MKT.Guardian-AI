"""Ponte segura de campanhas entre o Linux e o Desktop via Supabase.

Este módulo é somente backend: exige SUPABASE_SERVICE_ROLE_KEY e nunca deve
ser importado por uma interface que rode no navegador.
"""

from __future__ import annotations

import mimetypes
import os
import re
from datetime import datetime, timedelta, timezone
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
CREATION_SOURCES = {"DESKTOP", "TELEGRAM"}
CREATION_PUBLICS = {"idosos", "pais", "empresarios", "escolas"}
CREATION_SCAMS = {
    "falso_parente",
    "pix_fantasma",
    "falsa_central",
    "grooming",
    "phishing",
    "clonagem_whatsapp",
    "link_malicioso",
    "falso_emprego",
    "falso_investimento",
}


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
        base_asset_path = record.get("base_asset_path") or ""
        storage = {
            "bucket": self.bucket,
            "storage_path": "",
            "basename": _clean(os.path.basename(asset_path), 255),
        }
        base_storage = {
            "bucket": self.bucket,
            "storage_path": "",
            "basename": _clean(os.path.basename(base_asset_path), 255),
        }
        if asset_path:
            storage = self.upload_asset(
                campaign_id,
                asset_path,
                version=int(record.get("version", 0)),
            )
        if base_asset_path and os.path.isfile(os.path.realpath(base_asset_path)):
            base_storage = self.upload_asset(
                campaign_id,
                base_asset_path,
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
                "base_asset_available": bool(base_storage["storage_path"]),
                "base_storage_path": base_storage["storage_path"],
                "qa": record.get("qa") or {},
            },
            "plataforma": _clean(record.get("plataforma"), 80),
            "id_retornado": _clean(record.get("id_retornado"), 300),
            "mensagem_erro": _clean(record.get("mensagem_erro"), 1000),
            "aprovado_por": _clean(record.get("aprovado_por"), 120) or None,
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

    def recover_stale_commands(
        self,
        *,
        stale_after_seconds: int = 1800,
        limit: int = 20,
    ) -> list[str]:
        """Devolve à fila comandos CLAIMED abandonados por um worker interrompido."""
        bounded_limit = max(1, min(int(limit), 50))
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(seconds=max(60, int(stale_after_seconds)))
        ).isoformat()
        try:
            response = (
                self.client.table("mkt_campaign_commands")
                .select("id")
                .eq("status", "CLAIMED")
                .lt("claimed_at", cutoff)
                .order("claimed_at")
                .limit(bounded_limit)
                .execute()
            )
        except Exception as exc:
            raise SupabaseBridgeError(
                f"Falha ao localizar comandos abandonados: {exc}"
            ) from exc

        recovered: list[str] = []
        for row in response.data or []:
            command_id = row.get("id")
            if not command_id:
                continue
            try:
                result = (
                    self.client.table("mkt_campaign_commands")
                    .update(
                        {
                            "status": "PENDING",
                            "claimed_at": None,
                            "completed_at": None,
                            "result": {},
                        }
                    )
                    .eq("id", command_id)
                    .eq("status", "CLAIMED")
                    .lt("claimed_at", cutoff)
                    .execute()
                )
            except Exception as exc:
                raise SupabaseBridgeError(
                    f"Falha ao recuperar comando abandonado {command_id}: {exc}"
                ) from exc
            if result.data:
                recovered.append(str(command_id))
        return recovered

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

    def update_campaign_editorial(
        self,
        campaign_id: str,
        status: str,
        *,
        approved_by: str = "",
        feedback: str = "",
    ) -> None:
        """Registra decisão editorial executada pelo worker Linux."""
        if status not in {"APROVADA", "REJEITADA", "AJUSTE_SOLICITADO"}:
            raise SupabaseBridgeError("Status editorial inválido.")
        campaign_id = self._validate_campaign_id(campaign_id)
        payload: dict[str, Any] = {
            "status": status,
            "mensagem_erro": _clean(feedback, 1000),
            "atualizado_em": _now(),
        }
        if status == "APROVADA":
            payload["aprovado_por"] = approved_by or None
            payload["data_aprovacao"] = _now()
        try:
            self.client.table("mkt_campaigns").update(payload).eq(
                "campaign_id", campaign_id
            ).execute()
        except Exception as exc:
            raise SupabaseBridgeError(
                f"Falha ao registrar decisão editorial {campaign_id}: {exc}"
            ) from exc

    @staticmethod
    def _validate_creation_config(config: dict[str, Any]) -> dict[str, Any]:
        """Valida e limita a configuração antes de colocá-la na fila."""
        if not isinstance(config, dict):
            raise SupabaseBridgeError("Configuração de campanha inválida.")
        required = {
            "publico_slug",
            "publico_id",
            "golpe_id",
            "midia",
            "canal",
            "objetivo",
        }
        missing = sorted(key for key in required if not config.get(key))
        if missing:
            raise SupabaseBridgeError(
                f"Configuração incompleta; campos ausentes: {', '.join(missing)}."
            )
        publico_slug = _clean(config["publico_slug"], 40).lower()
        golpe_id = _clean(config["golpe_id"], 60).lower()
        if publico_slug not in CREATION_PUBLICS:
            raise SupabaseBridgeError("Público-alvo inválido.")
        if golpe_id not in CREATION_SCAMS:
            raise SupabaseBridgeError("Tipo de golpe inválido.")
        allowed_keys = {
            "publico",
            "publico_id",
            "publico_slug",
            "golpe",
            "golpe_id",
            "midia",
            "canal",
            "preset_midia",
            "preset_metadata",
            "objetivo",
            "aprovacao_telegram",
            "aprovacao_terminal",
            "aprovacao_desktop",
            "postar_instagram",
        }
        sanitized: dict[str, Any] = {
            key: value for key, value in config.items() if key in allowed_keys
        }
        for key in (
            "publico",
            "publico_id",
            "golpe",
            "midia",
            "canal",
            "objetivo",
        ):
            sanitized[key] = _clean(sanitized.get(key), 160)
        sanitized["publico_slug"] = publico_slug
        sanitized["golpe_id"] = golpe_id
        for key in (
            "aprovacao_telegram",
            "aprovacao_terminal",
            "aprovacao_desktop",
            "postar_instagram",
        ):
            sanitized[key] = bool(config.get(key, False))
        if not any(
            sanitized[key]
            for key in ("aprovacao_telegram", "aprovacao_terminal", "aprovacao_desktop")
        ):
            sanitized["aprovacao_desktop"] = True
        if isinstance(config.get("preset_midia"), dict):
            sanitized["preset_midia"] = config["preset_midia"]
        if isinstance(config.get("preset_metadata"), dict):
            sanitized["preset_metadata"] = config["preset_metadata"]
        return sanitized

    def create_campaign_request(
        self,
        config: dict[str, Any],
        *,
        source: str,
        requested_by: str = "",
        requester_label: str = "",
    ) -> dict[str, Any]:
        """Coloca uma nova campanha na fila para o worker Linux gerar."""
        source = _clean(source, 20).upper()
        if source not in CREATION_SOURCES:
            raise SupabaseBridgeError("Origem da solicitação inválida.")
        payload: dict[str, Any] = {
            "source": source,
            "requested_by": _clean(requested_by, 120) or None,
            "requester_label": _clean(requester_label, 160),
            "config": self._validate_creation_config(config),
        }
        try:
            response = (
                self.client.table("mkt_campaign_creation_requests")
                .insert(payload)
                .execute()
            )
        except Exception as exc:
            raise SupabaseBridgeError(
                f"Falha ao enfileirar criação da campanha: {exc}"
            ) from exc
        return (response.data or [payload])[0]

    def claim_pending_creation_requests(self, limit: int = 5) -> list[dict[str, Any]]:
        """Reivindica solicitações de criação sem permitir execução duplicada."""
        bounded_limit = max(1, min(int(limit), 20))
        try:
            response = (
                self.client.table("mkt_campaign_creation_requests")
                .select("*")
                .eq("status", "PENDING")
                .order("created_at")
                .limit(bounded_limit)
                .execute()
            )
        except Exception as exc:
            raise SupabaseBridgeError(
                f"Falha ao consultar solicitações de criação: {exc}"
            ) from exc
        claimed: list[dict[str, Any]] = []
        for request in response.data or []:
            request_id = request.get("id")
            if not request_id:
                continue
            try:
                result = (
                    self.client.table("mkt_campaign_creation_requests")
                    .update({"status": "CLAIMED", "claimed_at": _now()})
                    .eq("id", request_id)
                    .eq("status", "PENDING")
                    .execute()
                )
            except Exception as exc:
                raise SupabaseBridgeError(
                    f"Falha ao reivindicar criação {request_id}: {exc}"
                ) from exc
            if result.data:
                claimed.append({**request, "status": "CLAIMED"})
        return claimed

    def recover_stale_creation_requests(
        self,
        *,
        stale_after_seconds: int = 1800,
        limit: int = 20,
    ) -> list[str]:
        """Recoloca na fila criações abandonadas por um worker interrompido."""
        bounded_limit = max(1, min(int(limit), 50))
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(seconds=max(60, int(stale_after_seconds)))
        ).isoformat()
        try:
            response = (
                self.client.table("mkt_campaign_creation_requests")
                .select("id")
                .eq("status", "CLAIMED")
                .lt("claimed_at", cutoff)
                .order("claimed_at")
                .limit(bounded_limit)
                .execute()
            )
        except Exception as exc:
            raise SupabaseBridgeError(
                f"Falha ao localizar criações abandonadas: {exc}"
            ) from exc
        recovered: list[str] = []
        for request in response.data or []:
            request_id = request.get("id")
            if not request_id:
                continue
            result = (
                self.client.table("mkt_campaign_creation_requests")
                .update(
                    {
                        "status": "PENDING",
                        "claimed_at": None,
                        "completed_at": None,
                        "result": {},
                        "error_message": "",
                    }
                )
                .eq("id", request_id)
                .eq("status", "CLAIMED")
                .lt("claimed_at", cutoff)
                .execute()
            )
            if result.data:
                recovered.append(str(request_id))
        return recovered

    def complete_campaign_request(
        self,
        request_id: str,
        *,
        success: bool,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        """Finaliza uma solicitação sem persistir respostas brutas ou segredos."""
        safe_result = {
            key: value
            for key, value in (result or {}).items()
            if key in {"campaign_id", "status", "version", "provider", "qa_score"}
        }
        payload = {
            "status": "SUCCEEDED" if success else "FAILED",
            "result": safe_result,
            "error_message": _clean(error, 1000),
            "completed_at": _now(),
        }
        try:
            self.client.table("mkt_campaign_creation_requests").update(payload).eq(
                "id", _clean(request_id, 100)
            ).eq("status", "CLAIMED").execute()
        except Exception as exc:
            raise SupabaseBridgeError(
                f"Falha ao finalizar criação {request_id}: {exc}"
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
                "version",
                "provider",
                "qa_score",
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
