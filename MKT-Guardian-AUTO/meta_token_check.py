#!/usr/bin/env python3
"""
Diagnóstico do META_ACCESS_TOKEN — validade, escopos e origem do .env.

Uso (Linux):
  cd ~/Documentos/Guardian-AI/MKT_Guardian-AI/MKT-Guardian-AUTO
  python3 meta_token_check.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from env_loader import load_project_env

GRAPH_BASE = "https://graph.facebook.com/v21.0"
PKG_DIR = Path(__file__).resolve().parent


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "—"
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _token_fingerprint(token: str) -> str:
    if len(token) < 16:
        return "(token curto demais ou ausente)"
    return f"{token[:10]}…{token[-6:]}"


def _env_sources() -> list[str]:
    paths = [PKG_DIR.parent / ".env", PKG_DIR / ".env"]
    return [str(p) for p in paths if p.is_file()]


def main() -> int:
    load_project_env()

    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    ig_user = os.getenv("META_IG_USER_ID", "").strip()
    app_id = os.getenv("META_APP_ID", "").strip()
    app_secret = os.getenv("META_APP_SECRET", "").strip()

    print("=" * 60)
    print("META TOKEN CHECK — Guardian AI")
    print("=" * 60)

    env_files = _env_sources()
    if env_files:
        print("\n📁 Arquivos .env encontrados (ordem de carga):")
        for p in env_files:
            mtime = datetime.fromtimestamp(Path(p).stat().st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            print(f"   • {p}  (modificado: {mtime})")
        if len(env_files) == 2:
            print("   → MKT-Guardian-AUTO/.env SOBRESCREVE ../.env")
    else:
        print("\n⚠️  Nenhum .env encontrado na raiz do clone nem em AUTO/")

    print(f"\n🔑 META_ACCESS_TOKEN: {_token_fingerprint(token)}")
    print(f"📸 META_IG_USER_ID: {ig_user or '(não definido)'}")

    if not token:
        print("\n❌ META_ACCESS_TOKEN ausente. Edite o .env no Linux e rode de novo.")
        return 1

    # debug_token — app token preferível; senão usa o próprio user token
    app_token = f"{app_id}|{app_secret}" if app_id and app_secret else token
    try:
        r = requests.get(
            f"{GRAPH_BASE}/debug_token",
            params={"input_token": token, "access_token": app_token},
            timeout=20,
        )
        body = r.json()
    except Exception as e:
        print(f"\n❌ Falha ao consultar debug_token: {e}")
        return 1

    if "error" in body and "data" not in body:
        err = body["error"]
        print(f"\n❌ debug_token: {err.get('message')} (code={err.get('code')})")
        print("\n💡 Se a mensagem fala em 'Session has expired', o token no .env")
        print("   do LINUX está expirado — renove e cole no arquivo correto.")
        return 1

    data = body.get("data", {})
    is_valid = data.get("is_valid", False)
    expires_at = data.get("expires_at", 0)
    issued_at = data.get("issued_at")
    scopes = data.get("scopes") or []
    app_name = (data.get("application") or "") or str(data.get("app_id", ""))

    print(f"\n📋 App: {app_name}")
    print(f"✅ Válido agora: {'SIM' if is_valid else 'NÃO'}")
    print(f"📅 Emitido: {_fmt_ts(issued_at)}")
    print(f"⏰ Expira: {_fmt_ts(expires_at)}")

    if expires_at:
        now = datetime.now(tz=timezone.utc).timestamp()
        dias = (expires_at - now) / 86400
        if dias <= 0:
            print(f"   ⚠️  EXPIRADO há {abs(dias):.1f} dia(s)")
        elif dias < 7:
            print(f"   ⚠️  Expira em {dias:.1f} dia(s) — renove em breve")
        else:
            print(f"   ✓ Restam ~{dias:.0f} dias (long-lived)")

    needed = {"instagram_basic", "instagram_content_publish"}
    missing = needed - set(scopes)
    print(f"\n🔐 Escopos ({len(scopes)}): {', '.join(scopes) or '—'}")
    if missing:
        print(f"   ❌ Faltam para publicar Reels: {', '.join(sorted(missing))}")
    else:
        print("   ✓ Escopos mínimos para publicação OK")

    if ig_user:
        try:
            r2 = requests.get(
                f"{GRAPH_BASE}/{ig_user}",
                params={"fields": "id,username,name", "access_token": token},
                timeout=20,
            )
            ig = r2.json()
            if "error" in ig:
                print(f"\n❌ Conta IG {ig_user}: {ig['error'].get('message')}")
            else:
                print(
                    f"\n📸 Instagram: @{ig.get('username')} "
                    f"({ig.get('name')}) id={ig.get('id')}"
                )
        except Exception as e:
            print(f"\n⚠️  Não foi possível validar IG: {e}")

    print("\n" + "=" * 60)
    if not is_valid:
        print("RESULTADO: token INVÁLIDO — atualize META_ACCESS_TOKEN no .env do Linux.")
        print("\nRenovação long-lived (60 dias):")
        print("  1) Graph API Explorer → token curto EAA... com instagram_content_publish")
        print("  2) Troque por long-lived:")
        print("     curl \"https://graph.facebook.com/v21.0/oauth/access_token?")
        print("       grant_type=fb_exchange_token&")
        print("       client_id=SEU_APP_ID&")
        print("       client_secret=SEU_APP_SECRET&")
        print("       fb_exchange_token=TOKEN_CURTO\"")
        print("  3) Cole o access_token retornado em META_ACCESS_TOKEN")
        print("  4) Rode: python3 meta_token_check.py  (deve mostrar ~60 dias)")
        return 1

    if missing:
        print("RESULTADO: token válido mas SEM permissão de publicação.")
        return 1

    print("RESULTADO: token OK para publicar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
