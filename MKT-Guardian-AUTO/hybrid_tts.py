"""Roteamento híbrido de TTS entre Google Chirp 3 HD e ElevenLabs."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any

import requests

CHIRP_ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
ELEVENLABS_ENDPOINT = "https://api.elevenlabs.io/v1/text-to-speech"
VALID_MODES = {"auto", "chirp", "elevenlabs"}
MIN_AUDIO_BYTES = 1000
MAX_AUDIO_BYTES = 20 * 1024 * 1024


class TTSProviderError(RuntimeError):
    """Erro seguro de configuração, autenticação ou síntese."""


@dataclass(frozen=True)
class TTSOutcome:
    output_path: str
    provider: str
    errors: tuple[str, ...] = ()


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _safe_error(response: Any, provider: str) -> str:
    if response.status_code in {401, 403}:
        return f"{provider}: credencial inválida ou sem permissão (HTTP {response.status_code})"
    if response.status_code == 429:
        return f"{provider}: limite ou saldo indisponível (HTTP 429)"
    try:
        body = response.json()
        detail = body.get("error") or body.get("detail") or body
        if isinstance(detail, dict):
            detail = detail.get("message") or detail.get("status") or detail
        message = str(detail)[:240]
    except Exception:
        message = str(getattr(response, "text", ""))[:240]
    return f"{provider}: HTTP {response.status_code} — {message}"


def _write_audio(path: str, content: bytes) -> None:
    if not MIN_AUDIO_BYTES < len(content) <= MAX_AUDIO_BYTES:
        raise TTSProviderError("resposta de áudio vazia ou fora do limite permitido")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temporary = f"{path}.tmp"
    try:
        with open(temporary, "wb") as file:
            file.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


class GoogleChirpProvider:
    name = "chirp"

    def __init__(
        self,
        api_key: str,
        voice: str = "pt-BR-Chirp3-HD-Aoede",
        *,
        session: Any = requests,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.voice = (voice or "pt-BR-Chirp3-HD-Aoede").strip()
        self.session = session

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def synthesize(self, text: str, output_path: str, _preset: dict) -> str:
        if not self.configured:
            raise TTSProviderError("Chirp: GOOGLE_CLOUD_TTS_API_KEY ausente")
        response = self.session.post(
            CHIRP_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
            },
            json={
                "input": {"text": text},
                "voice": {
                    "languageCode": "pt-BR",
                    "name": self.voice,
                },
                "audioConfig": {"audioEncoding": "MP3"},
            },
            timeout=120,
        )
        if response.status_code != 200:
            raise TTSProviderError(_safe_error(response, "Chirp"))
        try:
            encoded = response.json().get("audioContent") or ""
            if len(encoded) > (MAX_AUDIO_BYTES * 4 // 3) + 8:
                raise ValueError("resposta acima do limite")
            content = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise TTSProviderError("Chirp: resposta sem áudio válido") from exc
        _write_audio(output_path, content)
        return output_path


class ElevenLabsProvider:
    name = "elevenlabs"

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model_id: str = "eleven_multilingual_v2",
        *,
        session: Any = requests,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.voice_id = (voice_id or "").strip()
        self.model_id = (model_id or "eleven_multilingual_v2").strip()
        self.session = session

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.voice_id)

    def _request(self, text: str, preset: dict, include_speed: bool) -> Any:
        settings = {
            "stability": float(preset.get("eleven_stability", 0.4)),
            "similarity_boost": 0.9,
            "style": float(preset.get("eleven_style", 0.45)),
        }
        speed = float(preset.get("eleven_speed", 1.0))
        if include_speed and abs(speed - 1.0) > 0.01:
            settings["speed"] = speed
        return self.session.post(
            f"{ELEVENLABS_ENDPOINT}/{self.voice_id}",
            headers={
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key,
            },
            json={
                "text": text,
                "model_id": self.model_id,
                "voice_settings": settings,
            },
            timeout=120,
        )

    def synthesize(self, text: str, output_path: str, preset: dict) -> str:
        if not self.configured:
            raise TTSProviderError("ElevenLabs: credencial ou voice_id ausente")
        response = self._request(text, preset, include_speed=True)
        speed = float(preset.get("eleven_speed", 1.0))
        if response.status_code in {400, 422} and abs(speed - 1.0) > 0.01:
            response = self._request(text, preset, include_speed=False)
        if response.status_code != 200:
            raise TTSProviderError(_safe_error(response, "ElevenLabs"))
        _write_audio(output_path, response.content)
        return output_path


class HybridTTSRouter:
    """Seleciona o provedor por canal e tenta fallback sem duplicar áudio."""

    def __init__(
        self,
        chirp: GoogleChirpProvider,
        elevenlabs: ElevenLabsProvider,
        *,
        mode: str = "auto",
        fallback_enabled: bool = True,
        max_chars: int = 5000,
    ) -> None:
        normalized_mode = (mode or "auto").strip().lower()
        self.mode = normalized_mode if normalized_mode in VALID_MODES else "auto"
        self.fallback_enabled = fallback_enabled
        self.max_chars = max(1, min(int(max_chars), 5000))
        self.providers = {
            "chirp": chirp,
            "elevenlabs": elevenlabs,
        }

    @classmethod
    def from_env(cls, *, session: Any = requests) -> "HybridTTSRouter":
        eleven_key = (
            os.getenv("ELEVENLABS_API_KEY")
            or os.getenv("ELEVEN_LABS_API_KEY")
            or os.getenv("ELEVENLABS_KEY")
            or ""
        )
        eleven_voice = (
            os.getenv("ELEVENLABS_VOICE_ID")
            or os.getenv("ELEVEN_LABS_VOICE_ID")
            or "21m00Tcm4TlvDq8ikWAM"
        )
        return cls(
            GoogleChirpProvider(
                os.getenv("GOOGLE_CLOUD_TTS_API_KEY", ""),
                os.getenv("GOOGLE_CLOUD_TTS_VOICE", "pt-BR-Chirp3-HD-Aoede"),
                session=session,
            ),
            ElevenLabsProvider(
                eleven_key,
                eleven_voice,
                os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
                session=session,
            ),
            mode=os.getenv("AUDIO_TTS_MODE", "auto"),
            fallback_enabled=_env_bool("AUDIO_TTS_FALLBACK", True),
            max_chars=_env_int("AUDIO_TTS_MAX_CHARS", 5000),
        )

    def provider_order(self, preset: dict | None = None) -> tuple[str, ...]:
        if self.mode in {"chirp", "elevenlabs"}:
            primary = self.mode
        else:
            preset_id = str((preset or {}).get("preset_id") or "")
            primary = "elevenlabs" if preset_id == "shorts_urgente" else "chirp"
        secondary = "chirp" if primary == "elevenlabs" else "elevenlabs"
        return (primary, secondary) if self.fallback_enabled else (primary,)

    def synthesize(
        self,
        text: str,
        output_path: str,
        preset: dict | None = None,
    ) -> TTSOutcome:
        clean_text = str(text or "").strip()
        if not clean_text:
            return TTSOutcome(output_path, "", ("Narração vazia.",))
        if len(clean_text) > self.max_chars:
            return TTSOutcome(
                output_path,
                "",
                (f"Narração excede o limite seguro de {self.max_chars} caracteres.",),
            )

        errors: list[str] = []
        for name in self.provider_order(preset):
            provider = self.providers[name]
            if not provider.configured:
                errors.append(f"{name}: não configurado")
                continue
            try:
                provider.synthesize(clean_text, output_path, preset or {})
                return TTSOutcome(output_path, name, tuple(errors))
            except (OSError, requests.RequestException, TTSProviderError) as exc:
                errors.append(str(exc))
        return TTSOutcome(output_path, "", tuple(errors))
