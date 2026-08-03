"""Guardião lexical da copy — regras bloqueantes e substituições canônicas."""

from __future__ import annotations

import json
import os
import re
from typing import Any


COPY_FIELDS = (
    "gancho_atencao_inicial",
    "desenvolvimento_copy",
    "chamada_para_acao_cta",
    "texto_card_notificacao",
    "frase_destaque_golpista",
    "texto_card_solucao",
    "publico_alvo_icp",
    "direcao_arte_emocional",
    "genero_personagem_visual",
)


class CopyLexicon:
    """Carrega o léxico canônico e aplica as regras de linguagem da campanha."""

    def __init__(self, base_dir: str):
        self.path = os.path.join(base_dir, "contexto_negocio", "copy_lexicon.json")
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _prohibited(self) -> list[dict[str, Any]]:
        return self.data.get("expressoes_proibidas", [])

    def _substitutions(self) -> list[dict[str, str]]:
        return self.data.get("substituicoes_automaticas", [])

    def scan_violations(self, text: str) -> list[dict[str, str]]:
        """Retorna as expressões proibidas encontradas no texto."""
        violations: list[dict[str, str]] = []
        for item in self._prohibited():
            for pattern in item.get("padroes", []):
                match = re.search(re.escape(pattern), text or "", flags=re.IGNORECASE)
                if match:
                    violations.append(
                        {
                            "id": str(item.get("id", "")),
                            "expressao": match.group(0),
                            "padrao": pattern,
                            "motivo": str(item.get("motivo", "")),
                            "severidade": str(item.get("severidade", "bloqueante")),
                        }
                    )
                    break
        return violations

    def apply_substitutions(self, text: str) -> str:
        """Aplica substituições literais, preservando o restante da copy."""
        result = text or ""
        for item in self._substitutions():
            pattern = item.get("padrao", "")
            replacement = item.get("substituto", "")
            if pattern and replacement:
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    def sanitize_creative(self, creative_data: dict) -> tuple[dict, list[dict[str, str]]]:
        """Sanitiza campos textuais e retorna violações remanescentes."""
        for field in COPY_FIELDS:
            value = creative_data.get(field)
            if isinstance(value, str) and value:
                creative_data[field] = self.apply_substitutions(value)

        violations: list[dict[str, str]] = []
        for field in COPY_FIELDS:
            value = creative_data.get(field)
            if isinstance(value, str):
                for violation in self.scan_violations(value):
                    violations.append({**violation, "campo": field})
        return creative_data, violations

    def is_compliant(self, creative_data: dict) -> bool:
        _, violations = self.sanitize_creative(dict(creative_data))
        return not violations

    def format_for_prompt(self) -> str:
        """Renderiza o léxico para inclusão no prompt do agente criador."""
        lines = ["LÉXICO CANÔNICO DA COPY — OBRIGATÓRIO:"]
        lines.append("EXPRESSÕES PROIBIDAS:")
        for item in self._prohibited():
            patterns = ", ".join(f'"{p}"' for p in item.get("padroes", []))
            lines.append(f"- {patterns}")
        lines.append("EXPRESSÕES SUGERIDAS:")
        for item in self.data.get("expressoes_sugeridas", []):
            lines.append(f"- {item.get('usar', '')}")
        return "\n".join(lines)
