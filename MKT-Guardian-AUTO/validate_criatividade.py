#!/usr/bin/env python3
"""Validação rápida das Fases 1–5 (criatividade) — rodar antes da fábrica."""

import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from build_info import ORCHESTRATOR_VERSION, print_build_banner
from campaign_history import CampaignHistory
from creative_brief import HeadlineRotator
from feedback_router import classify_improvement, detect_narrative_override
from scam_library import ScamLibrary
from visual_variety import VisualVarietyEngine


def check(name: str, ok: bool, detail: str = "") -> bool:
    mark = "OK" if ok else "FALHA"
    line = f"  [{mark}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return ok


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print("=" * 60)
    print("VALIDACAO MKT GUARDIAN — CRIATIVIDADE (Fases 1-5)")
    print("=" * 60)
    print_build_banner(BASE)
    print(f"  Versao esperada: v5.4+ | Atual: v{ORCHESTRATOR_VERSION}")
    ok_all = True

    for rel in (
        "contexto_negocio/guardian_base.json",
        "contexto_negocio/golpes_whatsapp.json",
        "contexto_negocio/campanha_context_matrix.json",
    ):
        try:
            with open(os.path.join(BASE, rel), encoding="utf-8") as f:
                json.load(f)
            ok_all &= check(f"JSON {rel}", True)
        except Exception as e:
            ok_all &= check(f"JSON {rel}", False, str(e))

    with open(os.path.join(BASE, "contexto_negocio/guardian_base.json"), encoding="utf-8") as f:
        ctx = json.load(f)
    personas = ctx.get("PERSONAS_EXEMPLO", [])
    golpes = ctx.get("TIPOS_DE_GOLPE", [])
    ok_all &= check("Personas >= 24", len(personas) >= 24, f"{len(personas)} personas")
    novos = {"link_malicioso", "falso_emprego", "falso_investimento"}
    ids = {g.get("id") for g in golpes}
    ok_all &= check("Novos golpe_id Fase 4", novos.issubset(ids), str(novos & ids))

    lib = ScamLibrary(BASE)
        ok_all &= check("Variantes golpes >= 20", lib.count_variants() >= 20, str(lib.count_variants()))
        emp = lib.pick_variant("link_malicioso", "empresarios")
        emp_vid = (emp or {}).get("variant_id", "")
        emp_frase = ((emp or {}).get("frase_golpista") or "").lower()
        ok_all &= check(
            "Variante B2B empresarios",
            bool(emp and ("b2b" in emp_vid or "fornecedor" in emp_vid or "fornecedor" in emp_frase)),
            emp_vid,
        )

    hist = CampaignHistory(BASE)
    ve = VisualVarietyEngine(BASE, hist)
    rot = HeadlineRotator(BASE, hist)
    ok_all &= check("CampaignHistory", hist is not None)
    ok_all &= check("VisualVarietyEngine", ve is not None)
    ok_all &= check("HeadlineRotator", rot is not None)

    p = ve.pick_persona(ctx, "pais", "pais")
    ok_all &= check("Casting persona", bool(p.get("persona_id")), p.get("persona_id", ""))

    v = lib.pick_variant("falso_emprego", "massa")
    ok_all &= check("ScamLibrary pick", bool(v and v.get("frase_golpista")), (v or {}).get("variant_id", ""))

    plan = classify_improvement("Quero estoria de escola com diretor")
    ok_all &= check("Feedback narrativa", plan.get("primary_category") == "narrativa")
    ov = detect_narrative_override("Quero estoria de escola com diretor")
    ok_all &= check("Override escolas", ov.get("publico_slug") == "escolas")

    plan_h = classify_improvement("Mudar so a manchete headline")
    ok_all &= check("Feedback headline_only", plan_h.get("headline_only") is True)

    print()
    if ok_all:
        print("RESULTADO: TUDO OK — pode rodar campaign_orchestrator.py na fabrica.")
        return 0
    print("RESULTADO: FALHAS DETECTADAS — corrija antes de produzir campanhas.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
