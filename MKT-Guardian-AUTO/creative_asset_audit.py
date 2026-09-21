"""Auditoria automática do criativo final antes da aprovação/publicação."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from PIL import Image

from campaign_history import visual_hash


_PLACEHOLDERS = {
    "",
    "N/A",
    "FALHOU",
    "NÃO SOLICITADO",
    "NÃO SOLICITADA",
    "NAO SOLICITADO",
    "NAO SOLICITADA",
}
_CTA_GRAMMAR_RE = re.compile(r"\b(?:dos\s+sua|da\s+seu|do\s+sua|das\s+seu)\b", re.IGNORECASE)
_FEMALE_CHILD_RE = re.compile(r"\b(?:filha|menina)\b", re.IGNORECASE)
_MALE_CHILD_RE = re.compile(r"\b(?:filho|menino)\b", re.IGNORECASE)
_LUFS_RE = re.compile(r"Input Integrated:\s*(-?\d+(?:\.\d+)?)\s*LUFS", re.IGNORECASE)


@dataclass(frozen=True)
class AuditIssue:
    code: str
    severity: str
    message: str


@dataclass
class CreativeAssetAudit:
    blocking: list[AuditIssue] = field(default_factory=list)
    warnings: list[AuditIssue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    recommended_stage: str = ""

    @property
    def ok(self) -> bool:
        return not self.blocking

    def add_blocking(self, code: str, message: str) -> None:
        self.blocking.append(AuditIssue(code, "blocking", message))

    def add_warning(self, code: str, message: str) -> None:
        self.warnings.append(AuditIssue(code, "warning", message))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "blocking": [asdict(issue) for issue in self.blocking],
            "warnings": [asdict(issue) for issue in self.warnings],
            "metrics": self.metrics,
            "recommended_stage": self.recommended_stage,
        }


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _is_video_media(config: dict, creative_data: dict) -> bool:
    media = str(
        config.get("midia")
        or creative_data.get("tipo_midia_selecionada")
        or ""
    ).lower()
    return "vídeo" in media or "video" in media or "animado" in media


def _usable_path(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    path = value.strip()
    return "" if path.upper() in _PLACEHOLDERS else path


def _run_command(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _probe_streams(path: str, runner: CommandRunner) -> dict[str, Any]:
    try:
        result = runner(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,duration,width,height",
                "-of",
                "json",
                path,
            ],
            timeout=20,
        )
        if result.returncode != 0:
            return {}
        return json.loads(result.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return {}


def _probe_lufs(path: str, runner: CommandRunner) -> float | None:
    try:
        result = runner(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                path,
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=summary",
                "-f",
                "null",
                "-",
            ],
            timeout=45,
        )
        match = _LUFS_RE.search(result.stderr or "")
        return float(match.group(1)) if match else None
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return None


def _stream_types(probe: dict[str, Any]) -> set[str]:
    return {
        str(stream.get("codec_type"))
        for stream in probe.get("streams", [])
        if isinstance(stream, dict) and stream.get("codec_type")
    }


def _duration(probe: dict[str, Any]) -> float | None:
    raw = probe.get("format", {}).get("duration")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _expected_dimensions(creative_data: dict) -> tuple[int, int] | None:
    preset = creative_data.get("preset_midia") or {}
    try:
        width = int(preset["width"])
        height = int(preset["height"])
    except (KeyError, TypeError, ValueError):
        return None
    return width, height


def _audit_dimensions(
    audit: CreativeAssetAudit,
    image_path: str,
    creative_data: dict,
) -> None:
    try:
        with Image.open(image_path) as image:
            actual = image.size
    except (OSError, ValueError):
        audit.add_blocking("imagem_invalida", "O JPG final não pôde ser aberto.")
        return

    audit.metrics["image_dimensions"] = {"width": actual[0], "height": actual[1]}
    expected = _expected_dimensions(creative_data)
    if expected and actual != expected:
        audit.add_blocking(
            "dimensao_invalida",
            f"Dimensão do JPG {actual[0]}x{actual[1]}; esperado {expected[0]}x{expected[1]}.",
        )


def _audit_cta(audit: CreativeAssetAudit, creative_data: dict) -> None:
    cta = str(
        creative_data.get("texto_botao_conversao")
        or creative_data.get("chamada_para_acao_cta")
        or ""
    ).strip()
    if not cta:
        audit.add_blocking("cta_ausente", "CTA final não foi definido.")
        return

    audit.metrics["cta"] = cta
    if _CTA_GRAMMAR_RE.search(cta):
        audit.add_blocking(
            "cta_gramatica",
            f"CTA contém combinação gramatical inválida: {cta}",
        )

    narrative = " ".join(
        str(creative_data.get(field) or "")
        for field in (
            "gancho_atencao_inicial",
            "desenvolvimento_copy",
            "texto_card_notificacao",
        )
    )
    narrative_female = bool(_FEMALE_CHILD_RE.search(narrative))
    narrative_male = bool(_MALE_CHILD_RE.search(narrative))
    cta_female = bool(_FEMALE_CHILD_RE.search(cta))
    cta_male = bool(_MALE_CHILD_RE.search(cta))
    if narrative_male and not narrative_female and cta_female and not cta_male:
        audit.add_blocking(
            "cta_publico_incoerente",
            "O roteiro menciona filho/menino, mas o CTA menciona filha/menina.",
        )
    if narrative_female and not narrative_male and cta_male and not cta_female:
        audit.add_blocking(
            "cta_publico_incoerente",
            "O roteiro menciona filha/menina, mas o CTA menciona filho/menino.",
        )


def _audit_visual_variation(
    audit: CreativeAssetAudit,
    creative_data: dict,
    config: dict,
    history: Any,
) -> None:
    if history is None:
        return
    scene = str(creative_data.get("direcao_arte_emocional") or "")
    persona = str(creative_data.get("persona_id") or "")
    if not scene and not persona:
        return

    current_hash = visual_hash(scene, persona)
    audit.metrics["visual_hash"] = current_hash
    try:
        recent = history.get_recent(
            config.get("publico_slug", ""),
            config.get("golpe_id", ""),
            limit=10,
        )
    except (AttributeError, TypeError):
        return

    basename = str(config.get("_asset_basename") or "")
    repeated = [
        row
        for row in recent
        if row.get("visual_hash") == current_hash
        and row.get("basename") != basename
    ]
    if repeated:
        audit.add_warning(
            "visual_repetido",
            "A cena/persona coincide com um criativo recente do mesmo combo.",
        )


def _audit_media(
    audit: CreativeAssetAudit,
    creative_data: dict,
    config: dict,
    assets: dict,
    runner: CommandRunner,
) -> None:
    image_path = _usable_path(assets.get("static_image_file"))
    video_path = _usable_path(assets.get("commercial_video_file"))
    audio_path = _usable_path(assets.get("audio_file"))
    is_video = _is_video_media(config, creative_data)

    required_path = video_path if is_video else image_path
    if not required_path or not os.path.isfile(required_path):
        expected = "MP4" if is_video else "JPG"
        audit.add_blocking(
            "asset_ausente",
            f"Asset principal ausente ou inválido: {expected}.",
        )
    elif not is_video:
        _audit_dimensions(audit, required_path, creative_data)

    if image_path and os.path.isfile(image_path):
        _audit_dimensions(audit, image_path, creative_data)

    if is_video:
        if not audio_path or not os.path.isfile(audio_path):
            audit.add_blocking("audio_ausente", "Vídeo sem arquivo de áudio da narração.")

        if video_path and os.path.isfile(video_path):
            video_probe = _probe_streams(video_path, runner)
            video_types = _stream_types(video_probe)
            audit.metrics["video_streams"] = sorted(video_types)
            if "video" not in video_types:
                audit.add_blocking("video_invalido", "MP4 não contém stream de vídeo válido.")
            if "audio" not in video_types:
                audit.add_blocking("audio_no_video_ausente", "MP4 final não contém stream de áudio.")
            if audio_path and os.path.isfile(audio_path):
                audio_probe = _probe_streams(audio_path, runner)
                video_duration = _duration(video_probe)
                audio_duration = _duration(audio_probe)
                if video_duration and audio_duration:
                    difference = abs(video_duration - audio_duration)
                    audit.metrics["duration_difference_seconds"] = round(difference, 3)
                    if difference > 1.5:
                        audit.add_warning(
                            "duracoes_divergentes",
                            "Duração do vídeo e da narração diverge mais de 1,5 segundo.",
                        )

    if audio_path and os.path.isfile(audio_path):
        lufs = _probe_lufs(audio_path, runner)
        if lufs is not None:
            audit.metrics["audio_integrated_lufs"] = lufs
            if lufs < -20:
                audit.add_warning(
                    "audio_baixo",
                    f"Áudio abaixo do nível recomendado: {lufs:.1f} LUFS.",
                )


def _audit_visual_quality(
    audit: CreativeAssetAudit,
    creative_data: dict,
    config: dict,
    assets: dict,
    visual_auditor: Any,
) -> None:
    try:
        result = visual_auditor.audit(creative_data, config, assets)
    except Exception as exc:
        audit.add_warning("qa_visual_erro", f"QA multimodal indisponível: {exc}")
        return
    result_data = result.to_dict() if hasattr(result, "to_dict") else {}
    audit.metrics["visual_quality"] = result_data
    if getattr(result, "skipped", False):
        if getattr(result, "error", ""):
            audit.add_warning(
                "qa_visual_indisponivel",
                str(result.error),
            )
        if getattr(result, "passed", True):
            return
    if getattr(result, "passed", True):
        return
    failed = [
        finding for finding in getattr(result, "findings", [])
        if not getattr(finding, "ok", True)
    ]
    details = "; ".join(
        f"{finding.dimension}={finding.score:.1f}: {finding.reason}"
        for finding in failed[:3]
    )
    audit.recommended_stage = getattr(result, "recommended_stage", "") or "imagem"
    score = getattr(result, "overall_score", None)
    score_text = "indisponível" if score is None else f"{score:.1f}/10"
    audit.add_blocking(
        "qa_visual_abaixo_minimo",
        f"Nota multimodal {score_text} abaixo do mínimo. {details}".strip(),
    )


def _recommended_stage_from_blocking(audit: CreativeAssetAudit, is_video: bool) -> str:
    if audit.recommended_stage:
        return audit.recommended_stage
    codes = {issue.code for issue in audit.blocking}
    if codes & {"audio_ausente", "audio_no_video_ausente"}:
        return "audio"
    if "video_invalido" in codes:
        return "video"
    if codes & {"dimensao_invalida", "imagem_invalida"}:
        return "imagem"
    if codes & {"cta_ausente", "cta_gramatica", "cta_publico_incoerente"}:
        return "layout"
    if "asset_ausente" in codes:
        return "video" if is_video else "imagem"
    return "copy"


def audit_creative_assets(
    creative_data: dict,
    config: dict,
    assets: dict,
    *,
    history: Any = None,
    runner: CommandRunner = _run_command,
    visual_auditor: Any = None,
) -> CreativeAssetAudit:
    """Audita localmente e, quando configurado, usa QA multimodal."""
    audit = CreativeAssetAudit()
    config_for_variation = dict(config)
    config_for_variation["_asset_basename"] = assets.get("basename", "")
    _audit_cta(audit, creative_data)
    _audit_media(audit, creative_data, config, assets, runner)
    _audit_visual_variation(audit, creative_data, config_for_variation, history)
    if visual_auditor is not None:
        _audit_visual_quality(audit, creative_data, config, assets, visual_auditor)
    visual_quality = audit.metrics.get("visual_quality")
    audit.metrics["qa_multimodal_passed"] = bool(
        isinstance(visual_quality, dict)
        and visual_quality.get("enabled")
        and not visual_quality.get("skipped")
        and visual_quality.get("passed")
    )
    if isinstance(visual_quality, dict):
        audit.metrics["qa_multimodal_score"] = visual_quality.get("overall_score")
    audit.metrics["media_type"] = "video" if _is_video_media(config, creative_data) else "image"
    audit.recommended_stage = _recommended_stage_from_blocking(
        audit,
        _is_video_media(config, creative_data),
    )
    return audit


def format_audit_result(audit: CreativeAssetAudit) -> str:
    lines = [
        f"QA criativo: {'OK' if audit.ok else 'REPROVADO'}",
        f"  Métricas: {json.dumps(audit.metrics, ensure_ascii=False, sort_keys=True)}",
    ]
    for issue in audit.blocking + audit.warnings:
        lines.append(f"  [{issue.severity.upper()}] {issue.code}: {issue.message}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("Use audit_creative_assets() a partir do orquestrador ou dos testes.")
