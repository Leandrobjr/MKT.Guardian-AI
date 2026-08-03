#!/usr/bin/env python3
"""Administração das regras linguísticas globais do Guardian AI."""

from __future__ import annotations

import argparse
import os
import re
import sys

from agent_memory import AgentMemory


BASE = os.path.dirname(os.path.abspath(__file__))


def _rule_id(expression: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", expression.lower()).strip("_")
    return f"admin_{normalized[:48]}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", default=BASE, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("listar", help="Lista as regras linguísticas ativas.")

    prohibited = sub.add_parser("add-proibida", help="Adiciona uma expressão proibida.")
    prohibited.add_argument("expressao")
    prohibited.add_argument("--usar", default="", help="Expressão substituta.")
    prohibited.add_argument("--motivo", default="Regra definida pelo administrador.")
    prohibited.add_argument("--id", default="")

    suggested = sub.add_parser("add-sugerida", help="Adiciona uma expressão sugerida.")
    suggested.add_argument("expressao")
    suggested.add_argument("--motivo", default="Expressão preferida pelo administrador.")
    suggested.add_argument("--id", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    memory = AgentMemory(args.base_dir)

    if args.command == "listar":
        rules = memory.regras_linguisticas()
        if not rules:
            print("Nenhuma regra linguística ativa.")
            return 0
        for rule in rules:
            prefix = "[PROIBIDA]" if rule.get("tipo") == "proibida" else "[SUGERIDA]"
            replacement = f" → {rule.get('usar')}" if rule.get("usar") else ""
            print(f"{prefix} {rule.get('id')}: {rule.get('expressao')}{replacement}")
        return 0

    expression = args.expressao.strip()
    if not expression:
        print("ERRO: A expressão não pode ser vazia.")
        return 2
    rule_id = args.id.strip() or _rule_id(expression)
    if args.command == "add-proibida":
        added = memory.registrar_regra_linguistica(
            rule_id,
            "proibida",
            expression,
            args.usar.strip(),
            args.motivo.strip(),
            origem="lexicon_admin",
        )
    else:
        added = memory.registrar_regra_linguistica(
            rule_id,
            "sugerida",
            expression,
            expression,
            args.motivo.strip(),
            origem="lexicon_admin",
        )
    if not added:
        print(f"AVISO: Regra já existente: {rule_id}")
        return 0
    print(f"OK: Regra adicionada: {rule_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
