"""Classifica feedback do Telegram/terminal MELHORAR para acionar a correção certa."""

from __future__ import annotations

import re

CATEGORIAS = ("narrativa", "headline", "visual", "golpe", "layout", "audio", "copy")


def _is_surgical_copy_edit(t: str) -> bool:
    """Edição pontual de frase, card ou regra de produto — não troca ICP/golpe do menu."""
    markers = (
        "altere a seguinte frase",
        "no roteiro",
        "mude para:",
        "mude para ",
        "substitua por",
        "substituir por",
        "no card golp",
        "card golpista altere",
        "card golpísta altere",
        "lembre-se sempre",
        "lembre se sempre",
        "não citar",
        "nao citar",
        "nunca citar",
        "nunca afirmar",
        "não afirmar",
        "nao afirmar",
        "monitora conversas",
        "monitora essas conversas",
        "texto exato",
    )
    if any(m in t for m in markers):
        return True
    if "altere" in t and any(x in t for x in ("roteiro", "frase", "card")):
        return True
    return False


def _has_explicit_icp_change_intent(t: str) -> bool:
    """Troca real de ICP/protagonista — não palavras soltas dentro de texto de card."""
    if _is_surgical_copy_edit(t):
        return False
    explicit = (
        "estória de escola",
        "estoria de escola",
        "historia de escola",
        "história de escola",
        "quero escola",
        "focar em escola",
        "focar na escola",
        "ambiente escolar",
        "trocar protagonista",
        "protagonista diretor",
        "protagonista professora",
        "diretor escolar",
        "estória de idoso",
        "estoria de idoso",
        "quero idoso",
        "focar em idoso",
        "estória de empres",
        "estoria de empres",
        "quero empres",
        "focar no comerciante",
        "focar no empres",
        "outra estória",
        "outra estoria",
        "mudar icp",
        "trocar icp",
        "trocar público",
        "trocar publico",
        "não mãe",
        "nao mae",
        "não pai",
        "nao pai",
        "com pai de família",
        "com mãe de família",
        "com mae de familia",
    )
    if any(p in t for p in explicit):
        return True
    return bool(
        re.search(
            r"(quero|preciso|focar|trocar|mudar).{0,40}"
            r"(escola|idoso|empres|comerciante|diretor|coordenador pedag)",
            t,
        )
    )


def _has_explicit_golpe_change_intent(t: str) -> bool:
    """Troca real de tipo de golpe — não 'PIX' dentro de texto de card."""
    if _is_surgical_copy_edit(t):
        return False
    explicit = (
        "outro golpe",
        "trocar golpe",
        "mudar golpe",
        "golpe diferente",
        "tipo de golpe",
        "abordar outro golpe",
        "estória de pix",
        "estoria de pix",
        "focar no pix",
        "focar no grooming",
        "abordar grooming",
        "abordar o pix",
        "variante do golpe",
        "golpe do falso parente",
        "falso parente",
    )
    if any(p in t for p in explicit):
        return True
    if re.search(r"(quero|preciso|trocar|mudar).{0,30}golpe", t):
        return True
    return False


def _has_narrative_intent(t: str) -> bool:
    """Pedidos de mudar estória, protagonista ou ICP — não edição cirúrgica de copy."""
    if _is_surgical_copy_edit(t):
        return False
    if _has_explicit_icp_change_intent(t):
        return True
    return any(
        x in t
        for x in (
            "protagonista",
            "trocar personagem",
            "mudar protagonista",
            "homem no lugar",
            "mulher no lugar",
            "masculino no lugar",
            "feminino no lugar",
        )
    )


def _has_golpe_intent(t: str) -> bool:
    if _is_surgical_copy_edit(t):
        return False
    return _has_explicit_golpe_change_intent(t)


def _has_headline_intent(t: str) -> bool:
    headline_terms = ("headline", "titulo", "título", "manchete", "gancho", "chamar")
    if not any(x in t for x in headline_terms):
        return False
    full_copy = any(x in t for x in ("roteiro", "narra", "estória", "estoria", "historia", "história", "copy inteir"))
    return not full_copy


