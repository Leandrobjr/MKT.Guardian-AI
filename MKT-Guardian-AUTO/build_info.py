"""Versão do build — exibida no startup para confirmar git pull."""

MEDIA_FACTORY_VERSION = "18.4"
ORCHESTRATOR_VERSION = "4.6"
MIN_GIT_COMMIT_PREFIX = "fbc6e11"  # FFmpeg nativo + overlay PNG


def get_git_short_hash(base_dir: str) -> str:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=base_dir, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "desconhecido"


def print_build_banner(base_dir: str) -> None:
    git_hash = get_git_short_hash(base_dir)
    print(
        f"📦 Build: Orquestrador v{ORCHESTRATOR_VERSION} | "
        f"Fábrica v{MEDIA_FACTORY_VERSION} | git {git_hash}"
    )
    print(
        "   Esperado: Orquestrador v4.6+ | Etapa 6 com aprovação final via terminal (opção 4). "
        "Se não aparecer, rode: git pull origin main"
    )
