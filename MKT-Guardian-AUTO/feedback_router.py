"""Classifica feedback do Telegram MELHORAR para acionar a correção certa."""


def classify_improvement(feedback: str) -> dict:
    t = feedback.lower().strip()

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
    copy = any(
        x in t
        for x in (
            "headline", "titulo", "título", "roteiro", "narra", "gancho",
            "cta", "copy", "re/escrev", "reescrev", "mudar o texto da",
            "texto do golp", "frase do golp", "chamar", "urgencia",
        )
    )
    visual = any(
        x in t
        for x in (
            "imagem", "foto", "cena", "cozinha", "loja", "vídeo", "video",
            "kling", "pessoa", "empresário", "empresario", "ambiente",
            "cenário", "cenario", "modelo", "atriz", "ator",
        )
    )
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
        copy = False

    recompose_only = layout and not copy and not visual and not audio
    reapply_audio_only = audio and not copy and not visual and not layout
    regenerate_copy = copy or (not layout and not visual and not audio and not copy)

    return {
        "layout": layout,
        "copy": copy,
        "visual": visual,
        "audio": audio,
        "recompose_only": recompose_only,
        "reapply_audio_only": reapply_audio_only,
        "regenerate_copy": regenerate_copy and not recompose_only and not reapply_audio_only,
        "regenerate_visual": visual,
        "regenerate_audio": audio,
    }


def describe_plan(plan: dict) -> str:
    if plan["recompose_only"]:
        return "layout/overlay (quebra de texto nos cards — sem regerar copy)"
    if plan.get("reapply_audio_only"):
        return "narração/áudio (fechamento no card — sem regerar copy/Kling)"
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