def detect_narrative_override(feedback: str) -> dict:
    """
    Detecta override temporário de ICP e/ou golpe — só com intenção explícita.
    Edições cirúrgicas de frase/card NÃO disparam override.
    """
    t = feedback.lower().strip()
    if not t or _is_surgical_copy_edit(t):
        return {}

    override: dict = {"note": feedback.strip()[:300]}
    icp_change = _has_explicit_icp_change_intent(t)
    golpe_change = _has_explicit_golpe_change_intent(t)

    if not icp_change and not golpe_change:
        return {}

    if icp_change:
        publico_patterns: list[tuple[tuple[str, ...], str, str]] = [
            (("escola", "escolar", "diretor", "diretora", "professor", "professora", "coordenador"), "escolas", "escola"),
            (("idoso", "idosos", "aposentad", "avó", "avo", "vó"), "idosos", "idosos"),
            (("empresário", "empresario", "comerciante", "lojista", "negócio", "negocio", "caixa", "cnpj"), "empresarios", "empresários"),
            (("pai de família", "pai de familia", "quero pai", "focar no pai", "não mãe", "nao mae"), "pais", "pais"),
            (("mãe de família", "mae de familia", "quero mãe", "quero mae", "focar na mãe", "não pai", "nao pai"), "pais", "pais"),
        ]
        for keywords, slug, label in publico_patterns:
            if any(k in t for k in keywords):
                override["publico_slug"] = slug
                override["publico_label"] = label
                break

    if golpe_change:
        golpe_patterns: list[tuple[tuple[str, ...], str]] = [
            (("falso parente", "falso filho", "troquei de número", "troquei de numero"), "falso_parente"),
            (("pix fantasma", "golpe do pix", "focar no pix", "estória de pix", "estoria de pix", "qr code", "boleto falso"), "pix_fantasma"),
            (("falsa central", "central banc", "suporte banc"), "falsa_central"),
            (("grooming", "aliciamento", "predador digital"), "grooming"),
            (("phishing", "link malicioso", "bit.ly", "apk falso"), "link_malicioso"),
            (("clonagem", "código sms", "codigo sms"), "clonagem_whatsapp"),
            (("falso emprego", "vaga falsa", "home office falso"), "falso_emprego"),
            (("falso investimento", "cripto falsa", "grupo vip"), "falso_investimento"),
        ]
        for keywords, golpe_id in golpe_patterns:
            if any(k in t for k in keywords):
                override["golpe_id"] = golpe_id
                break

    if len(override) <= 1:
        return {}
    return override


def correction_tag(plan: dict) -> str:
    """Tag principal para memória ([narrativa], [headline], etc.)."""
    cat = plan.get("primary_category", "copy")
    return f"[{cat}]"


