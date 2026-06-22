"""
Memória persistente dos agentes — aprendizado com correções do administrador.

Arquivos em contexto_negocio/memoria/ (append-only JSONL):
  - correcoes_admin.jsonl  feedback MELHORAR do Telegram
  - aprovados.jsonl        criativos aprovados (referência positiva)
  - rejeitados.jsonl         criativos rejeitados
"""

import json
import os
from datetime import datetime


class AgentMemory:
    def __init__(self, base_dir: str):
        self.mem_dir = os.path.join(base_dir, "contexto_negocio", "memoria")
        os.makedirs(self.mem_dir, exist_ok=True)
        self._correcoes = os.path.join(self.mem_dir, "correcoes_admin.jsonl")
        self._aprovados = os.path.join(self.mem_dir, "aprovados.jsonl")
        self._rejeitados = os.path.join(self.mem_dir, "rejeitados.jsonl")

    def _append(self, path: str, record: dict) -> None:
        record.setdefault("data", datetime.now().strftime("%Y-%m-%d %H:%M"))
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _load_recent(self, path: str, limit: int = 10) -> list[dict]:
        if not os.path.isfile(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            linhas = [ln.strip() for ln in f if ln.strip()]
        registros = []
        for ln in linhas[-limit:]:
            try:
                registros.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        return registros

    def registrar_correcao(
        self,
        publico: str,
        golpe: str,
        feedback: str,
        basename: str = "",
        revisao: int = 0,
    ) -> None:
        self._append(self._correcoes, {
            "tipo": "correcao_admin",
            "publico": publico,
            "golpe": golpe,
            "feedback": feedback,
            "basename": basename,
            "revisao": revisao,
        })

    def registrar_aprovado(
        self,
        publico: str,
        golpe: str,
        basename: str,
        headline: str,
        asset_path: str,
    ) -> None:
        self._append(self._aprovados, {
            "tipo": "aprovado",
            "publico": publico,
            "golpe": golpe,
            "basename": basename,
            "headline": headline,
            "asset": asset_path,
        })

    def registrar_rejeitado(
        self,
        publico: str,
        golpe: str,
        basename: str,
        motivo: str = "rejeitado_admin",
    ) -> None:
        self._append(self._rejeitados, {
            "tipo": "rejeitado",
            "publico": publico,
            "golpe": golpe,
            "basename": basename,
            "motivo": motivo,
        })

    def format_for_prompt(self, limit_correcoes: int = 8) -> str:
        """Texto injetado no prompt Gemini — regras aprendidas."""
        partes: list[str] = []
        correcoes = self._load_recent(self._correcoes, limit_correcoes)
        if correcoes:
            partes.append("CORREÇÕES DO ADMINISTRADOR (não repetir):")
            for c in correcoes:
                fb = c.get("feedback", c.get("problema", ""))
                pub = c.get("publico", "")
                if fb:
                    partes.append(f"- [{pub}] {fb}")

        rejeitados = self._load_recent(self._rejeitados, 5)
        if rejeitados:
            partes.append("\nPADRÕES REJEITADOS:")
            for r in rejeitados:
                partes.append(f"- [{r.get('publico', '')}] {r.get('motivo', 'rejeitado')}")

        aprovados = self._load_recent(self._aprovados, 3)
        if aprovados:
            partes.append("\nREFERÊNCIAS APROVADAS (inspire-se no tom):")
            for a in aprovados:
                partes.append(f"- [{a.get('publico', '')}] {a.get('headline', '')[:80]}")

        return "\n".join(partes)
