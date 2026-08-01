#!/usr/bin/env python3
"""
Republica campanha já gerada — sem regerar vídeo/copy.

Uso:
  python3 publicar_campanha.py              # última aprovada ou mp4 mais recente
  python3 publicar_campanha.py --listar     # lista candidatos
  python3 publicar_campanha.py --basename 003_massas_reels_20260801
  python3 publicar_campanha.py --asset output_campanha/arquivo.mp4
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from env_loader import load_project_env

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "output_campanha"
APROVADOS = BASE / "contexto_negocio" / "memoria" / "aprovados.jsonl"
HASHTAGS = "#guardianai #segurancadigital #golpewhatsapp #whatsapp #pix #golpe"
URL = "https://guardian-ai.app"


def _load_aprovados() -> list[dict]:
    if not APROVADOS.is_file():
        return []
    rows: list[dict] = []
    with open(APROVADOS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _resolve_asset(path: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = BASE / p
    p = p.resolve()
    if p.is_file():
        return str(p)
    for ext in (".mp4", ".jpg"):
        cand = OUTPUT / f"{path}{ext}" if not path.endswith(ext) else p
        if cand.is_file():
            return str(cand.resolve())
    raise FileNotFoundError(f"Asset não encontrado: {path}")


def _pick_from_basename(basename: str) -> tuple[str, str]:
    for ext in (".mp4", ".jpg"):
        cand = OUTPUT / f"{basename}{ext}"
        if cand.is_file():
            return str(cand.resolve()), basename
    raise FileNotFoundError(f"Nenhum arquivo para basename '{basename}' em output_campanha/")


def _pick_latest_mp4() -> tuple[str, str]:
    mp4s = sorted(OUTPUT.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not mp4s:
        raise FileNotFoundError("Nenhum .mp4 em output_campanha/")
    p = mp4s[0]
    return str(p.resolve()), p.stem


def _pick_last_approved() -> tuple[str, str, str]:
    """Retorna (asset_path, basename, headline)."""
    for row in reversed(_load_aprovados()):
        asset = (row.get("asset") or "").strip()
        headline = (row.get("headline") or "").strip()
        basename = (row.get("basename") or "").strip()
        if asset:
            try:
                path = _resolve_asset(asset)
                return path, basename or Path(path).stem, headline
            except FileNotFoundError:
                continue
        if basename:
            try:
                path, stem = _pick_from_basename(basename)
                return path, stem, headline
            except FileNotFoundError:
                continue
    raise FileNotFoundError(
        "Nenhum registro em aprovados.jsonl com arquivo existente. "
        "Use --asset ou --basename."
    )


def _montar_caption(headline: str, copy: str = "") -> str:
    h = headline.strip() or "Proteja-se no WhatsApp com Guardian AI"
    body = copy.strip() if copy else (
        "Golpes no WhatsApp estão mais frequentes. "
        "O Guardian AI detecta e bloqueia ameaças em tempo real."
    )
    return f"{h}\n\n{body[:800]}\n\nBaixe grátis — {URL}\n\n{HASHTAGS}"


def _listar_candidatos() -> None:
    print("📂 output_campanha/ (mp4 mais recentes):")
    mp4s = sorted(OUTPUT.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in mp4s[:8]:
        ts = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"   {ts}  {p.name}  ({p.stat().st_size // 1024} KB)")
    if not mp4s:
        print("   (vazio)")

    print("\n📋 aprovados.jsonl (últimos):")
    for row in _load_aprovados()[-5:]:
        asset = row.get("asset", "—")
        ok = "✓" if asset and Path(asset).is_file() else "✗"
        print(
            f"   [{ok}] {row.get('data', '—')} | {row.get('basename', '—')} | "
            f"{(row.get('headline') or '')[:50]}"
        )


def main() -> int:
    load_project_env()

    parser = argparse.ArgumentParser(description="Republica campanha no Instagram")
    parser.add_argument("--listar", action="store_true", help="Lista vídeos e aprovados")
    parser.add_argument("--asset", help="Caminho do .mp4 ou .jpg")
    parser.add_argument("--basename", help="Nome base em output_campanha (sem extensão)")
    parser.add_argument("--headline", help="Headline para a legenda")
    parser.add_argument("--copy", help="Texto extra da legenda")
    parser.add_argument("--dry-run", action="store_true", help="Só mostra o que publicaria")
    args = parser.parse_args()

    if args.listar:
        _listar_candidatos()
        return 0

    headline = args.headline or ""
    try:
        if args.asset:
            asset_path = _resolve_asset(args.asset)
            basename = Path(asset_path).stem
        elif args.basename:
            asset_path, basename = _pick_from_basename(args.basename)
        else:
            try:
                asset_path, basename, headline = _pick_last_approved()
                print(f"📋 Última campanha aprovada: {basename}")
            except FileNotFoundError:
                asset_path, basename = _pick_latest_mp4()
                print(f"📋 MP4 mais recente: {basename}")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("   Rode: python3 publicar_campanha.py --listar")
        return 1

    if not headline:
        for row in reversed(_load_aprovados()):
            if row.get("basename") == basename or basename in (row.get("asset") or ""):
                headline = (row.get("headline") or "").strip()
                if headline:
                    break

    caption = _montar_caption(headline, args.copy or "")
    size_kb = os.path.getsize(asset_path) // 1024

    print(f"\n📤 Asset: {asset_path} ({size_kb} KB)")
    print(f"📝 Headline: {headline or '(padrão)'}")
    print(f"📄 Legenda (início): {caption[:120]}…\n")

    if args.dry_run:
        print("(--dry-run: nada foi publicado)")
        return 0

    try:
        from meta_publisher import MetaPublisher
    except ImportError:
        print("❌ meta_publisher.py não encontrado.")
        return 1

    publisher = MetaPublisher()
    token_err = publisher.verificar_token()
    if token_err:
        print(f"❌ {token_err['erro']}")
        return 1

    resultado = publisher.postar_asset(asset_path, caption)
    if resultado.get("ok"):
        print(f"\n✅ Reel publicado! ID: {resultado.get('post_id')}")
        return 0
    print(f"\n❌ Falha: {resultado.get('erro')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
