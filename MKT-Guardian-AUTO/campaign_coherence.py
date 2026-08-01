"""Coerência narrativa — card, roteiro, headline e variante do golpe alinhados."""

from __future__ import annotations

import re
import unicodedata

THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fornecedor_cadastro": (
        "fornecedor", "fornecedores", "cadastro", "atualiz", "cnpj", "cadastral",
    ),
    "brinde_premio": (
        "brinde", "prêmio", "premio", "selecionado", "resgatar", "sorteio", "parabéns", "parabens",
    ),
    "encomenda": (
        "encomenda", "entrega", "retida", "correios", "rastreio", "rastreamento", "pacote",
    ),
    "apk_seguranca": (
        "apk", "aplicativo", "instal", "segurança", "seguranca", "atualização do whats",
    ),
    "cliente_comercial": (
        "cliente", "pedido", "comprovante", "business", "loja", "comerciante",
    ),
    "grooming": (
        "foto", "segredo", "bonit", "menor", "filho", "filha", "predador",
    ),
    "pix": ("pix", "transfer", "pagamento", "boleto", "qr code"),
}


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def detect_themes(text: str) -> set[str]:
    t = _norm(text)
    found: set[str] = set()
    for theme, keywords in THEME_KEYWORDS.items():
        if any(k in t for k in keywords):
            found.add(theme)
    return found or {"generico"}


def theme_overlap(a: str, b: str) -> float:
    ta, tb = detect_themes(a), detect_themes(b)
    if "generico" in ta or "generico" in tb:
        return 0.5
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def keyword_overlap(roteiro: str, frase: str) -> float:
    words_frase = {w for w in re.findall(r"[\wÀ-ÿ]{4,}", _norm(frase))}
    words_roteiro = {w for w in re.findall(r"[\wÀ-ÿ]{4,}", _norm(roteiro))}
    if not words_frase:
        return 1.0
    hits = len(words_frase & words_roteiro)
    return hits / max(len(words_frase), 1)


def nexo_score(roteiro: str, frase: str, headline: str = "") -> float:
    """0–1 — quanto roteiro/headline compartilham o mesmo 'golpe' da frase do card."""
    if not frase or not roteiro:
        return 0.0
    theme = theme_overlap(roteiro, frase)
    kw = keyword_overlap(roteiro, frase)
    head = theme_overlap(headline, frase) if headline else 0.5
    return theme * 0.45 + kw * 0.35 + head * 0.20


def is_coherent(roteiro: str, frase: str, headline: str = "", min_score: float = 0.35) -> bool:
    return nexo_score(roteiro, frase, headline) >= min_score


def pick_coherent_gancho(ganchos: list[str], frase: str, start_idx: int = 0) -> tuple[str | None, int]:
    """Escolhe gancho com melhor nexo com a frase_golpista (rotação como desempate)."""
    if not ganchos:
        return None, -1
    scored: list[tuple[float, int, str]] = []
    for i, g in enumerate(ganchos):
        score = nexo_score(g, frase, g)
        rot_bonus = -((i - start_idx) % len(ganchos)) * 0.01
        scored.append((score + rot_bonus, i, g))
    scored.sort(key=lambda x: (-x[0], x[1]))
    _, idx, gancho = scored[0]
    return gancho, idx


def format_nexo_prompt_block(frase: str, variant_titulo: str = "") -> str:
    titulo = variant_titulo or "golpe selecionado"
    return (
        "COERÊNCIA OBRIGATÓRIA DA CAMPANHA (NEXO — NÃO VIOLAR):\n"
        f"- Variante do golpe: {titulo}\n"
        f"- A mensagem EXATA do golpista no WhatsApp (card) será:\n"
        f'  «{frase.strip()}»\n'
        "- O roteiro (desenvolvimento_copy) DEVE contar a história DESTE mesmo golpe — "
        "mesmo pretexto, mesma isca (cadastro OU brinde OU encomenda — nunca misturar).\n"
        "- A manchete (gancho_atencao_inicial) DEVE refletir o MESMO pretexto da frase acima.\n"
        "- PROIBIDO: roteiro sobre 'atualização de cadastro de fornecedor' com card sobre "
        "'prêmio/brinde/resgatar', ou vice-versa.\n"
        "- texto_card_notificacao: copie a frase acima com no máximo ajuste informal mínimo.\n"
    )
