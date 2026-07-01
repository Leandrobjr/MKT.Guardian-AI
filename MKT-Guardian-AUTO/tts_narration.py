"""Montagem do roteiro TTS — sem URL falada; fechamento visual via card."""

from __future__ import annotations

import re

NARRATION_CLOSING = "Clique no link abaixo e assine agora"
# Texto fixo no card 2 — não depende do Gemini, nunca diz "bloqueou"
CARD_SOLUCAO_PADRAO = "Guardian AI detectou ameaça e enviou um ALERTA imediato ao usuário!"
CTA_OVERLAY_FALLBACK = "TESTE GRÁTIS — PROTEJA SEU WHATSAPP AGORA!"


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


def _fix_app_name_pronunciation(text: str) -> str:
    """Força ElevenLabs a pronunciar 'Guardian AI' em inglês (A.I. = duas letras)."""
    import re as _re
    return _re.sub(r"Guardian\s+AI\b", "Guardian A.I.", text, flags=_re.IGNORECASE)


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
    4. Corrige pronúncia do nome do app para inglês
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

    script = f"{core}. {closing}."
    return _fix_app_name_pronunciation(script)


def card_solucao_text() -> str:
    """Sempre o mesmo texto no card Guardian — capacidade real do produto."""
    return CARD_SOLUCAO_PADRAO


def normalize_card_solucao(text: str) -> str:
    return card_solucao_text()


def resolve_overlay_cta(creative_data: dict) -> str:
    """Botão verde inferior: usa texto_botao_conversao (ICP), nunca CTA genérico do Gemini."""
    cta = (creative_data.get("texto_botao_conversao") or "").strip()
    if cta:
        return cta
    return CTA_OVERLAY_FALLBACK
