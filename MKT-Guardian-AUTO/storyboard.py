"""Storyboard determinístico para vídeos de campanha."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class StoryboardScene:
    cena: int
    duracao_segundos: int
    enquadramento: str
    movimento: str
    acao: str
    emocao: str
    texto_permitido: tuple[str, ...]
    transicao: str
    objetivo_narrativo: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["texto_permitido"] = list(self.texto_permitido)
        return data


def _is_video(config: dict) -> bool:
    media = str(config.get("midia") or "").lower()
    return "vídeo" in media or "video" in media or "animado" in media


def _target_duration(brief: dict) -> int:
    target = brief.get("formato", {}).get("target_narration_seconds")
    if target:
        try:
            return max(15, int(float(target)))
        except (TypeError, ValueError):
            pass
    duration = str(brief.get("duracao") or "")
    values = [int(value) for value in re.findall(r"\d+", duration)]
    return max(15, values[-1] if values else 20)


def _scene_durations(total: int) -> list[int]:
    weights = (0.16, 0.24, 0.22, 0.20, 0.18)
    durations = [max(2, round(total * weight)) for weight in weights]
    durations[-1] += total - sum(durations)
    if durations[-1] < 2:
        deficit = 2 - durations[-1]
        durations[-1] = 2
        for index in range(len(durations) - 2, -1, -1):
            reduction = min(deficit, max(0, durations[index] - 2))
            durations[index] -= reduction
            deficit -= reduction
            if not deficit:
                break
    return durations


def build_storyboard(
    brief: dict,
    config: dict,
    campaign_ctx: dict | None = None,
) -> list[dict]:
    """Cria cinco cenas para vídeo; imagem estática não recebe storyboard."""
    if not _is_video(config):
        return []

    campaign_ctx = campaign_ctx or {}
    durations = _scene_durations(_target_duration(brief))
    personagem = brief.get("personagem") or "protagonista brasileiro"
    cenario = brief.get("cenario") or "ambiente cotidiano organizado"
    mensagem = brief.get("mensagem_golpista") or "mensagem suspeita no WhatsApp"
    emocao = brief.get("emocao") or "urgência e proteção"
    return [
        StoryboardScene(
            cena=1,
            duracao_segundos=durations[0],
            enquadramento="plano médio contextual do protagonista e do ambiente",
            movimento="push-in lento e controlado",
            acao=f"{personagem} percebe uma situação de risco em {cenario}",
            emocao="alerta crescente",
            texto_permitido=("headline",),
            transicao="corte seco para o celular",
            objetivo_narrativo="Apresentar o risco nos primeiros segundos.",
        ).to_dict(),
        StoryboardScene(
            cena=2,
            duracao_segundos=durations[1],
            enquadramento="over-the-shoulder com close legível no celular",
            movimento="rack focus do rosto para a tela do WhatsApp",
            acao=f"O celular recebe a mensagem direta: “{mensagem}”",
            emocao="surpresa e tensão",
            texto_permitido=("mensagem do card do golpe",),
            transicao="match cut acompanhando o movimento do celular",
            objetivo_narrativo="Mostrar a isca real do golpe em conversa 1:1.",
        ).to_dict(),
        StoryboardScene(
            cena=3,
            duracao_segundos=durations[2],
            enquadramento="close-up natural da reação do protagonista",
            movimento="pan lateral curto, sem gesto exagerado",
            acao=f"{personagem} interrompe a ação e confere a mensagem com cuidado",
            emocao=emocao,
            texto_permitido=(),
            transicao="dissolve curto para o alerta",
            objetivo_narrativo="Agitar a dor e criar identificação com o público.",
        ).to_dict(),
        StoryboardScene(
            cena=4,
            duracao_segundos=durations[3],
            enquadramento="insert do celular com área segura para o card Guardian AI",
            movimento="leve zoom-in no alerta, mantendo a tela estável",
            acao="Guardian AI detecta o padrão suspeito e envia um alerta imediato",
            emocao="alívio e proteção",
            texto_permitido=("card de solução",),
            transicao="wipe suave para a cena final",
            objetivo_narrativo="Apresentar a solução e sua capacidade real.",
        ).to_dict(),
        StoryboardScene(
            cena=5,
            duracao_segundos=durations[4],
            enquadramento="plano médio limpo, protagonista seguro e composição central",
            movimento="pull-back sutil com encerramento estável",
            acao="O protagonista decide não responder ao golpe e fica protegido",
            emocao="confiança e decisão",
            texto_permitido=("CTA", "URL"),
            transicao="encerramento em fade",
            objetivo_narrativo="Concluir a história e orientar a conversão.",
        ).to_dict(),
    ]


def format_storyboard_prompt(storyboard: list[dict]) -> str:
    """Resume o storyboard para prompts visuais sem permitir texto gerado por IA."""
    if not storyboard:
        return ""
    lines = ["STORYBOARD — RESPEITE A SEQUÊNCIA E O MOVIMENTO:"]
    for scene in storyboard:
        lines.append(
            f"Cena {scene['cena']} ({scene['duracao_segundos']}s): "
            f"{scene['enquadramento']}; {scene['movimento']}; {scene['acao']}. "
            f"Transição: {scene['transicao']}."
        )
    lines.append(
        "Textos permitidos somente na pós-produção: headline, cards, CTA e URL. "
        "Não renderize texto dentro da imagem gerada."
    )
    return " ".join(lines)


def format_storyboard_compact(storyboard: list[dict]) -> str:
    if not storyboard:
        return "Não aplicável — mídia estática."
    return " | ".join(
        f"Cena {scene['cena']} ({scene['duracao_segundos']}s): {scene['objetivo_narrativo']}"
        for scene in storyboard
    )
