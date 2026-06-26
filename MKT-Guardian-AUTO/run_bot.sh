#!/bin/bash
# Inicia o bot Telegram em foreground (Ctrl+C para encerrar).
# Para rodar em background: nohup ./run_bot.sh > bot.log 2>&1 &

cd "$(dirname "$0")"

if [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
elif [ -f "../../venv/bin/activate" ]; then
    source ../../venv/bin/activate
fi

python telegram_bot.py
