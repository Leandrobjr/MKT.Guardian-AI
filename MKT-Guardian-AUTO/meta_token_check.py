#!/usr/bin/env python3
"""
Diagnóstico do META_ACCESS_TOKEN — validade, escopos e origem do .env.

Uso (Linux):
  cd ~/Documentos/Guardian-AI/MKT_Guardian-AI/MKT-Guardian-AUTO
  python3 meta_token_check.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import dotenv_values

from env_loader import load_project_env

GRAPH_BASE = "https://graph.facebook.com/v21.0"
PKG_DIR = Path(__file__).resolve().parent
ENV_ROOT = PKG_DIR.parent / ".env"
ENV_AUTO = PKG_DIR / ".env"


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "—"
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _token_fingerprint(token: str) -> str:
    if len(token) < 16:
        return "(ausente ou curto demais)"
    return f"{token[:10]}…{token[-6:]}"


def _read_meta_from_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    raw = dotenv_values(path)
    keys = (
        "META_ACCESS_TOKEN",
        "META_IG_USER_ID",
        "META_APP_ID",
        "META_APP_SECRET",
    )
    return {k: (raw.get(k) or "").strip() for k in keys if (raw.get(k) or "").strip()}


def _audit_env_files() -> tuple[Path | None, dict[str, str]]:
    """Mostra fingerprint por arquivo e retorna (arquivo_vencedor, vars_efetivas)."""
    print("\n📁 Auditoria por arquivo .env:")
    per_file: list[tuple[Path, dict[str, str]]] = []
    for label, path in (("raiz", ENV_ROOT), ("AUTO", ENV_AUTO)):
        if not path.is_file():
            print(f"   • {path}")
            print("     (não existe)")
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        vals = _read_meta_from_env(path)
        tok = vals.get("META_ACCESS_TOKEN", "")
        print(f"   • {path}")
        print(f"     modificado: {mtime}")
        print(f"     META_ACCESS_TOKEN: {_token_fingerprint(tok)}")
        if vals.get("META_IG_USER_ID"):
            print(f"     META_IG_USER_ID: {vals['META_IG_USER_ID']}")
        per_file.append((path, vals))

    winner: Path | None = None
    effective: dict[str, str] = {}
    if ENV_AUTO.is_file():
        winner = ENV_AUTO
        effective = _read_meta_from_env(ENV_AUTO)
        if ENV_ROOT.is_file():
            root_tok = _read_meta_from_env(ENV_ROOT).get("META_ACCESS_TOKEN", "")
            auto_tok = effective.get("META_ACCESS_TOKEN", "")
            print("\n⚠️  DOIS .env detectados — AUTO/.env SOBRESCREVE ../.env")
            if root_tok and auto_tok and root_tok != auto_tok:
                print("   → Tokens DIFERENTES: o da raiz está sendo IGNORADO.")
            elif root_tok and auto_tok and root_tok == auto_tok:
                print("   → Mesmo token nos dois arquivos (redundante).")
            print(f"\n   🎯 Token EFETIVO vem de: {ENV_AUTO}")
            print("   Para usar só a raiz: rm MKT-Guardian-AUTO/.env")
    elif ENV_ROOT.is_file():
        winner = ENV_ROOT
        effective = _read_meta_from_env(ENV_ROOT)
        print(f"\n   🎯 Token EFETIVO vem de: {ENV_ROOT}")
    else:
        print("\n❌ Nenhum .env com META_ACCESS_TOKEN encontrado.")

    return winner, effective


def _shell_vs_file_warning(from_files: dict[str, str]) -> None:
    """Detecta export stale no shell (causa #1 de 'atualizei .env mas não mudou')."""
    file_tok = from_files.get("META_ACCESS_TOKEN", "")
    if not file_tok:
        return
    shell_tok = os.environ.get("META_ACCESS_TOKEN", "").strip()
    if shell_tok and shell_tok != file_tok:
        print("\n🚨 CAUSA ENCONTRADA: shell com token DIFERENTE do .env")
        print(f"   Shell (export/source antigo): {_token_fingerprint(shell_tok)}")
        print(f"   Arquivo .env (correto):       {_token_fingerprint(file_tok)}")
        print("\n   Token Meta NÃO propaga — quem manda é o valor carregado.")
        print("   Rode: unset META_ACCESS_TOKEN")
        print("   Ou abra um terminal NOVO (sem source .env).")


def main() -> int:
    winner_path, from_files = _audit_env_files()
    _shell_vs_file_warning(from_files)

    load_project_env()
    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    ig_user = os.getenv("META_IG_USER_ID", "").strip()
    app_id = os.getenv("META_APP_ID", "").strip()
    app_secret = os.getenv("META_APP_SECRET", "").strip()

    print("\n" + "=" * 60)
    print("META TOKEN CHECK — Guardian AI")
    print("=" * 60)

    print(f"\n🔑 Token carregado pelo Python: {_token_fingerprint(token)}")
    print(f"📸 META_IG_USER_ID: {ig_user or '(não definido)'}")

    file_tok = from_files.get("META_ACCESS_TOKEN", "")
    if file_tok and token and file_tok != token:
        print(
            "\n⚠️  Shell com export antigo? "
            "Feche o terminal ou rode: unset META_ACCESS_TOKEN"
        )

    if file_tok and token == file_tok and token.endswith("4QZDZD"):
        print(
            "\n⚠️  Token no .env termina em …4QZDZD (expirou 30/07). "
            "Cole o token novo (…6vtN06d) e salve o arquivo."
        )

    if not token:
        print("\n❌ META_ACCESS_TOKEN ausente após carregar .env.")
        return 1

    if winner_path:
        print(f"\n📂 Arquivo em uso: {winner_path}")

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
        print("\n💡 A Meta rejeitou ESTE token literal. Próximos passos:")
        print("   1) rm ~/Documentos/Guardian-AI/MKT_Guardian-AI/MKT-Guardian-AUTO/.env")
        print("   2) Graph API Explorer → token NOVO (não o EAAoJmoNlc…)")
        print("   3) Troque por long-lived (curl fb_exchange_token)")
        print("   4) Cole só em MKT_Guardian-AI/.env")
        print("   5) python3 meta_token_check.py")
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
        elif dias < 30:
            print(f"   ⚠️  Restam ~{dias:.0f} dias (pode ser token curto trocado)")
        else:
            print(f"   ✓ Restam ~{dias:.0f} dias (long-lived OK)")

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
        print("RESULTADO: token INVÁLIDO.")
        return 1
    if missing:
        print("RESULTADO: token válido mas SEM permissão de publicação.")
        return 1
    print("RESULTADO: token OK para publicar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
