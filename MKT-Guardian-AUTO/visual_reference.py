"""Catálogo de referências visuais aprováveis para casting de campanhas."""

from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class VisualReference:
    reference_id: str
    publico_slug: str
    persona_id: str
    vestuario: str
    ambiente: str
    iluminacao: str
    enquadramento: str
    paleta: str
    estilo_fotografico: str
    aceito: tuple[str, ...]
    rejeitado: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["aceito"] = list(self.aceito)
        data["rejeitado"] = list(self.rejeitado)
        return data


class VisualReferenceCatalog:
    """Combina persona, ambiente e direção de arte sem repetir referência recente."""

    DEFAULT_SHOTS = (
        (
            "plano médio documental, lente 50mm, protagonista e celular inteiro "
            "visíveis com margem em todas as bordas"
        ),
        (
            "ângulo over-the-shoulder com celular e tela inteiros dentro do quadro, "
            "sem corte nas bordas"
        ),
        (
            "close natural nas mãos segurando o celular inteiro acima do terço inferior, "
            "rosto parcialmente visível"
        ),
        (
            "plano três-quartos espontâneo, protagonista sem olhar para a câmera, "
            "celular inteiro na altura do peito"
        ),
        (
            "plano de cintura, celular inteiro na altura do peito, composição limpa, "
            "sem mockup ampliado ou tela cortada"
        ),
    )
    DEFAULT_LIGHTING = (
        "luz natural quente da janela pela esquerda",
        "luz natural difusa e exposição uniforme",
        "luz suave de fim de tarde filtrada por cortinas",
        "luz interna neutra combinada com janela",
    )

    def __init__(
        self,
        context_data: dict,
        recent_reference_ids: set[str] | None = None,
        shot_variants: tuple[str, ...] | list[str] | None = None,
        lighting_variants: tuple[str, ...] | list[str] | None = None,
    ):
        self.context_data = context_data
        self.recent_reference_ids = recent_reference_ids or set()
        self.shot_variants = tuple(shot_variants or self.DEFAULT_SHOTS)
        self.lighting_variants = tuple(lighting_variants or self.DEFAULT_LIGHTING)

    def _palette(self) -> str:
        colors = self.context_data.get("IDENTIDADE_VISUAL_MARCA", {}).get("cores", {})
        navy = colors.get("fundo_navy", "#0B1424")
        green = colors.get("verde_destaque", "#34D399")
        return (
            f"neutros naturais e tons de pele realistas; navy {navy} e verde {green} "
            "somente em interface, cards e detalhes da marca"
        )

    def _accepted(self) -> tuple[str, ...]:
        visual = self.context_data.get("DIRETRIZES_VISUAIS", {})
        rules = visual.get("regras_obrigatorias") or []
        return tuple(
            [
                "brasileiro bem apresentado, cabelo e roupa cuidados",
                "ambiente pintado, organizado e de classe média cotidiana",
                "rosto, mãos e celular inteiros na área segura superior",
                *[str(rule) for rule in rules[:4]],
            ]
        )

    def _rejected(self) -> tuple[str, ...]:
        visual = self.context_data.get("DIRETRIZES_VISUAIS", {})
        rules = visual.get("proibicoes") or []
        return tuple(
            [
                "estética de pobreza extrema, roupa rasgada ou ambiente sujo",
                "mansão, luxo artificial, hacker genérico ou fundo tecnológico abstrato",
                "rosto, mãos ou celular deformados",
                *[str(rule) for rule in rules[:8]],
            ]
        )

    def _reference_id(
        self,
        publico_slug: str,
        persona_id: str,
        ambiente: str,
        shot: str,
        lighting: str,
    ) -> str:
        raw = "|".join((publico_slug, persona_id, ambiente, shot, lighting))
        return "ref_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

    def pick(
        self,
        publico_slug: str,
        persona: dict,
        ambiente: str,
    ) -> VisualReference:
        persona_id = str(persona.get("persona_id") or "persona_geral")
        wardrobe = str(
            persona.get("estilo_vestuario")
            or "camisa ou blusa casual limpa, jeans ou calça chino"
        )
        style = str(
            self.context_data.get("DIRETRIZES_VISUAIS", {}).get(
                "estilo_fotografico",
                "fotografia documental realista brasileira",
            )
        )
        candidates: list[VisualReference] = []
        for shot in self.shot_variants:
            for lighting in self.lighting_variants:
                reference_id = self._reference_id(
                    publico_slug, persona_id, ambiente, shot, lighting
                )
                candidates.append(
                    VisualReference(
                        reference_id=reference_id,
                        publico_slug=publico_slug,
                        persona_id=persona_id,
                        vestuario=wardrobe,
                        ambiente=ambiente,
                        iluminacao=lighting,
                        enquadramento=shot,
                        paleta=self._palette(),
                        estilo_fotografico=style,
                        aceito=self._accepted(),
                        rejeitado=self._rejected(),
                    )
                )
        fresh = [item for item in candidates if item.reference_id not in self.recent_reference_ids]
        return random.choice(fresh or candidates)


def validate_visual_reference(reference: dict[str, Any]) -> list[str]:
    required = (
        "reference_id",
        "persona_id",
        "vestuario",
        "ambiente",
        "iluminacao",
        "enquadramento",
        "paleta",
        "estilo_fotografico",
    )
    errors = [f"Campo ausente: {field}" for field in required if not reference.get(field)]
    if not reference.get("aceito"):
        errors.append("Catálogo sem critérios de aceitação.")
    if not reference.get("rejeitado"):
        errors.append("Catálogo sem critérios de rejeição.")
    return errors
