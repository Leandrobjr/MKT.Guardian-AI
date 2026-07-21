"""
TikTok Publisher — stub para Content Posting API.

Tokens vêm do OAuth no site (https://guardian-ai.app/MKT-GUARDIAN-AUTO):
  TIKTOK_ACCESS_TOKEN, TIKTOK_REFRESH_TOKEN, TIKTOK_OPEN_ID

A publicação real (upload + publish) será ligada após aprovação no portal TikTok.
Por enquanto só valida configuração e expõe status.
"""

from __future__ import annotations

import os
from typing import Any

from env_loader import load_project_env

load_project_env()

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


def _env_redirect_uri() -> str:
    return (
        (os.getenv("TIKTOK_REDIRECT_URI") or os.getenv("TIKTOK_REDIRECT_URL") or "").strip()
    )


class TikTokPublisher:
    def __init__(self) -> None:
        self.client_key = (os.getenv("TIKTOK_CLIENT_KEY") or "").strip()
        self.client_secret = (os.getenv("TIKTOK_CLIENT_SECRET") or "").strip()
        self.access_token = (os.getenv("TIKTOK_ACCESS_TOKEN") or "").strip()
        self.refresh_token = (os.getenv("TIKTOK_REFRESH_TOKEN") or "").strip()
        self.open_id = (os.getenv("TIKTOK_OPEN_ID") or "").strip()
        self.redirect_uri = _env_redirect_uri()

        if not self.access_token:
            raise EnvironmentError(
                "TIKTOK_ACCESS_TOKEN ausente. Conecte a conta em "
                "https://guardian-ai.app/MKT-GUARDIAN-AUTO e cole os tokens no .env."
            )

    def status(self) -> dict[str, Any]:
        return {
            "configured": True,
            "open_id": self.open_id[:12] + "…" if self.open_id else "",
            "has_refresh": bool(self.refresh_token),
            "has_client_credentials": bool(self.client_key and self.client_secret),
            "publish_ready": False,
            "note": "OAuth ok — publish Content Posting API ainda não ligado neste stub.",
        }

    def publish_video(self, caminho_video: str, caption: str = "") -> dict[str, Any]:
        """Reservado: Direct Post / Upload da Content Posting API."""
        raise NotImplementedError(
            "Publicação TikTok ainda não implementada. "
            "Use status() após sincronizar tokens do portal web."
        )


def is_tiktok_env_ready() -> bool:
    return bool((os.getenv("TIKTOK_ACCESS_TOKEN") or "").strip())
