#!/usr/bin/env python3
"""Diagnóstico ElevenLabs — créditos, voice_id e TTS de teste."""

from __future__ import annotations

import os
import sys

import requests

from env_loader import load_project_env

load_project_env()

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)


def main() -> int:
    key = (
        os.getenv("ELEVENLABS_API_KEY")
        or os.getenv("ELEVEN_LABS_API_KEY")
        or os.getenv("ELEVENLABS_KEY")
    )
    voice_id = (
        os.getenv("ELEVENLABS_VOICE_ID")
        or os.getenv("ELEVEN_LABS_VOICE_ID")
        or "21m00Tcm4TlvDq8ikWAM"
    )
    print("=" * 60)
    print("DIAGNÓSTICO ELEVENLABS")
    print("=" * 60)
    if not key:
        print("❌ ELEVENLABS_API_KEY ausente no .env")
        return 1
    print(f"✅ API key presente ({key[:8]}…)")
    print(f"   voice_id: {voice_id}")

    try:
        sub = requests.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": key},
            timeout=20,
        )
        if sub.ok:
            data = sub.json()
            used = data.get("character_count", 0)
            limit = data.get("character_limit", 0)
            remaining = max(0, int(limit) - int(used))
            print(f"✅ Assinatura OK — usado {used}/{limit} chars (~{remaining} restantes)")
            tier = data.get("tier") or data.get("status")
            if tier:
                print(f"   Plano: {tier}")
        else:
            print(f"⚠️ Não foi possível ler assinatura: HTTP {sub.status_code} {sub.text[:200]}")
    except Exception as e:
        print(f"⚠️ Erro ao consultar assinatura: {e}")

    sample = "Teste Guardian AI. Proteja seu WhatsApp agora."
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = {
        "text": sample,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.9, "style": 0.4},
    }
    try:
        r = requests.post(
            url,
            json=payload,
            headers={"Accept": "audio/mpeg", "xi-api-key": key},
            timeout=60,
        )
        if r.status_code == 200 and len(r.content) > 1000:
            out = os.path.join(BASE, "output_campanha", "_elevenlabs_test.mp3")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as f:
                f.write(r.content)
            print(f"✅ TTS teste OK — {len(r.content) // 1024} KB → {out}")
            return 0
        print(f"❌ TTS teste falhou: HTTP {r.status_code} {r.text[:300]}")
        return 1
    except Exception as e:
        print(f"❌ TTS teste erro: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
