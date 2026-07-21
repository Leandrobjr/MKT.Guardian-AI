"""
Carrega variáveis do .env do repositório.

Ordem (Linux típico):
  1) ../.env  — raiz do clone (ex.: ~/Documentos/Guardian-AI/MKT_Guardian-AI/.env)
  2) .env     — ao lado dos scripts (MKT-Guardian-AUTO/.env), sobrescreve a raiz
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

_PKG_DIR = Path(__file__).resolve().parent


def load_project_env() -> None:
    parent_env = _PKG_DIR.parent / ".env"
    local_env = _PKG_DIR / ".env"
    if parent_env.is_file():
        load_dotenv(parent_env)
    if local_env.is_file():
        load_dotenv(local_env, override=True)
    elif not parent_env.is_file():
        load_dotenv()
