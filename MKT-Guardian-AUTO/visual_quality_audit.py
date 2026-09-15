"""QA multimodal opcional para imagem e vídeo finais."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from typing import Any

from google.genai import types


QUALITY_DIMENSIONS = (
    "rosto",
    "maos",
    "celular",
    "texto",
    "logo",
    "contraste",
    "personagem",
    "cenario",
    "coerencia_publico",
    "coerencia_roteiro",
    "cta",
    "canal",
)

CRITICAL_DIMENSIONS = {"rosto", "maos", "celular", "texto", "canal"}
STAGE_BY_DIMENSION = {
    "rosto": "imagem",
    "maos": "imagem",
    "celular": "imagem",
    "personagem": "imagem",
    "cenario": "imagem",
    "texto": "layout",
    "logo": "layout",
    "contraste": "layout",
    "cta": "layout",
    "canal": "layout",
    "coerencia_publico": "copy",
    "coerencia_roteiro": "copy",
}


@dataclass(frozen=True)
class QualityFinding:
    dimension: str
    score: float
    ok: bool
    reason: str
    recommended_stage: str


@dataclass
class VisualQualityResult:
    enabled: bool
    skipped: bool
    provider: str
    model: str
    overall_score: float | None
    passed: bool
    findings: list[QualityFinding]
    error: str = ""

    @property
    def recommended_stage(self) -> str:
        failed = [item for item in self.findings if not item.ok]
        if not failed:
            return ""
        stages = [item.recommended_stage for item in failed]
        for preferred in ("layout", "imagem", "copy", "video", "audio"):
            if preferred in stages:
                return preferred
        return stages[0]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["findings"] = [asdict(item) for item in self.findings]
        data["recommended_stage"] = self.recommended_stage
        return data


def _is_video(path: str) -> bool:
    return os.path.splitext(path.lower())[1] in {".mp4", ".mov", ".webm", ".mkv"}


def _extract_video_frames(path: str, directory: str) -> list[str]:
    pattern = os.path.join(directory, "frame_%02d.jpg")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        path,
        "-vf",
        "fps=1/3,scale=720:-2",
        "-frames:v",
        "3",
        "-q:v",
        "4",
        pattern,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    return [
        os.path.join(directory, name)
        for name in sorted(os.listdir(directory))
        if name.startswith("frame_") and name.endswith(".jpg")
    ]


def _read_media_parts(path: str) -> list[Any]:
    media_paths: list[str] = [path]
    with tempfile.TemporaryDirectory(prefix="guardian_qa_") as directory:
        if _is_video(path):
            media_paths = _extract_video_frames(path, directory)
        parts = []
        for media_path in media_paths[:3]:
            try:
                with open(media_path, "rb") as media_file:
                    parts.append(
                        types.Part.from_bytes(
                            data=media_file.read(),
                            mime_type="image/jpeg",
                        )
                    )
            except OSError:
                continue
        return parts


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    parsed = json.loads(cleaned)
    return parsed if isinstance(parsed, dict) else {}


class GeminiVisualQualityAuditor:
    """Analisa somente assets finais e retorna correção localizada."""

    def __init__(
        self,
        client: Any,
        *,
        model: str = "gemini-3.6-flash",
        enabled: bool = True,
        required: bool = False,
        minimum_score: float = 7.0,
    ):
        self.client = client
        self.model = model
        self.enabled = enabled
        self.required = required
        self.minimum_score = minimum_score

    def _skipped(self, reason: str) -> VisualQualityResult:
        return VisualQualityResult(
            enabled=self.enabled,
            skipped=True,
            provider="gemini",
            model=self.model,
            overall_score=None,
            passed=not self.required,
            findings=[],
            error=reason,
        )

    def audit(
        self,
        creative_data: dict,
        config: dict,
        assets: dict,
    ) -> VisualQualityResult:
        if not self.enabled:
            return self._skipped("QA multimodal desativada.")
        if self.client is None:
            return self._skipped("Cliente Gemini indisponível.")

        candidates = (
            assets.get("commercial_video_file"),
            assets.get("static_image_file"),
        )
        asset_path = next(
            (
                path for path in candidates
                if isinstance(path, str) and os.path.isfile(path)
            ),
            "",
        )
        if not asset_path:
            return self._skipped("Asset final ausente para análise multimodal.")
        parts = _read_media_parts(asset_path)
        if not parts:
            return self._skipped("Não foi possível preparar frames para análise.")

        brief = creative_data.get("creative_brief") or {}
        prompt = (
            "Você é um auditor de qualidade de criativos publicitários. "
            "Avalie os frames anexados contra o brief abaixo. "
            "Não invente defeitos que não estejam visíveis. "
            "Retorne SOMENTE JSON válido no formato: "
            '{"overall_score": 0, "checks": {"rosto": {"score": 0, "ok": false, "reason": ""}}}. '
            f"Critérios obrigatórios: {', '.join(QUALITY_DIMENSIONS)}. "
            "Cada score deve ser de 0 a 10 e ok só pode ser true a partir de 7. "
            f"Brief: público={brief.get('publico', config.get('publico', ''))}; "
            f"golpe={brief.get('golpe', config.get('golpe', ''))}; "
            f"personagem={brief.get('personagem', '')}; cenário={brief.get('cenario', '')}; "
            f"canal={config.get('canal', '')}; mídia={config.get('midia', '')}. "
            "Verifique também se o telefone e sua tela aparecem inteiros, sem corte "
            "nas bordas ou elementos importantes fora do enquadramento; se os textos "
            "pós-produzidos estão legíveis, se o CTA é claro, se o logo está presente "
            "e se não há deformações."
        )
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[prompt, *parts],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            payload = _parse_json(getattr(response, "text", "") or "")
            overall = max(0.0, min(10.0, float(payload.get("overall_score", 0))))
            findings: list[QualityFinding] = []
            checks = payload.get("checks") or {}
            for dimension in QUALITY_DIMENSIONS:
                item = checks.get(dimension) or {}
                score = max(0.0, min(10.0, float(item.get("score", overall))))
                ok = bool(item.get("ok", score >= self.minimum_score))
                findings.append(
                    QualityFinding(
                        dimension=dimension,
                        score=score,
                        ok=ok and score >= self.minimum_score,
                        reason=str(item.get("reason") or "Sem observação."),
                        recommended_stage=STAGE_BY_DIMENSION.get(dimension, "copy"),
                    )
                )
            critical_failures = [
                item for item in findings
                if item.dimension in CRITICAL_DIMENSIONS and not item.ok
            ]
            passed = overall >= self.minimum_score and not critical_failures
            return VisualQualityResult(
                enabled=True,
                skipped=False,
                provider="gemini",
                model=self.model,
                overall_score=round(overall, 2),
                passed=passed,
                findings=findings,
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return self._skipped(f"Resposta Gemini inválida: {exc}")
        except Exception as exc:
            return self._skipped(f"Falha na QA Gemini: {exc}")
