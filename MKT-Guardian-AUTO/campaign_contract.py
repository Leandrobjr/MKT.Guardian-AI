"""Contrato determinístico para validar campanhas antes da geração de mídia."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from campaign_coherence import (
    _gender_from_personagem_field,
    _gender_from_roteiro,
    infer_recipient_gender,
    is_ambiguous_pix_headline,
    is_coherent_for_campaign,
    is_recipient_role_coherent,
)

VALID_PUBLICO_SLUGS = frozenset({"massa", "idosos", "pais", "empresarios", "escolas"})
PUBLICO_ID_BY_SLUG = {
    "massa": "massa",
    "idosos": "idosos",
    "pais": "pais",
    "empresarios": "profissionais",
    "escolas": "escolas",
}

LEGACY_GOLPE_GROUPS = {
    "pix_fantasma": {
        "falso_pix_familiar",
        "engenharia_social_urgencia",
        "boleto_falso",
        "qr_code_pix",
        "falsa_cobranca_empresarial",
    },
    "falso_parente": {"falso_pix_familiar", "voz_clonada"},
    "clonagem_whatsapp": {"clonagem_whatsapp", "confirmacao_codigo"},
    "falsa_central": {"falso_suporte_bancario"},
    "grooming": {"grooming"},
    "phishing": {"link_malicioso", "catalogo_falso_produto", "falso_sorteio"},
    "link_malicioso": {"link_malicioso", "malware_apk", "falsa_encomenda"},
    "falso_emprego": {"falso_emprego"},
    "falso_investimento": {"falso_investimento"},
}


@dataclass(frozen=True)
class CampaignContract:
    publico_slug: str
    golpe_id: str
    variant_id: str
    canonical_type_id: str
    frase_golpista: str
    allowed_publicos: frozenset[str]
    protagonista_gender: str = ""
    mecanismo: str = ""
    consequencia: str = ""
    termos_proibidos: tuple[str, ...] = ()
    recipient_gender: str = ""

    @property
    def combo_key(self) -> str:
        return f"{self.publico_slug}+{self.golpe_id}"


class CampaignContractError(ValueError):
    """Erro de configuração que deve bloquear a campanha antes das APIs."""


class CampaignContractCatalog:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self._catalog = self._load_json("contexto_negocio/golpes_catalogo.json")
        self._variants = self._load_json("contexto_negocio/golpes_whatsapp.json").get(
            "variantes", []
        )
        self._types = {
            item.get("id", ""): item for item in self._catalog.get("tipos", [])
        }
        self._variant_to_type = {
            variant_id: item
            for item in self._types.values()
            for variant_id in item.get("variantes", [])
        }
        self._variant_data = {
            item.get("variant_id", ""): item for item in self._variants
        }

    def _load_json(self, relative_path: str) -> dict:
        path = os.path.join(self.base_dir, relative_path)
        try:
            with open(path, encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise CampaignContractError(f"Catálogo inválido: {path}: {exc}") from exc

    def canonical_type_for_variant(self, variant_id: str) -> dict:
        return dict(self._variant_to_type.get(variant_id) or {})

    def variant_for_id(self, variant_id: str) -> dict:
        return dict(self._variant_data.get(variant_id) or {})

    def variant_ids_for_golpe(self, golpe_id: str) -> frozenset[str]:
        canonical_ids = LEGACY_GOLPE_GROUPS.get(golpe_id, set())
        return frozenset(
            variant_id
            for variant_id, canonical_type in self._variant_to_type.items()
            if canonical_type.get("id") in canonical_ids
        )

    def validate_catalog(self) -> list[str]:
        errors: list[str] = []
        if not self._types:
            return ["Catálogo canônico sem tipos de golpe."]
        variant_types: dict[str, list[str]] = {}
        for canonical_type in self._types.values():
            for variant_id in canonical_type.get("variantes", []):
                variant_types.setdefault(variant_id, []).append(
                    canonical_type.get("id", "")
                )
                mapped_type = self._variant_to_type.get(variant_id, {})
                current_type = canonical_type.get("id", "")
                if mapped_type and mapped_type.get("id") != current_type:
                    errors.append(
                        f"Variante {variant_id!r} mapeada para dois tipos: "
                        f"{mapped_type.get('id')} e {current_type}."
                    )
        for variant_id, type_ids in variant_types.items():
            if len(type_ids) > 1:
                errors.append(
                    f"Variante {variant_id!r} declarada em tipos canônicos múltiplos: "
                    f"{', '.join(type_ids)}."
                )
        for variant_id, canonical_type in self._variant_to_type.items():
            if variant_id not in self._variant_data:
                errors.append(
                    f"Variante {variant_id!r} não existe em golpes_whatsapp.json."
                )
            if not canonical_type.get("publicos"):
                errors.append(f"Tipo canônico {canonical_type.get('id')!r} sem públicos.")
            variant = self._variant_data.get(variant_id) or {}
            operational_id = str(variant.get("golpe_id") or "").strip()
            canonical_id = canonical_type.get("id", "")
            valid_operational_ids = {canonical_id}
            valid_operational_ids.update(
                alias
                for alias, canonical_ids in LEGACY_GOLPE_GROUPS.items()
                if canonical_id in canonical_ids
            )
            if operational_id and operational_id not in valid_operational_ids:
                errors.append(
                    f"Variante {variant_id!r} usa golpe_id operacional "
                    f"{operational_id!r}, incompatível com {canonical_id!r}."
                )
            extra_publicos = set(variant.get("publicos") or []) - set(
                canonical_type.get("publicos") or []
            )
            if extra_publicos:
                errors.append(
                    f"Variante {variant_id!r} declara públicos fora do tipo canônico: "
                    f"{', '.join(sorted(extra_publicos))}."
                )
        return errors

    def build(
        self,
        config: dict,
        campaign_ctx: dict,
        protagonista_gender: str = "",
    ) -> CampaignContract:
        publico_slug = str(config.get("publico_slug") or "").strip()
        golpe_id = str(config.get("golpe_id") or "").strip()
        variant_id = str(campaign_ctx.get("scam_variant_id") or "").strip()
        frase = str(campaign_ctx.get("frase_golpista") or "").strip()

        errors: list[str] = []
        if publico_slug not in VALID_PUBLICO_SLUGS:
            errors.append(
                f"Público inválido {publico_slug!r}; use um slug canônico, nunca 'geral'."
            )
        if not golpe_id:
            errors.append("golpe_id ausente.")
        expected_publico_id = PUBLICO_ID_BY_SLUG.get(publico_slug)
        configured_publico_id = str(config.get("publico_id") or "").strip()
        if (
            expected_publico_id
            and configured_publico_id
            and configured_publico_id != expected_publico_id
        ):
            errors.append(
                f"publico_id {configured_publico_id!r} diverge do público {publico_slug!r}."
            )
        if not variant_id:
            errors.append(
                f"Nenhuma variante compatível para {publico_slug}+{golpe_id}."
            )

        canonical_type = self.canonical_type_for_variant(variant_id)
        variant = self.variant_for_id(variant_id)
        if variant_id and not canonical_type:
            errors.append(f"Variante {variant_id!r} não está no catálogo canônico.")
        if variant_id and not variant:
            errors.append(f"Variante {variant_id!r} não está na biblioteca operacional.")

        canonical_id = canonical_type.get("id", "")
        allowed_publicos = frozenset(canonical_type.get("publicos") or [])
        if publico_slug and allowed_publicos and publico_slug not in allowed_publicos:
            errors.append(
                f"Variante {variant_id!r} não é permitida para o público {publico_slug!r}."
            )
        variant_publicos = frozenset(variant.get("publicos") or [])
        if publico_slug and variant_publicos and publico_slug not in variant_publicos:
            errors.append(
                f"Variante {variant_id!r} não declara compatibilidade operacional "
                f"com o público {publico_slug!r}."
            )
        allowed_legacy = LEGACY_GOLPE_GROUPS.get(golpe_id, set())
        if canonical_id and allowed_legacy and canonical_id not in allowed_legacy:
            errors.append(
                f"Variante {variant_id!r} ({canonical_id}) não pertence ao golpe "
                f"selecionado {golpe_id!r}."
            )
        if not frase:
            errors.append("A variante selecionada não possui frase_golpista.")
        if frase and not is_recipient_role_coherent(frase, publico_slug, golpe_id):
            errors.append(
                "Vocativo da mensagem é incompatível com o público e o tipo de golpe."
            )
        recipient_gender = infer_recipient_gender(frase)
        if (
            recipient_gender
            and protagonista_gender in ("feminino", "masculino")
            and recipient_gender != protagonista_gender
        ):
            errors.append(
                f"Vocativo da mensagem indica protagonista {recipient_gender}, "
                f"mas o casting foi definido como {protagonista_gender}."
            )

        if errors:
            raise CampaignContractError(" | ".join(errors))

        return CampaignContract(
            publico_slug=publico_slug,
            golpe_id=golpe_id,
            variant_id=variant_id,
            canonical_type_id=canonical_id,
            frase_golpista=frase,
            allowed_publicos=allowed_publicos,
            protagonista_gender=protagonista_gender
            if protagonista_gender in ("feminino", "masculino")
            else "",
            mecanismo=str(canonical_type.get("mecanismo") or ""),
            consequencia=str(canonical_type.get("consequencia") or ""),
            termos_proibidos=tuple(canonical_type.get("termos_proibidos") or ()),
            recipient_gender=recipient_gender,
        )


def _gender_cues(text: str) -> set[str]:
    normalized = (text or "").lower()
    cues: set[str] = set()
    if re.search(r"\b(ela|dela|dona|senhora|idosa|aposentada)\b", normalized):
        cues.add("feminino")
    if re.search(r"\b(ele|dele|senhor|idoso|aposentado)\b", normalized):
        cues.add("masculino")
    if re.match(r"\s*['\"“”‘’]?\s*(mãe|mae|vó|avó|vovó)\b", normalized):
        cues.add("feminino")
    if re.match(r"\s*['\"“”‘’]?\s*(pai|vô|avô|vovô)\b", normalized):
        cues.add("masculino")
    return cues


def validate_creative_contract(
    creative_data: dict,
    contract: CampaignContract,
    expected_gender: str = "",
    expected_persona: dict | None = None,
) -> list[str]:
    errors: list[str] = []
    card = str(creative_data.get("texto_card_notificacao") or "").strip()
    roteiro = str(creative_data.get("desenvolvimento_copy") or "").strip()
    headline = str(creative_data.get("gancho_atencao_inicial") or "").strip()
    personagem = str(creative_data.get("genero_personagem_visual") or "").strip()
    declared_gender = str(creative_data.get("protagonista_genero") or "").strip().lower()
    rendered_publico = str(creative_data.get("publico_slug") or "").strip()
    rendered_publico_id = str(creative_data.get("publico_id") or "").strip()
    expected_publico_id = PUBLICO_ID_BY_SLUG.get(contract.publico_slug, "")
    rendered_persona = creative_data.get("persona_visual") or {}

    if rendered_publico and rendered_publico != contract.publico_slug:
        errors.append("Público renderizado diverge do público contratado.")
    if rendered_publico_id and expected_publico_id and rendered_publico_id != expected_publico_id:
        errors.append("ID do público renderizado diverge do público contratado.")
    if (
        isinstance(rendered_persona, dict)
        and rendered_persona.get("publico_id")
        and rendered_persona["publico_id"] != expected_publico_id
    ):
        errors.append("Persona visual pertence a outro público.")
    age = rendered_persona.get("idade") if isinstance(rendered_persona, dict) else None
    if age is None:
        age = creative_data.get("protagonista_idade")
    if isinstance(age, (int, float)):
        age_ranges = {
            "idosos": (65, 85),
            "pais": (35, 50),
            "empresarios": (35, 55),
            "escolas": (40, 55),
        }
        age_range = age_ranges.get(contract.publico_slug)
        if age_range and not age_range[0] <= age <= age_range[1]:
            errors.append(
                f"Idade {age} incompatível com o público {contract.publico_slug}."
            )

    if card.casefold() != contract.frase_golpista.casefold():
        errors.append("Card golpista diferente da frase da variante selecionada.")
    if is_ambiguous_pix_headline(headline):
        errors.append(
            "Headline ambígua: parece atribuir à vítima a prática do golpe de PIX."
        )
    narrative = f"{headline} {roteiro}".casefold()
    for forbidden_claim in contract.termos_proibidos:
        if forbidden_claim.casefold() in narrative:
            errors.append(
                f"Copy atribui ao mecanismo {contract.mecanismo} uma consequência incorreta: "
                f"{forbidden_claim}."
            )
    if not is_coherent_for_campaign(
        roteiro,
        contract.frase_golpista,
        headline,
        contract.canonical_type_id,
    ):
        errors.append(
            f"Roteiro/headline não correspondem ao pretexto da variante {contract.variant_id}."
        )

    gender = expected_gender or contract.protagonista_gender
    if gender:
        roteiro_gender = _gender_from_roteiro(roteiro)
        personagem_gender = _gender_from_personagem_field(personagem.lower())
        headline_cues = _gender_cues(headline)
        if roteiro_gender and roteiro_gender != gender:
            errors.append("Gênero do protagonista no roteiro diverge do contrato.")
        if personagem_gender and personagem_gender != gender:
            errors.append("Gênero do personagem visual diverge do contrato.")
        if len(headline_cues) > 1 or (headline_cues and gender not in headline_cues):
            errors.append("Gênero indicado na headline diverge do protagonista.")
        if roteiro_gender and personagem_gender and roteiro_gender != personagem_gender:
            errors.append("Roteiro e personagem visual possuem gêneros diferentes.")
        if declared_gender and declared_gender != gender:
            errors.append("Gênero declarado do protagonista diverge do contrato.")

    if expected_persona:
        expected_name = str(expected_persona.get("nome") or "").split()[0].strip()
        declared_name = str(creative_data.get("protagonista_nome") or "").strip()
        expected_persona_id = str(expected_persona.get("persona_id") or "").strip()
        rendered_persona_id = str(creative_data.get("persona_id") or "").strip()
        if expected_name and expected_name.casefold() not in roteiro.casefold():
            errors.append(
                f"O roteiro não nomeia o protagonista contratado ({expected_name})."
            )
        expected_full_name = str(expected_persona.get("nome") or "").strip()
        if (
            declared_name
            and expected_name
            and declared_name.casefold()
            not in {expected_name.casefold(), expected_full_name.casefold()}
        ):
            errors.append("Nome declarado do protagonista diverge do casting contratado.")
        if expected_persona_id and rendered_persona_id != expected_persona_id:
            errors.append("Persona visual renderizada diverge do casting contratado.")
        if gender and rendered_persona.get("genero") and rendered_persona["genero"] != gender:
            errors.append("Gênero da persona visual diverge do contrato.")

    return errors