def classify_improvement(feedback: str) -> dict:
    t = feedback.lower().strip()
    surgical = _is_surgical_copy_edit(t)
    narrative = _has_narrative_intent(t)
    golpe = _has_golpe_intent(t)
    headline = _has_headline_intent(t)

    layout = any(
        x in t
        for x in (
            "extrapol", "overflow", "quebra", "limite", "cortad", "vazou",
            "wrap", "layout", "primeiro card", "1º card", "1o card",
            "mensagem suspeita", "card whatsapp", "card do",
            "não cabe", "nao cabe", "saiu do", "fora do card", "linha",
            "fonte grande", "fonte menor", "quebrar",
        )
    )
    copy = surgical or narrative or golpe or any(
        x in t
        for x in (
            "headline", "titulo", "título", "roteiro", "narra", "gancho",
            "cta", "copy", "re/escrev", "reescrev", "mudar o texto da",
            "texto do golp", "frase do golp", "chamar", "urgencia",
            "estória", "estoria", "historia", "história", "sentido",
            "altere", "mude para", "substitua",
        )
    )
    visual = any(
        x in t
        for x in (
            "imagem", "foto", "cena visual", "cozinha", "loja", "vídeo", "video",
            "kling", "empresário", "empresario", "ambiente",
            "cenário", "cenario", "modelo", "atriz", "ator",
            "pobre", "humilde", "vestid", "aparência", "aparencia", "bem vest",
            "organizad", "claro", "limpo", "fallback", "gemini",
        )
    )
    if not narrative and not surgical and any(x in t for x in ("pessoa", "personagem", "modelo")):
        visual = True

    pronunciation = any(
        x in t
        for x in (
            ".ap", "a p p", "a p. p", "soletr", "guardian traço",
            "ponto a", "url falad", "dominio", "domínio", "site no final",
        )
    )
    audio = any(
        x in t
        for x in (
            "áudio", "audio", "voz", "narração", "narracao",
            "pronuncia", "pronúncia", "fala", "eleven", "site", "url",
        )
    ) or pronunciation

    if pronunciation and not any(
        x in t for x in ("headline", "titulo", "título", "reescrev", "re/escrev", "mudar o texto")
    ):
        copy = False if not narrative and not surgical else copy

    headline_only = headline and not narrative and not golpe and not visual and not layout and not audio and not surgical

    recompose_only = layout and not copy and not visual and not audio
    reapply_audio_only = audio and not copy and not visual and not layout
    visual_only = visual and not copy and not audio and not layout and not narrative
    regenerate_copy = copy or (
        not layout and not visual and not audio and not copy and not narrative and not golpe
    )

    if surgical:
        primary = "copy"
    elif narrative:
        primary = "narrativa"
    elif headline_only:
        primary = "headline"
    elif golpe:
        primary = "golpe"
    elif visual_only or (visual and not copy):
        primary = "visual"
    elif layout and recompose_only:
        primary = "layout"
    elif audio and reapply_audio_only:
        primary = "audio"
    else:
        primary = "copy"

    override = detect_narrative_override(feedback)

    return {
        "layout": layout,
        "copy": copy,
        "visual": visual,
        "audio": audio,
        "narrative": narrative,
        "golpe": golpe,
        "headline": headline,
        "surgical_copy": surgical,
        "headline_only": headline_only,
        "narrative_override": override,
        "primary_category": primary,
        "recompose_only": recompose_only,
        "reapply_audio_only": reapply_audio_only,
        "visual_only": visual_only,
        "regenerate_copy": regenerate_copy and not recompose_only and not reapply_audio_only and not visual_only and not headline_only,
        "regenerate_visual": visual and not narrative,
        "regenerate_audio": audio,
    }


def describe_plan(plan: dict) -> str:
    if plan.get("surgical_copy"):
        return "copy cirúrgica (frase/card/regra — mantém combo do menu)"
    if plan.get("headline_only"):
        return "headline/manchete (nova manchete + overlay — mantém roteiro)"
    if plan["recompose_only"]:
        return "layout/overlay (quebra de texto nos cards — sem regerar copy)"
    if plan.get("visual_only"):
        return "imagem/vídeo (nova cena — mantém copy e áudio aprovados)"
    if plan.get("reapply_audio_only"):
        return "narração/áudio (fechamento no card — sem regerar copy/Kling)"
    if plan.get("golpe") and not plan.get("narrative"):
        return "golpe/variante (nova frase golpista — regerar copy e card)"
    if plan.get("narrative"):
        return "estória/narrativa (mudança de enredo ou ICP — regerar texto e mídia)"
    parts = []
    if plan["regenerate_copy"]:
        parts.append("copy")
    if plan["regenerate_visual"]:
        parts.append("imagem/vídeo")
    if plan["regenerate_audio"]:
        parts.append("áudio")
    if plan["layout"] and not plan["recompose_only"]:
        parts.append("overlay")
    return " + ".join(parts) if parts else "copy completa"


def format_menu_conflict(
    menu_publico: str,
    menu_golpe: str,
    override: dict,
) -> str:
    """Mensagem UX quando override conflita com seleção do menu."""
    lines = [
        "⚠️ CONFLITO COM O MENU — sua instrução sobrescreve a matriz nesta revisão:",
        f"   Menu: público={menu_publico or '?'} | golpe={menu_golpe or '?'}",
    ]
    if override.get("publico_slug") and override["publico_slug"] != menu_publico:
        lines.append(
            f"   → Narrativa aplicada: público={override['publico_slug']} "
            f"(menu mantém {menu_publico} — troque o menu na próxima campanha se quiser fixar)"
        )
    if override.get("golpe_id") and override["golpe_id"] != menu_golpe:
        lines.append(
            f"   → Golpe aplicado: {override['golpe_id']} "
            f"(menu mantém {menu_golpe})"
        )
    if not override.get("publico_slug") and not override.get("golpe_id"):
        lines.append("   → Override narrativo genérico (instrução livre no prompt)")
    return "\n".join(lines)
