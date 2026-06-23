#!/usr/bin/env python3
"""
Descobre TELEGRAM_CHAT_ID usando o token do seu bot.

Passos:
  1. Coloque TELEGRAM_BOT_TOKEN no .env
  2. No Telegram, abra SEU bot (username que criou no BotFather)
  3. Toque Iniciar e envie: oi
  4. Rode: python3 descobrir_chat_id.py
"""

import os
import sys

import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN não encontrado no .env")
        sys.exit(1)

    print("=" * 60)
    print("DESCOBRIR TELEGRAM_CHAT_ID")
    print("=" * 60)
    print("\n1. Abra seu bot no Telegram (busque o @username do bot)")
    print("2. Toque INICIAR (/start) e envie a mensagem: oi")
    input("\n3. Depois de enviar, pressione ENTER aqui... ")

    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    try:
        r = requests.get(url, timeout=20)
        data = r.json()
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        sys.exit(1)

    if not data.get("ok"):
        print(f"❌ Token inválido ou erro da API:\n{data}")
        sys.exit(1)

    updates = data.get("result", [])
    if not updates:
        print("\n❌ Nenhuma mensagem recebida pelo bot.")
        print("\nVerifique:")
        print("  • Você enviou mensagem para o BOT certo (não para o BotFather)")
        print("  • Clicou em INICIAR antes de enviar 'oi'")
        print("  • O token no .env é do mesmo bot")
        sys.exit(1)

    vistos = set()
    print("\n✅ Chats encontrados (use o ID da sua conversa privada):\n")
    for upd in reversed(updates):
        msg = upd.get("message") or upd.get("edited_message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if not chat_id or chat_id in vistos:
            continue
        vistos.add(chat_id)
        nome = chat.get("first_name") or chat.get("title") or "?"
        tipo = chat.get("type", "?")
        username = chat.get("username") or ""
        user_tag = f" @{username}" if username else ""
        print(f"  TELEGRAM_CHAT_ID={chat_id}")
        print(f"    Nome: {nome}{user_tag} | Tipo: {tipo}\n")

    print("Copie a linha TELEGRAM_CHAT_ID=... para o seu .env")


if __name__ == "__main__":
    main()
