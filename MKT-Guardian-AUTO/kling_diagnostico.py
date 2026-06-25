#!/usr/bin/env python3
"""Diagnóstico rápido da conta Kling API — rode antes de gerar campanhas."""

import os
import sys

from dotenv import load_dotenv

from kling_client import fetch_resource_packages, format_balance_report, resolve_kling_auth

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    os.chdir(BASE_DIR)
    load_dotenv(os.path.join(BASE_DIR, ".env"))

    token, mode = resolve_kling_auth()
    print("=" * 60)
    print("KLING AI — DIAGNÓSTICO DE CONTA API")
    print("=" * 60)

    if not token:
        print("❌ Nenhuma credencial Kling no .env")
        print("   Configure KLING_API_KEY (Kling 3.0) OU")
        print("   KLING_ACCESS_KEY + KLING_SECRET_KEY (JWT legado)")
        return 1

    print(f"🔑 Credencial detectada (modo: {mode})")
    print(f"🌐 Base URL: https://api-singapore.klingai.com")
    print()
    print("📊 Consultando pacotes de recursos (últimos 30 dias)...")
    print()

    info = fetch_resource_packages(days=30)
    print(format_balance_report(info))
    print()
    print("-" * 60)
    print("NOTAS IMPORTANTES:")
    print("• Créditos do site/app Kling ≠ saldo da API developer.")
    print("• Compra de recursos: Developer Console → Resource Pack.")
    print("• Saldo no painel pode demorar até ~12h para refletir recarga.")
    print("• Este app NÃO usa cache de respostas Kling — cada geração é nova.")
    print("-" * 60)

    if info.get("ok") and info.get("total_remaining", 0) <= 0 and not info.get("pending_packs"):
        return 2
    return 0 if info.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
