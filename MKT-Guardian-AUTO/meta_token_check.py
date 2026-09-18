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
    """Audita a fonte canônica e informa se há um arquivo interno ignorado."""
    print("\n📁 Auditoria do arquivo .env oficial:")
    if not ENV_ROOT.is_file():
        print(f"   ❌ Ausente: {ENV_ROOT}")
        return None, {}

    effective = _read_meta_from_env(ENV_ROOT)
    mtime = datetime.fromtimestamp(ENV_ROOT.stat().st_mtime).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    print(f"   • {ENV_ROOT}")
    print(f"     modificado: {mtime}")
    print(f"     META_ACCESS_TOKEN: {_token_fingerprint(effective.get('META_ACCESS_TOKEN', ''))}")
    if effective.get("META_IG_USER_ID"):
        print(f"     META_IG_USER_ID: {effective['META_IG_USER_ID']}")
    if ENV_AUTO.is_file():
        print(f"\n⚠️ Arquivo ignorado durante a transição: {ENV_AUTO}")
    print(f"\n   🎯 Token EFETIVO vem de: {ENV_ROOT}")
    return ENV_ROOT, effective


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

    try:
        load_project_env()
    except FileNotFoundError as exc:
        print(f"\n❌ {exc}")
        return 1
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
        print("   1) Confirme o arquivo oficial MKT_Guardian-AI/.env")
        print("   2) Gere ou selecione um token válido no Graph API Explorer")
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
            print(f"   ❌ EXPIRADO há {abs(dias):.1f} dia(s)")
        elif dias < 1:
            horas = dias * 24
            print(f"   ❌ Token CURTO — expira em ~{horas:.1f}h (NÃO é long-lived de 60 dias)")
        elif dias < 30:
            print(f"   ❌ Restam apenas ~{dias:.0f} dias — provavelmente NÃO é long-lived")
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

    dias_restantes = None
    if expires_at:
        dias_restantes = (expires_at - datetime.now(tz=timezone.utc).timestamp()) / 86400

    if dias_restantes is not None and dias_restantes < 30:
        print("RESULTADO: ERRADO — token abaixo do mínimo de 30 dias; renove para long-lived (60 dias).")
        print("   Cole o access_token do curl (expires_in: 5183999) em ../.env")
        print("   Confirme a validade e a data de expiração retornadas pelo seu curl.")
        return 1

    print("RESULTADO: token OK para publicar (long-lived confirmado).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
