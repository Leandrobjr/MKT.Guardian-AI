"""
Memória persistente dos agentes — aprendizado com correções do administrador.

Arquivos em contexto_negocio/memoria/ (append-only JSONL):
  - correcoes_admin.jsonl  feedback MELHORAR do Telegram
  - aprovados.jsonl        criativos aprovados (referência positiva)
  - rejeitados.jsonl         criativos rejeitados
"""

import json
import os
import re
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
        categoria: str = "",
    ) -> None:
        tag = categoria.strip("[]") if categoria else ""
        self._append(self._correcoes, {
            "tipo": "correcao_admin",
            "publico": publico,
            "golpe": golpe,
            "feedback": feedback,
            "categoria": tag or self._infer_categoria(feedback),
            "basename": basename,
            "revisao": revisao,
        })

    @staticmethod
    def _infer_categoria(feedback: str) -> str:
        m = re.search(r"\[(\w+)\]", feedback or "")
        if m:
            return m.group(1)
        return "copy"

    def correcoes_por_categoria(
        self,
        publico: str = "",
        golpe: str = "",
        categoria: str = "",
        limit: int = 5,
    ) -> list[dict]:
        rows = self._filter_by_combo(
            self._load_recent(self._correcoes, limit * 6),
            publico,
            golpe,
            limit * 3,
        )
        if categoria:
            rows = [r for r in rows if r.get("categoria") == categoria]
        return rows[-limit:]

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

    def _filter_by_combo(
        self, registros: list[dict], publico: str, golpe: str, limit: int
    ) -> list[dict]:
        if not publico and not golpe:
            return registros[-limit:]
        filtrados = [
            r for r in registros
            if (not publico or r.get("publico") == publico)
            and (not golpe or r.get("golpe") == golpe)
        ]
        if filtrados:
            return filtrados[-limit:]
        return registros[-limit:]

    def headlines_usadas(self, publico: str, golpe: str, limit: int = 10) -> list[str]:
        """Headlines aprovadas do mesmo combo — para blocklist no prompt."""
        todos = self._load_recent(self._aprovados, 200)
        filtrados = self._filter_by_combo(todos, publico, golpe, limit)
        headlines: list[str] = []
        for a in filtrados:
            h = (a.get("headline") or "").strip()
            if h and h not in headlines:
                headlines.append(h)
        return headlines[:limit]

    def format_for_prompt(
        self,
        publico: str = "",
        golpe: str = "",
        limit_correcoes: int = 8,
    ) -> str:
        """Texto injetado no prompt Gemini — regras aprendidas (filtradas por combo)."""
        partes: list[str] = []
        correcoes = self._filter_by_combo(
            self._load_recent(self._correcoes, limit_correcoes * 3),
            publico,
            golpe,
            limit_correcoes,
        )
        if correcoes:
            combo = f"{publico}/{golpe}" if publico or golpe else "geral"
            partes.append(f"CORREÇÕES DO ADMINISTRADOR — combo {combo} (não repetir):")
            for c in correcoes:
                fb = c.get("feedback", c.get("problema", ""))
                if fb:
                    cat = c.get("categoria", "")
                    prefix = f"[{cat}] " if cat else ""
                    partes.append(f"- {prefix}{fb}")

        headlines = self.headlines_usadas(publico, golpe, limit=8)
        if headlines:
            partes.append("\nHEADLINES JÁ USADAS NESTE COMBO (NÃO REPETIR — crie manchete nova):")
            for h in headlines:
                partes.append(f"- {h[:100]}")

        rejeitados = self._filter_by_combo(
            self._load_recent(self._rejeitados, 20),
            publico,
            golpe,
            5,
        )
        if rejeitados:
            partes.append("\nPADRÕES REJEITADOS:")
            for r in rejeitados:
                partes.append(f"- {r.get('motivo', 'rejeitado')}")

        aprovados = self._filter_by_combo(
            self._load_recent(self._aprovados, 20),
            publico,
            golpe,
            2,
        )
        if aprovados:
            partes.append("\nREFERÊNCIAS APROVADAS (inspire-se no tom, não copie a manchete):")
            for a in aprovados:
                partes.append(f"- {a.get('headline', '')[:80]}")

        return "\n".join(partes)
