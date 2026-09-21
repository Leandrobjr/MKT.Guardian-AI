"""Roteamento de raciocínio multimodal via OpenCode com fallback Gemini."""

from __future__ import annotations

import base64
import os
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

import requests

from env_loader import load_project_env


@dataclass(frozen=True)
class AIResponse:
    text: str
    provider: str
    model: str


class OpenCodeClientError(RuntimeError):
    """Falha segura ao consultar o provedor OpenCode."""


class OpenCodeClient:
    """Cliente OpenAI-compatible para modelos DeepSeek hospedados no OpenCode."""

    def __init__(self) -> None:
        load_project_env()
        self.api_key = os.getenv("OPENCODE_API_KEY", "").strip()
        self.base_url = os.getenv(
            "OPENCODE_BASE_URL",
            "https://opencode.ai/zen/go/v1/chat/completions",
        ).strip()
        self.model = os.getenv(
            "OPENCODE_MODEL",
            "deepseek-v4-flash-vision-exp",
        ).strip()
        self.session_id = os.getenv("OPENCODE_SESSION_ID", "").strip() or uuid.uuid4().hex
        self.timeout = max(
            10,
            min(int(os.getenv("OPENCODE_TIMEOUT_SECONDS", "60")), 180),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    @staticmethod
    def _content_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict)
            )
        return ""

    def complete(
        self,
        prompt: str,
        *,
        system_instruction: str = "",
        images: Iterable[tuple[bytes, str]] = (),
    ) -> AIResponse:
        if not self.enabled:
            raise OpenCodeClientError("OpenCode não configurado.")
        if not self.base_url.startswith("https://"):
            raise OpenCodeClientError("OPENCODE_BASE_URL deve usar HTTPS.")

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for data, mime_type in images:
            encoded = base64.b64encode(data).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{encoded}",
                    },
                }
            )
        messages: list[dict[str, Any]] = []
        if system_instruction.strip():
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": content})

        try:
            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "x-opencode-session": self.session_id,
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.0,
                    "stream": False,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            choices = payload.get("choices") or []
            message = choices[0].get("message") if choices else {}
            text = self._content_text((message or {}).get("content"))
        except (OSError, ValueError, requests.RequestException) as exc:
            raise OpenCodeClientError(f"Falha na chamada OpenCode: {exc}") from exc

        if not text.strip():
            raise OpenCodeClientError("OpenCode retornou resposta vazia.")
        return AIResponse(text=text, provider="opencode", model=self.model)


class HybridAIClient:
    """Usa OpenCode/DeepSeek primeiro e Gemini como fallback controlado."""

    def __init__(
        self,
        gemini_client: Any,
        *,
        gemini_text_model: str,
        gemini_vision_model: str,
        opencode_client: OpenCodeClient | None = None,
    ) -> None:
        self.gemini_client = gemini_client
        self.gemini_text_model = gemini_text_model
        self.gemini_vision_model = gemini_vision_model
        self.opencode = opencode_client or OpenCodeClient()
        self.last_provider = ""

    def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: str = "",
        fallback_config: Any = None,
        force_gemini: bool = False,
    ) -> AIResponse:
        if self.opencode.enabled and not force_gemini:
            try:
                result = self.opencode.complete(
                    prompt,
                    system_instruction=system_instruction,
                )
                self.last_provider = result.provider
                return result
            except OpenCodeClientError:
                pass

        response = self.gemini_client.models.generate_content(
            model=self.gemini_text_model,
            contents=prompt,
            config=fallback_config,
        )
        result = AIResponse(
            text=getattr(response, "text", "") or "",
            provider="gemini",
            model=self.gemini_text_model,
        )
        self.last_provider = result.provider
        return result

    def generate_vision(
        self,
        prompt: str,
        media_files: Iterable[tuple[bytes, str]],
        *,
        force_gemini: bool = False,
    ) -> AIResponse:
        if self.opencode.enabled and not force_gemini:
            try:
                result = self.opencode.complete(prompt, images=media_files)
                self.last_provider = result.provider
                return result
            except OpenCodeClientError:
                pass

        from google.genai import types

        parts = [
            types.Part.from_bytes(data=data, mime_type=mime_type)
            for data, mime_type in media_files
        ]
        response = self.gemini_client.models.generate_content(
            model=self.gemini_vision_model,
            contents=[prompt, *parts],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        result = AIResponse(
            text=getattr(response, "text", "") or "",
            provider="gemini",
            model=self.gemini_vision_model,
        )
        self.last_provider = result.provider
        return result
