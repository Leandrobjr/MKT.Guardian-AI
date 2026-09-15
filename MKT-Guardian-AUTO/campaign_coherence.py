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


def is_coherent_for_campaign(
    roteiro: str,
    frase: str,
    headline: str = "",
    canonical_type_id: str = "",
) -> bool:
    """Aplica nexo semântico específico quando a variante tem vocabulário variável."""
    if is_coherent(roteiro, frase, headline):
        return True
    if canonical_type_id == "voz_clonada":
        text = _norm(f"{roteiro} {frase} {headline}")
        has_voice_signal = any(
            term in text
            for term in ("voz clonada", "audio", "áudio", "imitando a voz", "deepfake")
        )
        has_pix_signal = any(term in text for term in ("pix", "dinheiro", "transfer"))
        return has_voice_signal and has_pix_signal
    if canonical_type_id != "falso_pix_familiar":
        return False
    text = _norm(f"{roteiro} {headline}")
    return (
        "pix" in text
        and "whatsapp" in text
        and any(term in text for term in ("pedir", "pedido", "enviar", "transfer"))
    )


def is_ambiguous_pix_headline(headline: str) -> bool:
    """Bloqueia headlines que atribuem à vítima a prática do golpe."""
    normalized = _norm(headline)
    return bool(
        re.search(
            r"\bpix\s+que\s+voce\s+fizer\b.*\b(pode\s+ser\s+um\s+golpe|cair\s+na\s+conta)\b",
            normalized,
        )
    )


def infer_recipient_gender(message: str) -> str:
    """Infere o gênero do protagonista pelo vocativo da mensagem recebida."""
    text = (message or "").lower()
    feminine = r"\b(mãe|mae|vó|avó|vovó|tia|irmã|irma|amiga|filha|senhora)\b"
    masculine = r"\b(pai|vô|avô|vovô|tio|irmão|irmao|amigo|filho|senhor)\b"
    feminine_match = re.search(feminine, text)
    masculine_match = re.search(masculine, text)
    if feminine_match and not masculine_match:
        return "feminino"
    if masculine_match and not feminine_match:
        return "masculino"
    return ""


def is_recipient_role_coherent(
    message: str,
    publico_slug: str,
    golpe_id: str = "",
) -> bool:
    """Valida o vínculo do destinatário com o público e o golpe selecionados."""
    if golpe_id != "falso_parente":
        return True
    text = (message or "").lower()
    if publico_slug == "idosos":
        return not bool(re.search(r"\bchefe\b", text))
    if publico_slug == "pais":
        return not bool(
            re.search(
                r"\b(vó|vovó|avó|vô|vovô|avô|neto|neta|chefe)\b",
                text,
            )
        )
    if publico_slug == "empresarios":
        return not bool(
            re.search(r"\b(mãe|mae|pai|filho|filha|vó|vô|avó|avô|neto|neta)\b", text)
        )
    return True


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


SEU_POSSESSIVE = frozenset({
    "whatsapp", "celular", "telefone", "dinheiro", "patrimonio", "patrimônio",
    "pix", "link", "conta", "app", "aplicativo", "privado", "grupo", "numero",
    "número", "banco", "cartao", "cartão", "email", "e-mail", "computador",
    "aporte", "investimento", "cadastro", "nome", "filho", "filha", "filhos",
})


def _gender_from_personagem_field(gp: str) -> str:
    if not gp:
        return ""
    if re.search(r"\b(idosa|mulher|feminino|senhora|aposentada)\b", gp):
        return "feminino"
    if re.search(r"\b(idoso|homem|masculino|senhor|aposentado)\b", gp):
        return "masculino"
    return ""


def _gender_from_roteiro(roteiro: str) -> str:
    if not roteiro:
        return ""
    r = roteiro.lower()
    if re.search(r"\bdona\s+\w+", r):
        return "feminino"
    m = re.search(r"\b(?:o\s+)?seu\s+(\w+)", r)
    if m and m.group(1).lower() not in SEU_POSSESSIVE:
        return "masculino"
    if re.search(r"\bm[ãa]e\b|\bvó\b|\bvovó\b|\bavó\b|\btitia\b|\bsogra\b", r):
        return "feminino"
    if re.search(r"\bpai\b|\bvô\b|\bvovô\b|\bavô\b|\btitio\b|\bsogro\b", r):
        return "masculino"
    tem_dela = bool(re.search(r"\bdela\b|\bela\b", r))
    tem_dele = bool(re.search(r"\bdele\b", r))
    if tem_dela and not tem_dele:
        return "feminino"
    if tem_dele and not tem_dela:
        return "masculino"
    return ""


def infer_protagonist_gender(creative_data: dict) -> str:
    """Infere gênero do protagonista — ROTEIRO prevalece sobre personagem/campo auxiliar."""
    from_roteiro = _gender_from_roteiro(creative_data.get("desenvolvimento_copy", ""))
    if from_roteiro:
        return from_roteiro

    from_field = _gender_from_personagem_field(
        (creative_data.get("genero_personagem_visual") or "").lower()
    )
    if from_field:
        return from_field

    aux = (
        creative_data.get("gancho_atencao_inicial", "") + " "
        + creative_data.get("texto_card_notificacao", "")
    ).lower()
    if re.search(r"\bm[ãa]e\b|\bdona\s+\w+", aux):
        return "feminino"
    if re.search(r"\bpai\b", aux):
        return "masculino"

    gc = creative_data.get("genero_campanha", "")
    return gc if gc in ("feminino", "masculino") else ""


def is_gender_coherent(creative_data: dict) -> bool:
    """True se genero_campanha/cena batem com o protagonista nomeado no roteiro."""
    roteiro_gender = _gender_from_roteiro(creative_data.get("desenvolvimento_copy", ""))
    if not roteiro_gender:
        return True
    campanha = creative_data.get("genero_campanha", "")
    return campanha == roteiro_gender


def describe_protagonist(creative_data: dict) -> str:
    """Resumo legível do protagonista inferido do roteiro."""
    roteiro = creative_data.get("desenvolvimento_copy", "") or ""
    m_dona = re.search(r"\bdona\s+(\w+)", roteiro, re.I)
    if m_dona:
        return f"feminino — Dona {m_dona.group(1).capitalize()}"
    m_seu = re.search(r"\b(?:o\s+)?seu\s+(\w+)", roteiro, re.I)
    if m_seu and m_seu.group(1).lower() not in SEU_POSSESSIVE:
        return f"masculino — Seu {m_seu.group(1).capitalize()}"
    g = _gender_from_roteiro(roteiro)
    if g == "feminino":
        return "feminino — protagonista feminina no roteiro"
    if g == "masculino":
        return "masculino — protagonista masculino no roteiro"
    return "neutro — roteiro sem protagonista nomeado"


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
