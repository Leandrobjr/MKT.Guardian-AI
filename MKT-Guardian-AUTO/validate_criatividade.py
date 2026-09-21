#!/usr/bin/env python3
"""Validação rápida das Fases 1–11 — rodar antes da fábrica."""

import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from build_info import ORCHESTRATOR_VERSION, print_build_banner
from campaign_catalog import CAMPAIGN_STATUSES
from campaign_contract import CampaignContractCatalog, VALID_PUBLICO_SLUGS
from campaign_history import CampaignHistory
from composition_templates import list_composition_templates
from creative_brief import HeadlineRotator
from feedback_router import classify_improvement, detect_narrative_override
from scam_library import ScamLibrary
from visual_reference import VisualReferenceCatalog, validate_visual_reference
from visual_variety import VisualVarietyEngine
from visual_quality_audit import QUALITY_DIMENSIONS
from meta_publisher import MetaPublisher
from manual_export import export_tiktok_package
from supabase_campaign_bridge import SupabaseCampaignBridge
from campaign_command_worker import CampaignCommandWorker
from desktop_campaign_client import DesktopCampaignClient
from hybrid_tts import HybridTTSRouter


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
    print("VALIDACAO MKT GUARDIAN — CRIATIVIDADE (Fases 1-11)")
    print("=" * 60)
    print_build_banner(BASE)
    print(f"  Versao esperada: v5.11+ | Atual: v{ORCHESTRATOR_VERSION}")
    ok_all = True

    for rel in (
        "contexto_negocio/guardian_base.json",
        "contexto_negocio/golpes_whatsapp.json",
        "contexto_negocio/golpes_catalogo.json",
        "contexto_negocio/campanha_context_matrix.json",
        "contexto_negocio/copy_lexicon.json",
        "contexto_negocio/memoria/regras_linguisticas.json",
    ):
        try:
            with open(os.path.join(BASE, rel), encoding="utf-8") as f:
                json.load(f)
            ok_all &= check(f"JSON {rel}", True)
        except Exception as e:
            ok_all &= check(f"JSON {rel}", False, str(e))

    with open(os.path.join(BASE, "contexto_negocio/guardian_base.json"), encoding="utf-8") as f:
        ctx = json.load(f)
    with open(os.path.join(BASE, "contexto_negocio/copy_lexicon.json"), encoding="utf-8") as f:
        lexicon = json.load(f)
    proibidas = {
        p.lower()
        for item in lexicon.get("expressoes_proibidas", [])
        for p in item.get("padroes", [])
    }
    sugeridas = {
        item.get("usar", "").lower()
        for item in lexicon.get("expressoes_sugeridas", [])
        if item.get("usar")
    }
    ok_all &= check("Léxico: expressões proibidas", "chat privado" in proibidas)
    ok_all &= check("Léxico: expressões sugeridas", "mensagem no chat do whatsapp" in sugeridas)
    personas = ctx.get("PERSONAS_EXEMPLO", [])
    golpes = ctx.get("TIPOS_DE_GOLPE", [])
    ok_all &= check("Personas >= 24", len(personas) >= 24, f"{len(personas)} personas")
    novos = {"link_malicioso", "falso_emprego", "falso_investimento"}
    ids = {g.get("id") for g in golpes}
    ok_all &= check("Novos golpe_id Fase 4", novos.issubset(ids), str(novos & ids))

    lib = ScamLibrary(BASE)
    ok_all &= check("Variantes golpes >= 20", lib.count_variants() >= 20, str(lib.count_variants()))
    contract_catalog = CampaignContractCatalog(BASE)
    catalog_errors = contract_catalog.validate_catalog()
    ok_all &= check(
        "Catálogo canônico de golpes",
        len(contract_catalog._types) == 20 and not catalog_errors,
        f"{len(contract_catalog._types)} tipos, {len(contract_catalog._variant_to_type)} variantes",
    )
    ok_all &= check(
        "Sem fallback de público geral",
        lib.pick_variant("pix_fantasma", "geral") is None
        and "geral" not in VALID_PUBLICO_SLUGS,
        "seleção inválida bloqueada",
    )
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
    reference = VisualReferenceCatalog(ctx).pick(
        "pais", p, "sala brasileira organizada"
    ).to_dict()
    ok_all &= check(
        "Catálogo de referência visual",
        not validate_visual_reference(reference),
        reference.get("reference_id", ""),
    )
    templates = list_composition_templates()
    ok_all &= check(
        "Templates de composição por canal",
        len(templates) == 3 and all(len(item.card_regions) == 3 for item in templates),
        ", ".join(item.template_id for item in templates),
    )
    ok_all &= check(
        "Critérios de QA multimodal",
        len(QUALITY_DIMENSIONS) >= 10,
        f"{len(QUALITY_DIMENSIONS)} critérios",
    )
    ok_all &= check(
        "Narração híbrida",
        hasattr(HybridTTSRouter, "provider_order")
        and hasattr(HybridTTSRouter, "synthesize"),
        "Chirp para Meta + ElevenLabs para Shorts + fallback",
    )
    required_statuses = {
        "GERANDO",
        "AGUARDANDO_APROVACAO_HISTORIA",
        "PRODUZIDA",
        "AGUARDANDO_APROVACAO_FINAL",
        "APROVADA",
        "PRONTA_PARA_PUBLICAR",
        "PUBLICANDO",
        "PUBLICADA",
        "ERRO_PUBLICACAO",
        "REJEITADA",
    }
    ok_all &= check(
        "Catálogo e estados das Fases 8-9",
        required_statuses.issubset(set(CAMPAIGN_STATUSES)),
        f"{len(CAMPAIGN_STATUSES)} estados",
    )
    ok_all &= check(
        "Preflight de publicação Meta",
        hasattr(MetaPublisher, "preflight"),
        "token + permissões + conta profissional",
    )
    ok_all &= check(
        "Gate QA multimodal para publicação",
        hasattr(MetaPublisher, "_validate_qa_evidence"),
        "publicação sem evidência QA é bloqueada",
    )
    ok_all &= check(
        "Exportação manual TikTok",
        callable(export_tiktok_package),
        "sem publicação automática",
    )
    migration = os.path.join(
        BASE, "supabase", "migrations", "20260912125000_mkt_campaign_bridge.sql"
    )
    ok_all &= check(
        "Ponte Supabase Linux ↔ Desktop",
        os.path.isfile(migration)
        and hasattr(SupabaseCampaignBridge, "sync_campaign")
        and hasattr(SupabaseCampaignBridge, "claim_pending_commands"),
        "Storage privado + metadata + fila de comandos",
    )
    ok_all &= check(
        "Worker Linux da fila",
        hasattr(CampaignCommandWorker, "run_once")
        and hasattr(CampaignCommandWorker, "process_command"),
        "dry-run padrão + execução Meta controlada",
    )
    ok_all &= check(
        "Cliente Desktop Supabase",
        hasattr(DesktopCampaignClient, "list_campaigns")
        and hasattr(DesktopCampaignClient, "request_publication")
        and hasattr(DesktopCampaignClient, "create_asset_url"),
        "leitura + confirmação + URL temporária",
    )
    desktop_files = (
        "desktop/index.html",
        "desktop/styles.css",
        "desktop/app.js",
        "desktop/README.md",
    )
    desktop_js = ""
    try:
        with open(os.path.join(BASE, "desktop", "app.js"), encoding="utf-8") as file:
            desktop_js = file.read()
    except OSError:
        pass
    ok_all &= check(
        "Interface Desktop",
        all(os.path.isfile(os.path.join(BASE, item)) for item in desktop_files)
        and "SUPABASE_SERVICE_ROLE_KEY" not in desktop_js
        and "localStorage" not in desktop_js,
        "login + preview + confirmação sem service_role",
    )

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
