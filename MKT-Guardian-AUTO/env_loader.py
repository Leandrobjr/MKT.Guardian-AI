"""Carrega o único arquivo de ambiente oficial do projeto.

A fonte canônica é sempre o ``.env`` na raiz do repositório. O arquivo
``MKT-Guardian-AUTO/.env`` pode permanecer durante a transição, mas não é
carregado para evitar configurações divergentes.
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

_PKG_DIR = Path(__file__).resolve().parent


def load_project_env() -> None:
    """Carrega a configuração da raiz, sem procurar outros arquivos."""
    parent_env = _PKG_DIR.parent / ".env"
    if not parent_env.is_file():
        raise FileNotFoundError(
            f"Arquivo .env oficial não encontrado: {parent_env}"
        )
    load_dotenv(parent_env, override=True)
