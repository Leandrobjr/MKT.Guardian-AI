"""Cliente utilitário Kling AI — autenticação, saldo e erros."""

import os
import time
from datetime import datetime, timedelta

import requests

KLING_BASE_URL = "https://api-singapore.klingai.com"

# Códigos documentados pela Kling (painel developer)
KLING_ERROR_HINTS = {
    1101: "Conta em débito — recarregue o pacote de recursos da API (não confundir com créditos do site).",
    1102: "Pacote de recursos esgotado ou expirado — compre/renove em app.klingai.com → Developer → Resource Pack.",
    1303: "Limite de tarefas paralelas — aguarde renders anteriores terminarem.",
}


def _encode_jwt(access_key: str, secret_key: str) -> str:
    try:
        import jwt
    except ImportError as exc:
        raise RuntimeError(
            "PyJWT necessário para KLING_ACCESS_KEY/KLING_SECRET_KEY. Instale: pip install PyJWT"
        ) from exc

    now = int(time.time())
    payload = {"iss": access_key, "exp": now + 1800, "nbf": now - 5}
    return jwt.encode(payload, secret_key, algorithm="HS256", headers={"alg": "HS256", "typ": "JWT"})


def resolve_kling_auth() -> tuple[str, str]:
    """
    Retorna (token_bearer, modo_auth).
    Prioridade: JWT (Access+Secret) > KLING_API_KEY simples.
    """
    access = (os.getenv("KLING_ACCESS_KEY") or "").strip()
    secret = (os.getenv("KLING_SECRET_KEY") or "").strip()
    if access and secret:
        return _encode_jwt(access, secret), "jwt"

    api_key = (os.getenv("KLING_API_KEY") or "").strip()
    if api_key:
        return api_key, "api_key"

    return "", "none"


def kling_headers() -> dict[str, str]:
    token, _ = resolve_kling_auth()
    if not token:
        return {"Content-Type": "application/json"}
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def parse_kling_response(res: requests.Response) -> dict:
    try:
        body = res.json()
    except ValueError:
        body = {"raw": res.text[:500]}
    code = body.get("code")
    message = body.get("message") or body.get("msg") or res.text[:300]
    hint = KLING_ERROR_HINTS.get(code, "")
    return {
        "http_status": res.status_code,
        "code": code,
        "message": message,
        "hint": hint,
        "body": body,
    }


def fetch_resource_packages(days: int = 30) -> dict:
    """Consulta pacotes de recursos da API (saldo real para geração)."""
    headers = kling_headers()
    token, mode = resolve_kling_auth()
    if not token:
        return {"ok": False, "error": "KLING_API_KEY ou KLING_ACCESS_KEY+KLING_SECRET_KEY ausentes no .env"}

    end_ms = int(time.time() * 1000)
    start_ms = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    url = f"{KLING_BASE_URL}/account/costs?start_time={start_ms}&end_time={end_ms}"

    try:
        res = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc), "auth_mode": mode}

    parsed = parse_kling_response(res)
    if res.status_code != 200 or parsed.get("code") not in (0, None):
        return {"ok": False, "auth_mode": mode, **parsed}

    data = parsed["body"].get("data", {})
    packs = data.get("resource_pack_subscribe_infos") or []
    active = [p for p in packs if p.get("status") == "online"]
    pending = [p for p in packs if p.get("status") == "toBeOnline"]
    depleted = [p for p in packs if p.get("status") in ("runOut", "expired")]

    total_remaining = sum(float(p.get("remaining_quantity") or 0) for p in active)

    return {
        "ok": True,
        "auth_mode": mode,
        "total_remaining": total_remaining,
        "active_packs": active,
        "pending_packs": pending,
        "depleted_packs": depleted,
        "all_packs": packs,
        "note": "O painel Kling pode atrasar até ~12h para atualizar remaining_quantity.",
    }


def format_balance_report(info: dict) -> str:
    if not info.get("ok"):
        lines = ["❌ Não foi possível consultar saldo Kling API."]
        if info.get("http_status"):
            lines.append(f"   HTTP {info['http_status']} | code={info.get('code')} | {info.get('message')}")
        if info.get("hint"):
            lines.append(f"   → {info['hint']}")
        if info.get("error"):
            lines.append(f"   → {info['error']}")
        return "\n".join(lines)

    lines = [
        f"✅ Autenticação OK (modo: {info.get('auth_mode')})",
        f"💰 Saldo API (pacotes online): {info.get('total_remaining', 0):.2f} unidades",
        f"ℹ️  {info.get('note')}",
    ]
    for pack in info.get("active_packs") or []:
        name = pack.get("resource_pack_name", "Pacote")
        rem = pack.get("remaining_quantity", 0)
        total = pack.get("total_quantity", 0)
        lines.append(f"   • {name}: {rem}/{total} ({pack.get('status')})")
    if info.get("pending_packs"):
        lines.append("⏳ Pacotes pendentes de ativação (toBeOnline):")
        for pack in info["pending_packs"]:
            lines.append(f"   • {pack.get('resource_pack_name')} — aguardando ativação")
    if info.get("depleted_packs") and not info.get("active_packs"):
        lines.append("⚠️ Todos os pacotes estão esgotados ou expirados.")
    return "\n".join(lines)


def explain_balance_error(message: str) -> str:
    msg = (message or "").lower()
    if "balance" in msg or "not enough" in msg or "insufficient" in msg:
        return (
            "A API rejeitou por saldo insuficiente no PACOTE DE RECURSOS da API "
            "(developer), não necessariamente os créditos visíveis no site/app Kling. "
            "Verifique em app.klingai.com → Developer → Resource Pack / Billing."
        )
    return ""
