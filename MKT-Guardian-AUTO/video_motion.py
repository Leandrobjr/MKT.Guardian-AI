"""Sequenciamento de frames para movimento menos repetitivo nos vídeos."""

from __future__ import annotations

import random


def _pingpong_cycle(n: int) -> list[int]:
    """0,1,...,n-1,n-2,...,1,0 — evita salto brusco ao reiniciar."""
    if n <= 0:
        return [0]
    if n == 1:
        return [0]
    return list(range(n)) + list(range(n - 2, -1, -1))


def build_natural_frame_sequence(
    frame_count: int,
    needed: int,
    *,
    thin_step: int | None = None,
    hold_at_turns: int = 2,
    seed: int | None = None,
) -> list[int]:
    """
    Monta índices de frames para playback natural:
    - ping-pong (ida e volta) em vez de loop seco
    - amostragem mais espaçada em clipes longos (movimento mais calmo)
    - pausa leve nas reversões de direção
    - fase aleatória por campanha (ciclos não alinhados)
    """
    if frame_count <= 0:
        return [0] * needed
    if frame_count == 1:
        return [0] * needed

    rng = random.Random(seed)

    step = thin_step
    if step is None:
        step = 2 if frame_count > 70 else 1
    base = list(range(0, frame_count, step))
    if len(base) < 2:
        base = list(range(frame_count))

    cycle = _pingpong_cycle(len(base))
    phase = rng.randint(0, len(cycle) - 1)
    cycle = cycle[phase:] + cycle[:phase]

    turn_positions = {0, len(cycle) // 2}
    seq: list[int] = []
    ci = 0
    while len(seq) < needed:
        pos = ci % len(cycle)
        mapped = base[cycle[pos]]
        repeats = hold_at_turns if pos in turn_positions else 1
        for _ in range(repeats):
            if len(seq) >= needed:
                break
            seq.append(mapped)
        ci += 1

    return seq[:needed]


def motion_prompt_suffix() -> str:
    """Instruções para a Kling gerar movimento mais documental e menos repetitivo."""
    return (
        "Documentary camera almost static on tripod, very subtle natural motion only: "
        "light breathing, slight blink, minimal hand movement. "
        "Avoid repetitive gestures, avoid looping actions, avoid exaggerated animation."
    )


def still_video_zoom_filter(width: int, height: int, total_frames: int, fps: int = 25) -> str:
    """Ken Burns orgânico (zoom/pan oscilante) — não linear e repetitivo."""
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
        f"zoompan="
        f"z='1.02+0.028*sin(2*PI*on/{max(total_frames, 1)})'"
        f":x='iw/2-(iw/zoom/2)+12*sin(2*PI*on/{max(total_frames * 2, 1)})'"
        f":y='ih/2-(ih/zoom/2)+8*cos(2*PI*on/{max(total_frames * 3, 1)})'"
        f":d={total_frames}:s={width}x{height}:fps={fps}"
    )
