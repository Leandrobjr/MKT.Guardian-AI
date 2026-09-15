"""Presets de canal/mídia — duração de copy, voz, trilha e formato de saída."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from composition_templates import get_composition_template


def _is_video_midia(midia: str) -> bool:
    m = (midia or "").lower()
    return "vídeo" in m or "video" in m or "animado" in m


def is_video_media(midia: str) -> bool:
    """Indica se a mídia selecionada exige um asset de vídeo."""
    return _is_video_midia(midia)


def _is_meta_canal(canal: str) -> bool:
    value = (canal or "").lower()
    return any(token in value for token in ("meta", "instagram", "facebook", "feed", "reels"))


def _is_short_canal(canal: str) -> bool:
    value = (canal or "").lower()
    return any(token in value for token in ("tiktok", "youtube", "shorts"))


@dataclass(frozen=True)
class ChannelMediaValidation:
    valid: bool
    errors: tuple[str, ...]
    preset: dict
    metadata: dict

    def to_dict(self) -> dict:
        return asdict(self)


def _preset_metadata(preset: dict) -> dict:
    width = preset.get("width", 1080)
    height = preset.get("height", 1080)
    template = preset.get("composition_template") or {}
    return {
        "preset_id": preset.get("preset_id", ""),
        "template_id": template.get("template_id", ""),
        "area_segura": template.get("safe_area", []),
        "posicao_logo": template.get("logo_anchor", ""),
        "animacao_composicao": template.get("animation", ""),
        "resolucao": f"{width}x{height}",
        "proporcao": preset.get("aspect_ratio", ""),
        "duracao_copy": preset.get("copy_duration", ""),
        "duracao_alvo_segundos": preset.get("target_narration_seconds"),
        "ritmo": (
            "rápido e urgente"
            if preset.get("preset_id") == "shorts_urgente"
            else "pausado e focado em leitura"
        ),
        "tipo_trilha": preset.get("trilha_tipo", ""),
        "velocidade_narracao": preset.get("eleven_speed"),
    }


def _attach_composition_template(preset: dict) -> dict:
    preset["composition_template"] = get_composition_template(
        preset.get("preset_id", "")
    ).to_dict()
    return preset


def validate_channel_media(canal: str, midia: str) -> ChannelMediaValidation:
    """Valida combinação antes de consumir Gemini, Kling ou ElevenLabs."""
    media_video = _is_video_midia(midia)
    media_label = "vídeo vertical" if media_video else "imagem quadrada"
    errors: list[str] = []
    is_meta = _is_meta_canal(canal)
    is_short = _is_short_canal(canal)

    if not str(canal or "").strip():
        errors.append("O canal de distribuição é obrigatório.")
    elif not is_meta and not is_short:
        errors.append(
            f"Canal não suportado para {media_label}. Use Meta Ads ou TikTok/YouTube Shorts."
        )
    elif not media_video and not is_meta:
        errors.append(
            "Imagem estática quadrada só pode ser usada no Feed do Instagram/Facebook (Meta Ads)."
        )
    elif media_video and not (is_meta or is_short):
        errors.append(
            "Vídeo vertical só pode ser usado em Reels/Stories da Meta ou TikTok/YouTube Shorts."
        )

    preset = resolve_channel_preset(canal, midia)
    return ChannelMediaValidation(
        valid=not errors,
        errors=tuple(errors),
        preset=preset,
        metadata=_preset_metadata(preset),
    )


def resolve_channel_preset(canal: str, midia: str) -> dict:
    """Retorna preset técnico conforme canal e tipo de mídia."""
    if not _is_video_midia(midia):
        return _attach_composition_template({
            "preset_id": "feed_quadrado",
            "label": "Feed Instagram/Facebook 1:1",
            "width": 1080,
            "height": 1080,
            "aspect_ratio": "1:1",
            "visual_ratio_hint": "Square 1:1 composition, subject centered for Instagram/Facebook feed.",
            "copy_duration": "18-24 segundos de narração (copy mais curta para imagem estática).",
            "copy_tone": "Tom claro e direto, frases médias, foco em leitura no feed.",
            "eleven_speed": 0.92,
            "eleven_stability": 0.60,
            "eleven_style": 0.35,
            "trilha_tipo": "corporativo",
            "voice_volume": "1.35",
            "track_volume_db": "-10dB",
            "track_weight": "0.30",
            "kling_duration": 5,
            "kling_resolution": "720p",
        })

    if _is_meta_canal(canal):
        return _attach_composition_template({
            "preset_id": "meta_reels",
            "label": "Meta Ads — Reels/Stories (pausado, leitura)",
            "width": 1080,
            "height": 1920,
            "aspect_ratio": "9:16",
            "visual_ratio_hint": "Vertical 9:16 composition for Instagram/Facebook Reels.",
            "copy_duration": "25-35 segundos de narração. Copy mais longa e explicativa.",
            "copy_tone": (
                "Tom pausado, confiável, focado em leitura. Frases completas. "
                "Evite gírias agressivas. Priorize clareza para público 35+."
            ),
            "eleven_speed": 0.88,
            "eleven_stability": 0.60,
            "eleven_style": 0.28,
            "trilha_tipo": "corporativo",
            "voice_volume": "1.40",
            "track_volume_db": "-10dB",
            "track_weight": "0.30",
            "kling_duration": 10,
            "kling_resolution": "720p",
            "copy_max_chars": 520,
            "target_narration_seconds": 32,
            "video_slowdown": 1.35,
        })

    return _attach_composition_template({
        "preset_id": "shorts_urgente",
        "label": "TikTok / YouTube Shorts (rápido, urgente)",
        "width": 1080,
        "height": 1920,
        "aspect_ratio": "9:16",
        "visual_ratio_hint": "Vertical 9:16 dynamic composition for TikTok/Shorts, energetic framing.",
        "copy_duration": "12-18 segundos de narração. Copy curta e impactante.",
        "copy_tone": (
            "Tom urgente, ritmo acelerado, frases curtas e punchy. "
            "Máximo 3 frases no roteiro. Ganchos fortes nos primeiros 3 segundos."
        ),
        "eleven_speed": 1.0,
        "eleven_stability": 0.60,
        "eleven_style": 0.50,
        "trilha_tipo": "suspense",
        "voice_volume": "1.50",
        "track_volume_db": "-5dB",
        "track_weight": "0.50",
        "kling_duration": 5,
        "kling_resolution": "720p",
        "copy_max_chars": 250,
        "target_narration_seconds": 18,
        "auto_fit_narration": True,
        "max_audio_speedup": 1.25,
        "video_slowdown": 1.45,
    })


def format_preset_summary(preset: dict) -> str:
    alvo = preset.get("target_narration_seconds")
    alvo_txt = f" | alvo ~{alvo}s" if alvo else ""
    return (
        f"{preset['label']} | {preset['width']}x{preset['height']} | "
        f"narração {preset['eleven_speed']}x | trilha {preset['trilha_tipo']}{alvo_txt}"
    )
