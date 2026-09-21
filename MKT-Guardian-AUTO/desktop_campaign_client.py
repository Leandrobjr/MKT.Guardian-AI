"""Cliente seguro para o Desktop consultar campanhas e solicitar publicação.

Este módulo usa somente a chave publishable/anon e depende de uma sessão
Supabase autenticada. Nunca use SUPABASE_SERVICE_ROLE_KEY neste cliente.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

from env_loader import load_project_env

CAMPAIGN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
PUBLISHABLE_STATUSES = {"APROVADA", "PRONTA_PARA_PUBLICAR", "ERRO_PUBLICACAO"}
EDITORIAL_ACTIONS = {
    "approve": "APPROVE",
    "reject": "REJECT",
    "request_revision": "REQUEST_REVISION",
}


class DesktopCampaignClientError(RuntimeError):
    """Erro seguro da camada de integração do Desktop."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DesktopCampaignClient:
    """Cliente de leitura/aprovação; não publica e não grava assets."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        bucket: str | None = None,
    ):
        load_project_env()
        self.bucket = bucket or os.getenv(
            "SUPABASE_CAMPAIGN_BUCKET", "mkt-campaign-assets"
        )
        self.client = client or self._build_client()

    @staticmethod
    def _build_client() -> Any:
        url = os.getenv("SUPABASE_URL", "").strip()
        publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
        if not url or not publishable_key:
            raise DesktopCampaignClientError(
                "O Desktop exige SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY. "
                "Nunca configure SUPABASE_SERVICE_ROLE_KEY no cliente."
            )
        try:
            from supabase import create_client
        except ImportError as exc:
            raise DesktopCampaignClientError(
                "Dependência supabase não instalada. Instale requirements.txt."
            ) from exc
        return create_client(url, publishable_key)

    @staticmethod
    def _validate_campaign_id(campaign_id: str) -> str:
        if not CAMPAIGN_ID_PATTERN.fullmatch(str(campaign_id or "")):
            raise DesktopCampaignClientError("campaign_id inválido.")
        return str(campaign_id)

    def current_user_id(self) -> str:
        """Retorna o usuário autenticado; RLS valida se ele é ADMIN ativo."""
        try:
            response = self.client.auth.get_user()
            raw_response = response if isinstance(response, dict) else {}
            user = getattr(response, "user", None) or raw_response.get("user")
            raw_user = user if isinstance(user, dict) else {}
            user_id = getattr(user, "id", None) or raw_user.get("id")
        except Exception as exc:
            raise DesktopCampaignClientError(
                f"Sessão Supabase inválida ou expirada: {exc}"
            ) from exc
        if not user_id:
            raise DesktopCampaignClientError(
                "Faça login no Supabase antes de solicitar publicação."
            )
        return str(user_id)

    def list_campaigns(
        self, *, status: str = "", limit: int = 50
    ) -> list[dict[str, Any]]:
        """Lista somente campos necessários para a tela de campanhas."""
        bounded_limit = max(1, min(int(limit), 100))
        try:
            query = (
                self.client.table("mkt_campaigns")
                .select(
                    "campaign_id,version,status,publico,golpe,canal,midia,"
                    "basename,storage_bucket,storage_path,legenda,roteiro,preset,"
                    "metadata,plataforma,id_retornado,mensagem_erro,"
                    "data_criacao,data_aprovacao,data_publicacao,atualizado_em"
                )
            )
            if status:
                query = query.eq("status", status)
            response = query.order("atualizado_em", desc=True).limit(
                bounded_limit
            ).execute()
        except Exception as exc:
            raise DesktopCampaignClientError(
                f"Não foi possível carregar campanhas: {exc}"
            ) from exc
        return response.data or []

    def list_commands(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Lista comandos e seus estados sem expor qualquer token."""
        bounded_limit = max(1, min(int(limit), 100))
        try:
            response = (
                self.client.table("mkt_campaign_commands")
                .select(
                    "id,campaign_id,action,status,requested_by,payload,result,"
                    "created_at,claimed_at,completed_at"
                )
                .order("created_at", desc=True)
                .limit(bounded_limit)
                .execute()
            )
        except Exception as exc:
            raise DesktopCampaignClientError(
                f"Não foi possível carregar comandos: {exc}"
            ) from exc
        return response.data or []

    def request_editorial_decision(
        self,
        campaign_id: str,
        decision: str,
        *,
        feedback: str = "",
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """Enfileira aprovação editorial sem alterar status no navegador."""
        if not confirmed:
            raise DesktopCampaignClientError(
                "A decisão editorial exige confirmação explícita no Desktop."
            )
        action = EDITORIAL_ACTIONS.get(str(decision or "").lower())
        if not action:
            raise DesktopCampaignClientError("Decisão editorial inválida.")
        if action == "REQUEST_REVISION" and not str(feedback or "").strip():
            raise DesktopCampaignClientError(
                "Solicitação de ajuste exige um motivo."
            )
        campaign_id = self._validate_campaign_id(campaign_id)
        campaigns = self.list_campaigns(limit=100)
        campaign = next(
            (item for item in campaigns if item.get("campaign_id") == campaign_id),
            None,
        )
        if not campaign:
            raise DesktopCampaignClientError("Campanha não encontrada ou sem acesso.")
        if campaign.get("status") != "AGUARDANDO_APROVACAO_FINAL":
            raise DesktopCampaignClientError(
                "A campanha não está aguardando aprovação editorial."
            )
        user_id = self.current_user_id()
        payload = {
            "campaign_id": campaign_id,
            "action": action,
            "requested_by": user_id,
            "payload": {
                "confirmed": True,
                "confirmed_at": _now(),
                "version": campaign.get("version", 0),
                "feedback": str(feedback or "").strip()[:1000],
            },
        }
        try:
            response = (
                self.client.table("mkt_campaign_commands")
                .insert(payload)
                .execute()
            )
        except Exception as exc:
            raise DesktopCampaignClientError(
                "Não foi possível registrar a decisão editorial. "
                "Verifique se já existe um comando pendente."
            ) from exc
        return (response.data or [payload])[0]

    def request_publication(
        self, campaign_id: str, *, confirmed: bool = False
    ) -> dict[str, Any]:
        """Cria comando PUBLISH somente após confirmação explícita do usuário."""
        if not confirmed:
            raise DesktopCampaignClientError(
                "A publicação exige confirmação explícita no Desktop."
            )
        campaign_id = self._validate_campaign_id(campaign_id)
        campaigns = self.list_campaigns(limit=100)
        campaign = next(
            (item for item in campaigns if item.get("campaign_id") == campaign_id),
            None,
        )
        if not campaign:
            raise DesktopCampaignClientError("Campanha não encontrada ou sem acesso.")
        if campaign.get("status") == "PUBLICADA":
            raise DesktopCampaignClientError("Campanha já publicada.")
        if campaign.get("status") not in PUBLISHABLE_STATUSES:
            raise DesktopCampaignClientError(
                f"Campanha não está pronta: {campaign.get('status', '')}."
            )
        if "tiktok" in str(campaign.get("canal") or "").lower():
            raise DesktopCampaignClientError(
                "TikTok exige o fluxo de upload manual; não crie comando automático."
            )

        user_id = self.current_user_id()
        payload = {
            "campaign_id": campaign_id,
            "action": "PUBLISH",
            "requested_by": user_id,
            "payload": {"confirmed": True, "confirmed_at": _now()},
        }
        try:
            response = (
                self.client.table("mkt_campaign_commands")
                .insert(payload)
                .execute()
            )
        except Exception as exc:
            raise DesktopCampaignClientError(
                "Não foi possível criar o comando. "
                "Verifique se já existe uma publicação pendente."
            ) from exc
        return (response.data or [payload])[0]

    def create_asset_url(
        self, campaign_id: str, *, expires_in: int = 300
    ) -> str:
        """Gera URL temporária para o asset privado, sem expor caminho local."""
        campaign_id = self._validate_campaign_id(campaign_id)
        campaigns = self.list_campaigns(limit=100)
        campaign = next(
            (item for item in campaigns if item.get("campaign_id") == campaign_id),
            None,
        )
        if not campaign or not campaign.get("storage_path"):
            raise DesktopCampaignClientError("Asset não disponível.")
        seconds = max(60, min(int(expires_in), 900))
        try:
            response = self.client.storage.from_(
                campaign.get("storage_bucket") or self.bucket
            ).create_signed_url(campaign["storage_path"], seconds)
        except Exception as exc:
            raise DesktopCampaignClientError(
                "Não foi possível gerar a visualização temporária."
            ) from exc
        url = (
            response.get("signedURL")
            if isinstance(response, dict)
            else getattr(response, "signedURL", "")
        )
        if not url:
            raise DesktopCampaignClientError("Supabase não retornou URL temporária.")
        return str(url)
