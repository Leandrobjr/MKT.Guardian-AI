"""Templates de composição por canal para a fábrica de mídia."""

from __future__ import annotations

from dataclasses import asdict, dataclass


Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class CompositionTemplate:
    template_id: str
    preset_id: str
    aspect_ratio: str
    safe_area: tuple[float, float, float, float]
    logo_anchor: str
    logo_margin: float
    logo_font_size: int
    headline_top: float
    headline_font_size: int
    headline_max_lines: int
    card_regions: tuple[Box, Box, Box]
    card_body_font_size: int
    cta_font_size: int
    colors: dict[str, tuple[int, int, int]]
    animation: str
    duration_seconds: int

    def to_dict(self) -> dict:
        data = asdict(self)
        data["safe_area"] = list(self.safe_area)
        data["card_regions"] = [list(region) for region in self.card_regions]
        return data


_TEMPLATES: dict[str, CompositionTemplate] = {
    "feed_quadrado": CompositionTemplate(
        template_id="guardian_feed_quadrado_v1",
        preset_id="feed_quadrado",
        aspect_ratio="1:1",
        safe_area=(0.06, 0.06, 0.06, 0.04),
        logo_anchor="top_left",
        logo_margin=0.045,
        logo_font_size=22,
        headline_top=0.065,
        headline_font_size=38,
        headline_max_lines=2,
        card_regions=(
            (0.04, 0.665, 0.96, 0.755),
            (0.04, 0.765, 0.845, 0.845),
            (0.04, 0.855, 0.96, 0.955),
        ),
        card_body_font_size=19,
        cta_font_size=20,
        colors={
            "headline": (255, 255, 255),
            "highlight": (251, 191, 36),
            "card": (15, 23, 42),
            "card_border": (30, 58, 95),
            "cta": (52, 211, 153),
            "cta_text": (11, 20, 36),
            "whatsapp": (37, 211, 102),
            "scrim": (6, 12, 24),
        },
        animation="imagem_estatica_sem_animacao",
        duration_seconds=0,
    ),
    "meta_reels": CompositionTemplate(
        template_id="guardian_meta_reels_v1",
        preset_id="meta_reels",
        aspect_ratio="9:16",
        safe_area=(0.06, 0.10, 0.06, 0.08),
        logo_anchor="top_left",
        logo_margin=0.045,
        logo_font_size=24,
        headline_top=0.055,
        headline_font_size=42,
        headline_max_lines=3,
        card_regions=(
            (0.04, 0.68, 0.96, 0.765),
            (0.04, 0.775, 0.96, 0.83),
            (0.04, 0.84, 0.96, 0.90),
        ),
        card_body_font_size=22,
        cta_font_size=22,
        colors={
            "headline": (255, 255, 255),
            "highlight": (251, 191, 36),
            "card": (15, 23, 42),
            "card_border": (30, 58, 95),
            "cta": (52, 211, 153),
            "cta_text": (11, 20, 36),
            "whatsapp": (37, 211, 102),
            "scrim": (6, 12, 24),
        },
        animation="movimento_sutil_e_leitura_pausada",
        duration_seconds=32,
    ),
    "shorts_urgente": CompositionTemplate(
        template_id="guardian_shorts_urgente_v1",
        preset_id="shorts_urgente",
        aspect_ratio="9:16",
        safe_area=(0.06, 0.08, 0.06, 0.10),
        logo_anchor="top_left",
        logo_margin=0.045,
        logo_font_size=24,
        headline_top=0.05,
        headline_font_size=44,
        headline_max_lines=2,
        card_regions=(
            (0.04, 0.61, 0.96, 0.705),
            (0.04, 0.715, 0.96, 0.775),
            (0.04, 0.785, 0.96, 0.88),
        ),
        card_body_font_size=21,
        cta_font_size=23,
        colors={
            "headline": (255, 255, 255),
            "highlight": (251, 191, 36),
            "card": (15, 23, 42),
            "card_border": (30, 58, 95),
            "cta": (52, 211, 153),
            "cta_text": (11, 20, 36),
            "whatsapp": (37, 211, 102),
            "scrim": (6, 12, 24),
        },
        animation="zoom_sutil_e_ritmo_urgente",
        duration_seconds=18,
    ),
}


def get_composition_template(preset_id: str) -> CompositionTemplate:
    """Retorna template conhecido, com fallback seguro para Reels."""
    return _TEMPLATES.get(preset_id, _TEMPLATES["meta_reels"])


def list_composition_templates() -> tuple[CompositionTemplate, ...]:
    return tuple(_TEMPLATES.values())
