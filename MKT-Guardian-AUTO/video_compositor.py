"""Compositor FFmpeg — movimento nativo do clipe Kling sem reencodar centenas de JPEGs."""

from __future__ import annotations

import os
import subprocess


def _run(cmd: list[str]) -> tuple[bool, str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "")[-500:]
    return True, ""


def probe_duration(path: str) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path,
            ],
            capture_output=True, text=True, check=True,
        )
        return max(float(result.stdout.strip()), 1.0)
    except Exception:
        return 5.0


def build_boomerang_video(
    source_mp4: str,
    boom_mp4: str,
    width: int,
    height: int,
    slowdown: float = 1.35,
    fps: int = 24,
) -> bool:
    """
    Normaliza o clipe Kling, desacelera levemente e concatena ida+volta (boomerang).
    Tudo local — sem API.
    """
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},setpts={slowdown}*PTS,"
        f"split[v1][v2];[v2]reverse[vrev];[v1][vrev]concat=n=2:v=1:a=0"
    )
    cmd = [
        "ffmpeg", "-y", "-an", "-i", source_mp4,
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
        boom_mp4,
    ]
    ok, err = _run(cmd)
    if not ok:
        print(f"❌ FFmpeg boomerang falhou: {err}")
    return ok


def compose_video_with_overlay(
    video_mp4: str,
    overlay_png: str,
    audio_mp3: str,
    output_mp4: str,
    target_duration: float,
    width: int,
    height: int,
) -> bool:
    """Loop boomerang até a duração do áudio e aplica overlay PNG (cards estáticos)."""
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", video_mp4,
        "-loop", "1", "-i", overlay_png,
        "-i", audio_mp3,
        "-filter_complex",
        (
            f"[0:v]scale={width}:{height},fps=24,trim=duration={target_duration:.3f},"
            f"setpts=PTS-STARTPTS[vid];"
            f"[1:v]scale={width}:{height},format=rgba[ovr];"
            f"[vid][ovr]overlay=0:0:format=auto[vout]"
        ),
        "-map", "[vout]", "-map", "2:a:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{target_duration:.3f}",
        output_mp4,
    ]
    ok, err = _run(cmd)
    if not ok:
        print(f"❌ FFmpeg overlay+mux falhou: {err}")
    return ok


def compose_still_with_overlay(
    image_path: str,
    overlay_png: str,
    audio_mp3: str,
    output_mp4: str,
    target_duration: float,
    width: int,
    height: int,
    zoom_filter: str,
) -> bool:
    """Imagem estática com zoom orgânico + overlay — fallback sem Kling."""
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-loop", "1", "-i", overlay_png,
        "-i", audio_mp3,
        "-filter_complex",
        (
            f"[0:v]{zoom_filter},trim=duration={target_duration:.3f},setpts=PTS-STARTPTS[vid];"
            f"[1:v]scale={width}:{height},format=rgba[ovr];"
            f"[vid][ovr]overlay=0:0:format=auto[vout]"
        ),
        "-map", "[vout]", "-map", "2:a:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{target_duration:.3f}",
        output_mp4,
    ]
    ok, err = _run(cmd)
    if not ok:
        print(f"❌ FFmpeg still+overlay falhou: {err}")
    return ok


def compile_kling_pipeline(
    kling_raw: str,
    overlay_png: str,
    audio_mp3: str,
    output_mp4: str,
    boom_mp4: str,
    width: int,
    height: int,
    target_duration: float,
) -> bool:
    boom_dur = probe_duration(kling_raw) * 2 * 1.35
    print(
        f"🎬 Pipeline FFmpeg nativo: boomerang ~{boom_dur:.1f}s/ciclo → "
        f"destino {target_duration:.1f}s (sem extração JPEG)"
    )
    if not build_boomerang_video(kling_raw, boom_mp4, width, height):
        return False
    return compose_video_with_overlay(
        boom_mp4, overlay_png, audio_mp3, output_mp4,
        target_duration, width, height,
    )
