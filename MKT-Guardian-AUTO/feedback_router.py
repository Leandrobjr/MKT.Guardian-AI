"""Classifica feedback do Telegram MELHORAR para acionar a correção certa."""


def _has_narrative_intent(t: str) -> bool:
    """Pedidos de mudar estória, protagonista ou tipo de personagem — exige regerar copy."""
    narrative_terms = (
        "estória", "estoria", "narrativa", "historia", "história", "enredo",
        "protagonista", "diretor", "diretora", "professor", "professora",
        "escola", "mãe", "mae", "pai", "avó", "avo", "neto", "neta",
        "outra estória", "outra estoria", "outra historia", "outra história",
        "homem", "mulher", "masculino", "feminino", "ele ", "ela ",
    )
    if any(x in t for x in narrative_terms):
        return True
    change_verbs = ("trocar", "mudar", "alterar", "substituir", "quero ", "preciso ")
    subject_terms = ("personagem", "protagonista", "narrador", "cena narrativa", "estória", "estoria")
    if any(v in t for v in change_verbs) and any(s in t for s in subject_terms):
        return True
    return False


def classify_improvement(feedback: str) -> dict:
    t = feedback.lower().strip()
    narrative = _has_narrative_intent(t)

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
    copy = narrative or any(
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
    # "pessoa" / "personagem" só visual se NÃO for pedido narrativo
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

    recompose_only = layout and not copy and not visual and not audio
    reapply_audio_only = audio and not copy and not visual and not layout
    visual_only = visual and not copy and not audio and not layout and not narrative
    regenerate_copy = copy or (
        not layout and not visual and not audio and not copy and not narrative
    )

    return {
        "layout": layout,
        "copy": copy,
        "visual": visual,
        "audio": audio,
        "narrative": narrative,
        "recompose_only": recompose_only,
        "reapply_audio_only": reapply_audio_only,
        "visual_only": visual_only,
        "regenerate_copy": regenerate_copy and not recompose_only and not reapply_audio_only and not visual_only,
        "regenerate_visual": visual and not narrative,
        "regenerate_audio": audio,
    }


def describe_plan(plan: dict) -> str:
    if plan["recompose_only"]:
        return "layout/overlay (quebra de texto nos cards — sem regerar copy)"
    if plan.get("visual_only"):
        return "imagem/vídeo (nova cena — mantém copy e áudio aprovados)"
    if plan.get("reapply_audio_only"):
        return "narração/áudio (fechamento no card — sem regerar copy/Kling)"
    if plan.get("narrative"):
        return "estória/copy (mudança narrativa — regerar texto e mídia)"
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
