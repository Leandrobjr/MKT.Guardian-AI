"""Classifica feedback do Telegram/terminal MELHORAR para acionar a correção certa."""

from __future__ import annotations

import re

CATEGORIAS = ("narrativa", "headline", "visual", "golpe", "layout", "audio", "copy")


def _has_narrative_intent(t: str) -> bool:
    """Pedidos de mudar estória, protagonista, ICP ou tipo de personagem."""
    narrative_terms = (
        "estória", "estoria", "narrativa", "historia", "história", "enredo",
        "protagonista", "diretor", "diretora", "professor", "professora",
        "escola", "escolar", "mãe", "mae", "pai", "avó", "avo", "neto", "neta",
        "idoso", "idosos", "aposentad", "empresário", "empresario", "comerciante",
        "outra estória", "outra estoria", "outra historia", "outra história",
        "homem", "mulher", "masculino", "feminino", "ele ", "ela ",
    )
    if any(x in t for x in narrative_terms):
        return True
    change_verbs = ("trocar", "mudar", "alterar", "substituir", "quero ", "preciso ", "focar")
    subject_terms = ("personagem", "protagonista", "narrador", "cena narrativa", "estória", "estoria", "icp", "público", "publico")
    if any(v in t for v in change_verbs) and any(s in t for s in subject_terms):
        return True
    return False


def _has_golpe_intent(t: str) -> bool:
    golpe_terms = (
        "outro golpe", "trocar golpe", "mudar golpe", "variante",
        "tipo de golpe", "golpe diferente", "abordar outro",
    )
    if any(x in t for x in golpe_terms):
        return True
    especificos = (
        "pix", "phishing", "link malicioso", "clonagem", "grooming",
        "falso parente", "falsa central", "falso emprego", "investimento",
        "boleto", "encomenda", "sextorsão", "sextorsao",
    )
    change = ("golpe", "frase golp", "mensagem golp", "card golp", "ameaça")
    return any(g in t for g in especificos) and any(c in t for c in change + ("quero", "preciso", "trocar", "mudar"))


def _has_headline_intent(t: str) -> bool:
    headline_terms = ("headline", "titulo", "título", "manchete", "gancho", "chamar")
    if not any(x in t for x in headline_terms):
        return False
    full_copy = any(x in t for x in ("roteiro", "narra", "estória", "estoria", "historia", "história", "copy inteir"))
    return not full_copy


def detect_narrative_override(feedback: str) -> dict:
    """
    Detecta override temporário de ICP e/ou golpe a partir do feedback livre.
    Retorna dict com publico_slug, golpe_id, note (pode estar vazio).
    """
    t = feedback.lower().strip()
    if not t or not _has_narrative_intent(t):
        return {}

    override: dict = {"note": feedback.strip()[:300]}

    publico_patterns: list[tuple[tuple[str, ...], str, str]] = [
        (("escola", "escolar", "diretor", "diretora", "professor", "professora", "coordenador"), "escolas", "escola"),
        (("idoso", "idosos", "aposentad", "avó", "avo", "vó", "vo ", "neto", "neta"), "idosos", "idosos"),
        (("empresário", "empresario", "comerciante", "lojista", "negócio", "negocio", "caixa", "cnpj"), "empresarios", "empresários"),
        (("pai", "mãe", "mae", "filho", "filha", "família", "familia", "menor", "adolescente"), "pais", "pais"),
    ]
    for keywords, slug, label in publico_patterns:
        if any(k in t for k in keywords):
            override["publico_slug"] = slug
            override["publico_label"] = label
            break

    golpe_patterns: list[tuple[tuple[str, ...], str]] = [
        (("falso parente", "falso filho", "troquei de número", "troquei de numero", "neto", "neta"), "falso_parente"),
        (("pix", "transferência", "transferencia", "qr code", "boleto"), "pix_fantasma"),
        (("central", "banco", "atendente", "suporte banc"), "falsa_central"),
        (("grooming", "aliciamento", "predador", "menor", "filho"), "grooming"),
        (("phishing", "link", "clique", "bit.ly", "malicioso", "encomenda", "apk"), "link_malicioso"),
        (("clonagem", "código sms", "codigo sms", "verificação", "verificacao"), "clonagem_whatsapp"),
        (("emprego", "vaga", "home office", "rh falso"), "falso_emprego"),
        (("investimento", "cripto", "grupo vip", "lucro garantido"), "falso_investimento"),
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
    copy = narrative or golpe or any(
        x in t
        for x in (
            "headline", "titulo", "título", "roteiro", "narra", "gancho",
            "cta", "copy", "re/escrev", "reescrev", "mudar o texto da",
            "texto do golp", "frase do golp", "chamar", "urgencia",
            "estória", "estoria", "historia", "história", "sentido",
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
    if not narrative and any(x in t for x in ("pessoa", "personagem", "modelo")):
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
        copy = False if not narrative else copy

    headline_only = headline and not narrative and not golpe and not visual and not layout and not audio

    recompose_only = layout and not copy and not visual and not audio
    reapply_audio_only = audio and not copy and not visual and not layout
    visual_only = visual and not copy and not audio and not layout and not narrative
    regenerate_copy = copy or (
        not layout and not visual and not audio and not copy and not narrative and not golpe
    )

    if narrative:
        primary = "narrativa"
    elif headline_only:
        primary = "headline"
    elif golpe and not narrative:
        primary = "golpe"
    elif visual_only or (visual and not copy):
        primary = "visual"
    elif layout and recompose_only:
        primary = "layout"
    elif audio and reapply_audio_only:
        primary = "audio"
    else:
        primary = "copy"

    override = detect_narrative_override(feedback) if narrative else {}

    return {
        "layout": layout,
        "copy": copy,
        "visual": visual,
        "audio": audio,
        "narrative": narrative,
        "golpe": golpe,
        "headline": headline,
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
