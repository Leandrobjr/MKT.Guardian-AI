"""Montagem do roteiro TTS — sem URL falada; fechamento visual via card."""

from __future__ import annotations

import re

NARRATION_CLOSING = "Clique no link abaixo e assine agora!"
CARD_SOLUCAO_PADRAO = "Guardian AI detectou e enviou um ALERTA imediato ao usuário!"


def strip_written_site_urls(text: str, domain: str = "guardian-ai.app") -> str:
    """Remove URLs/domínio do texto — conversão fica no card visual."""
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
        r"visite\s+[^.]*\.?\s*$",
        r"clique\s+em\s+[^.]*\.?\s*$",
    ]
    result = text
    for pat in patterns:
        result = re.sub(pat, "", result, flags=re.IGNORECASE)
    result = re.sub(r"\s{2,}", " ", result)
    return result.strip(" .,;")


def build_narration_script(
    headline: str,
    body: str,
    trim_fn,
    preset: dict,
    closing: str = NARRATION_CLOSING,
) -> str:
    """
    Monta roteiro para TTS:
    1. Remove URL escrita do corpo (marca Guardian AI permanece intacta)
    2. Trunca corpo reservando espaço para o fechamento fixo
    3. Fecha com convite ao link no card — sem soletrar domínio
    """
    body_clean = strip_written_site_urls(body or "")
    headline = (headline or "").strip()
    core = f"{headline}. {body_clean}".strip() if headline else body_clean
    core = re.sub(r"\s+", " ", core).strip(" .,;")

    reserved = len(f" {closing}.")
    preset_copy = dict(preset)
    max_chars = preset_copy.get("copy_max_chars")
    if max_chars and len(core) + reserved > int(max_chars):
        preset_copy["copy_max_chars"] = max(80, int(max_chars) - reserved)

    core = trim_fn(core, preset_copy)
    core = core.rstrip(" .,;")
    core = re.sub(
        r"(?i)\s*(baixe|acesse|visite|download|clique)[^.]*$",
        "",
        core,
    ).rstrip(" .,;")

    return f"{core}. {closing}."


def card_solucao_needs_fix(text: str) -> bool:
    """True se o card implica bloqueio — capacidade que o app não tem."""
    if not text:
        return True
    lower = text.lower()
    return any(w in lower for w in ("bloque", "impede", "intercept", "barra ", "cancela a mensagem"))


def normalize_card_solucao(text: str) -> str:
    if card_solucao_needs_fix(text):
        return CARD_SOLUCAO_PADRAO
    return text.strip()
