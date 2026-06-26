"""Montagem do roteiro TTS — pronúncia correta do site guardian-ai.app."""

from __future__ import annotations

import re

# Soletração estável para ElevenLabs (vírgulas = micro-pausas)
DEFAULT_URL_FALADA = "guardian traço a i ponto a, P, P"

_URL_PLACEHOLDER = "§§URL_FALADA§§"


def extract_url_falada_from_feedback(feedback: str, default: str = DEFAULT_URL_FALADA) -> str:
    """Interpreta pedido de correção de pronúncia no Telegram."""
    t = feedback.lower()
    if any(x in t for x in (".ap", "a p p", "a p. p", "soletr", "pronunc", "ponto a", "guardian traço")):
        return DEFAULT_URL_FALADA
    return default


def strip_written_site_urls(text: str, domain: str = "guardian-ai.app") -> str:
    """Remove URLs/domínio escritos — o site é falado no fechamento padronizado."""
    if not text:
        return text
    dom = re.escape(domain)
    patterns = [
        rf"https?://(?:www\.)?{dom}",
        rf"(?:www\.)?{dom}",
        r"guardian\s*[-]?\s*ai\s*\.\s*app",
        r"guardian\s+ai\s+app",
        rf"em\s+{dom}",
        rf"no\s+{dom}",
        r"baixe\s+gr[aá]tis\s+em\s+[^.]*\.?\s*$",
        r"acesse\s+[^.]*\.?\s*$",
    ]
    result = text
    for pat in patterns:
        result = re.sub(pat, "", result, flags=re.IGNORECASE)
    result = re.sub(r"\s{2,}", " ", result)
    return result.strip(" .,;")


def build_narration_script(
    headline: str,
    body: str,
    url_falada: str,
    trim_fn,
    preset: dict,
) -> str:
    """
    Monta roteiro para TTS:
    1. Remove URL escrita do corpo
    2. Trunca corpo (TikTok) sem cortar o fechamento
    3. Acrescenta fechamento fixo com soletração correta
    """
    body_clean = strip_written_site_urls(body or "")
    headline = (headline or "").strip()
    core = f"{headline}. {body_clean}".strip() if headline else body_clean
    core = re.sub(r"\s+", " ", core).strip(" .,;")

    reserved = len(f" Baixe grátis em {url_falada}.")
    preset_copy = dict(preset)
    max_chars = preset_copy.get("copy_max_chars")
    if max_chars and len(core) + reserved > int(max_chars):
        preset_copy["copy_max_chars"] = max(80, int(max_chars) - reserved)

    core = trim_fn(core, preset_copy)
    core = core.rstrip(" .,;")
    core = re.sub(
        r"(?i)\s*(baixe|acesse|visite|download)[^.]*$",
        "",
        core,
    ).rstrip(" .,;")

    return f"{core}. Baixe grátis em {url_falada}."
