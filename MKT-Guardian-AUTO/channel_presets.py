"""Presets de canal/mídia — duração de copy, voz, trilha e formato de saída."""

from __future__ import annotations


def _is_video_midia(midia: str) -> bool:
    m = (midia or "").lower()
    return "vídeo" in m or "video" in m or "animado" in m


def _is_meta_canal(canal: str) -> bool:
    return "meta" in (canal or "").lower()


def resolve_channel_preset(canal: str, midia: str) -> dict:
    """Retorna preset técnico conforme canal (Etapa 4) e tipo de mídia (Etapa 3)."""
    if not _is_video_midia(midia):
        return {
            "preset_id": "feed_quadrado",
            "label": "Feed Instagram/Facebook 1:1",
            "width": 1080,
            "height": 1080,
            "aspect_ratio": "1:1",
            "visual_ratio_hint": "Square 1:1 composition, subject centered for Instagram/Facebook feed.",
            "copy_duration": "18-24 segundos de narração (copy mais curta para imagem estática).",
            "copy_tone": "Tom claro e direto, frases médias, foco em leitura no feed.",
            "eleven_speed": 0.92,
            "eleven_stability": 0.50,
            "eleven_style": 0.35,
            "trilha_tipo": "corporativo",
            "voice_volume": "1.35",
            "track_volume_db": "-10dB",
            "track_weight": "0.30",
            "kling_duration": 5,
            "kling_resolution": "720p",
        }

    if _is_meta_canal(canal):
        return {
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
            "eleven_stability": 0.58,
            "eleven_style": 0.28,
            "trilha_tipo": "corporativo",
            "voice_volume": "1.40",
            "track_volume_db": "-10dB",
            "track_weight": "0.30",
            "kling_duration": 10,
            "kling_resolution": "720p",
        }

    return {
        "preset_id": "shorts_urgente",
        "label": "TikTok / YouTube Shorts (rápido, urgente)",
        "width": 1080,
        "height": 1920,
        "aspect_ratio": "9:16",
        "visual_ratio_hint": "Vertical 9:16 dynamic composition for TikTok/Shorts, energetic framing.",
        "copy_duration": "15-22 segundos de narração. Copy curta e impactante.",
        "copy_tone": (
            "Tom urgente, ritmo acelerado, frases curtas e punchy. "
            "Ganchos fortes nos primeiros 3 segundos. Linguagem direta estilo viral."
        ),
        "eleven_speed": 1.12,
        "eleven_stability": 0.32,
        "eleven_style": 0.62,
        "trilha_tipo": "suspense",
        "voice_volume": "1.55",
        "track_volume_db": "-4dB",
        "track_weight": "0.55",
        "kling_duration": 5,
        "kling_resolution": "720p",
    }


def format_preset_summary(preset: dict) -> str:
    return (
        f"{preset['label']} | {preset['width']}x{preset['height']} | "
        f"narração {preset['eleven_speed']}x | trilha {preset['trilha_tipo']}"
    )
