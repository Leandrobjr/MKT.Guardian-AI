"""
Daemon Telegram — Guardian AI Campaign Launcher

Substitui o menu do terminal por botões inline no Telegram.
O pipeline de geração e aprovação permanece idêntico.

Uso:
    python telegram_bot.py
    # ou em background:
    nohup python telegram_bot.py > bot.log 2>&1 &
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import queue as _queue
import subprocess
import sys
import threading
from typing import Any

import aiohttp
import requests
from dotenv import load_dotenv
from build_info import MEDIA_FACTORY_VERSION, ORCHESTRATOR_VERSION

load_dotenv()

TELEGRAM_API = "https://api.telegram.org/bot"

# ---------------------------------------------------------------------------
# Definição das etapas do wizard
# ---------------------------------------------------------------------------

STEPS = [
    "select_publico",
    "select_golpe",
    "select_midia",
    "select_canal",
    "select_objetivo",
    "select_fluxo",
]

OPCOES: dict[str, list[tuple[str, str, str]]] = {
    # etapa: [(label_botão, valor_legível, id_interno)]
    "select_publico": [
        ("Idosos / Aposentados", "Idosos e aposentados vulneráveis a fraudes financeiras e familiares.", "idosos"),
        ("Pais / Filhos", "Pais preocupados com a segurança e integridade dos filhos na internet.", "pais"),
        ("Empresários", "Empresários e donos de comércios expostos a golpes e clonagem de contas.", "empresarios"),
        ("Escolas", "Dirigentes e professores focados na segurança de dados escolares.", "escolas"),
    ],
    "select_golpe": [
        ("Falso Parente", "Golpe do Falso Parente / Novo Número no WhatsApp pedindo dinheiro urgente.", "falso_parente"),
        ("Golpe do PIX", "Golpe do PIX e transferências bancárias sob indução mecânica ou pânico.", "pix_fantasma"),
        ("Falsa Central", "Golpe da Falsa Central Bancária simulando atendimento de segurança.", "falsa_central"),
        ("Grooming", "Grooming / Aliciamento digital de menores e exposição de crianças online.", "grooming"),
        ("Phishing", "Links maliciosos de Phishing e páginas clonadas para roubo de senhas.", "phishing"),
        ("Clonagem WhatsApp", "Clonagem de WhatsApp via engenharia social e roubo do código SMS.", "clonagem_whatsapp"),
    ],
    "select_midia": [
        ("Imagem Estática", "Imagem Estática Square (1080x1080)", "imagem"),
        ("Vídeo Animado", "Vídeo Vertical Animado", "video"),
    ],
    "select_canal": [
        ("Meta Ads (Instagram/Facebook)", "Meta Ads (Instagram/Facebook)", "meta"),
        ("TikTok / YouTube Shorts", "TikTok / YouTube Shorts", "tiktok"),
    ],
    "select_objetivo": [
        ("Instalação do App", "Instalação do Aplicativo (Downloads)", "install"),
        ("Geração de Leads", "Geração de Leads Qualificados", "leads"),
    ],
    "select_fluxo": [
        ("Salvar localmente", "local", "local"),
        ("Salvar + Aprovar Telegram", "telegram", "telegram"),
        ("Salvar + Telegram + Instagram", "telegram_instagram", "telegram_instagram"),
    ],
}

TITULOS = {
    "select_publico": "Etapa 1/6 — Selecione o *PÚBLICO-ALVO*:",
    "select_golpe":   "Etapa 2/6 — Selecione o *TIPO DE GOLPE*:",
    "select_midia":   "Etapa 3/6 — Selecione o *TIPO DE MÍDIA*:",
    "select_canal":   "Etapa 4/6 — Selecione o *CANAL DE VEICULAÇÃO*:",
    "select_objetivo": "Etapa 5/6 — Selecione o *OBJETIVO DE CONVERSÃO*:",
    "select_fluxo":   "Etapa 6/6 — Selecione o *FLUXO PÓS-GERAÇÃO*:",
}

PUBLICO_ID_MAP = {
    "idosos": "idosos",
    "pais": "pais",
    "empresarios": "profissionais",
    "escolas": "profissionais",
}

MIDIA_LABEL = {
    "imagem": "Imagem Estática Square (1080x1080)",
    "video": "Vídeo Vertical Animado",
}

CANAL_LABEL = {
    "meta": "Meta Ads (Instagram/Facebook)",
    "tiktok": "TikTok / YouTube Shorts",
}


# ---------------------------------------------------------------------------
# Estado da sessão (in-memory, single-user)
# ---------------------------------------------------------------------------

class Session:
    def __init__(self):
        self.step: str = "idle"
        self.selections: dict[str, str] = {}
        self.running: bool = False
        self.thread: threading.Thread | None = None

    def reset(self):
        self.__init__()

    def to_config(self) -> dict:
        publico_slug = self.selections["select_publico"]
        golpe_id = self.selections["select_golpe"]
        midia_key = self.selections["select_midia"]
        canal_key = self.selections["select_canal"]
        objetivo_key = self.selections["select_objetivo"]
        fluxo_key = self.selections["select_fluxo"]

        opcoes_golpe_map = {r[2]: r[1] for r in OPCOES["select_golpe"]}
        opcoes_publico_map = {r[2]: r[1] for r in OPCOES["select_publico"]}
        opcoes_objetivo_map = {r[2]: r[1] for r in OPCOES["select_objetivo"]}

        fluxo_config = {
            "local":              {"aprovacao_telegram": False, "postar_instagram": False},
            "telegram":           {"aprovacao_telegram": True,  "postar_instagram": False},
            "telegram_instagram": {"aprovacao_telegram": True,  "postar_instagram": True},
        }.get(fluxo_key, {"aprovacao_telegram": True, "postar_instagram": False})

        return {
            "publico":      opcoes_publico_map.get(publico_slug, publico_slug),
            "publico_id":   PUBLICO_ID_MAP.get(publico_slug, "massa"),
            "publico_slug": publico_slug,
            "golpe":        opcoes_golpe_map.get(golpe_id, golpe_id),
            "golpe_id":     golpe_id,
            "midia":        MIDIA_LABEL.get(midia_key, midia_key),
            "canal":        CANAL_LABEL.get(canal_key, canal_key),
            "objetivo":     opcoes_objetivo_map.get(objetivo_key, objetivo_key),
            **fluxo_config,
        }

    def summary(self) -> str:
        publico_labels  = {r[2]: r[0] for r in OPCOES["select_publico"]}
        golpe_labels    = {r[2]: r[0] for r in OPCOES["select_golpe"]}
        midia_labels    = {r[2]: r[0] for r in OPCOES["select_midia"]}
        canal_labels    = {r[2]: r[0] for r in OPCOES["select_canal"]}
        obj_labels      = {r[2]: r[0] for r in OPCOES["select_objetivo"]}
        fluxo_labels    = {r[2]: r[0] for r in OPCOES["select_fluxo"]}

        return (
            "*Resumo da campanha:*\n\n"
            f"Público: {publico_labels.get(self.selections.get('select_publico',''), '—')}\n"
            f"Golpe: {golpe_labels.get(self.selections.get('select_golpe',''), '—')}\n"
            f"Mídia: {midia_labels.get(self.selections.get('select_midia',''), '—')}\n"
            f"Canal: {canal_labels.get(self.selections.get('select_canal',''), '—')}\n"
            f"Objetivo: {obj_labels.get(self.selections.get('select_objetivo',''), '—')}\n"
            f"Fluxo: {fluxo_labels.get(self.selections.get('select_fluxo',''), '—')}\n\n"
            "Confirma e inicia a geração?"
        )


# ---------------------------------------------------------------------------
# Ponte de aprovação — usa o ÚNICO loop de polling do bot (evita corrida de
# getUpdates entre dois consumidores no mesmo bot token).
# ---------------------------------------------------------------------------

class BotApprovalBridge:
    """Interface compatível com TelegramApproval, porém sem polling próprio.

    O envio de mídia/mensagem é síncrono (requests, na thread do orquestrador).
    A decisão do usuário chega pelo loop principal do bot via fila thread-safe.
    """

    def __init__(self, bot: "CampaignBot"):
        self.bot = bot
        self.chat_id = bot.chat_id
        self._base = bot._base

    def _send_message(self, text: str, reply_markup: dict | None = None):
        payload = {"chat_id": self.chat_id, "text": text[:4096], "parse_mode": "Markdown"}
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        try:
            requests.post(f"{self._base}/sendMessage", data=payload, timeout=30)
        except Exception as e:
            print(f"[Bridge] erro sendMessage: {e}")

    def _send_asset(self, asset_path: str, caption: str, reply_markup: dict):
        is_video = asset_path.lower().endswith(".mp4")
        method = "sendVideo" if is_video else "sendPhoto"
        field = "video" if is_video else "photo"
        try:
            with open(asset_path, "rb") as f:
                content = f.read()
            files = {
                field: (
                    os.path.basename(asset_path),
                    content,
                    "video/mp4" if is_video else "image/jpeg",
                )
            }
            data = {
                "chat_id": self.chat_id,
                "caption": caption[:1024],
                "parse_mode": "Markdown",
                "reply_markup": json.dumps(reply_markup),
            }
            requests.post(f"{self._base}/{method}", data=data, files=files, timeout=180)
        except Exception as e:
            print(f"[Bridge] erro {method}: {e}")

    def aprovar_sincronamente(
        self,
        asset_path: str,
        headline: str,
        copy: str,
        job_id: str,
        timeout_segundos: int = 3600,
        audio_path: str | None = None,
    ) -> dict:
        if not os.path.exists(asset_path):
            print(f"❌ [Bridge] Asset não encontrado: {asset_path}")
            return {"action": "reject", "motivo": "asset_ausente"}

        copy_resumo = copy if len(copy) <= 300 else copy[:300] + "..."
        caption = (
            f"*APROVAÇÃO — Guardian AI*\n\n"
            f"*Headline:* {headline}\n\n"
            f"*Copy:* {copy_resumo}\n\n"
            f"Job: `{job_id}`"
        )
        teclado = {
            "inline_keyboard": [
                [{"text": "✅ APROVAR", "callback_data": f"A:{job_id}"}],
                [{"text": "✏️ MELHORAR (envie texto)", "callback_data": f"M:{job_id}"}],
                [{"text": "❌ REJEITAR", "callback_data": f"R:{job_id}"}],
            ]
        }

        result_q: _queue.Queue = _queue.Queue(maxsize=1)
        self.bot.register_approval(job_id, result_q)
        print(f"📲 [Bridge] Enviando para aprovação (Job {job_id})...")
        self._send_asset(asset_path, caption, teclado)
        try:
            decision = result_q.get(timeout=timeout_segundos)
        except _queue.Empty:
            self._send_message(f"⏱️ Timeout — Job {job_id} não aprovado a tempo.")
            decision = {"action": "timeout"}
        finally:
            self.bot.clear_approval(job_id)
        return decision

    def notificar_sync(self, mensagem: str):
        self._send_message(mensagem)


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------

class CampaignBot:
    def __init__(self):
        self.token   = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = str(os.getenv("TELEGRAM_CHAT_ID", ""))
        if not self.token or not self.chat_id:
            raise EnvironmentError(
                "TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID precisam estar no .env"
            )
        self._base   = f"{TELEGRAM_API}{self.token}"
        self.session = Session()
        self._pipeline_lock = asyncio.Lock()
        self.pending_approval: dict | None = None

    # -----------------------------------------------------------------------
    # Coordenação de aprovação (chamado pela thread do orquestrador)
    # -----------------------------------------------------------------------

    def register_approval(self, job_id: str, result_queue: _queue.Queue):
        self.pending_approval = {"job_id": job_id, "queue": result_queue, "awaiting_text": False}

    def clear_approval(self, job_id: str):
        if self.pending_approval and self.pending_approval.get("job_id") == job_id:
            self.pending_approval = None

    # -----------------------------------------------------------------------
    # HTTP helpers
    # -----------------------------------------------------------------------

    async def _post(self, session: aiohttp.ClientSession, method: str, **kwargs) -> dict:
        url = f"{self._base}/{method}"
        try:
            async with session.post(url, json=kwargs, timeout=aiohttp.ClientTimeout(total=30)) as r:
                return await r.json()
        except Exception as e:
            print(f"[Bot] Erro HTTP {method}: {e}")
            return {}

    async def _get_updates(self, session: aiohttp.ClientSession, offset: int, timeout: int = 25) -> list:
        params = {"offset": offset, "timeout": timeout, "allowed_updates": ["message", "callback_query"]}
        try:
            async with session.get(
                f"{self._base}/getUpdates",
                params=params,
                timeout=aiohttp.ClientTimeout(total=timeout + 10),
            ) as r:
                data = await r.json()
                return data.get("result", [])
        except Exception:
            return []

    async def _send(
        self,
        session: aiohttp.ClientSession,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str | None = "Markdown",
    ):
        kwargs: dict[str, Any] = {"chat_id": self.chat_id, "text": text}
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        if reply_markup:
            kwargs["reply_markup"] = reply_markup
        await self._post(session, "sendMessage", **kwargs)

    async def _answer_callback(
        self, session: aiohttp.ClientSession, cb_id: str, text: str = "", show_alert: bool = False
    ):
        await self._post(
            session, "answerCallbackQuery",
            callback_query_id=cb_id, text=text, show_alert=show_alert,
        )

    # -----------------------------------------------------------------------
    # Teclado inline
    # -----------------------------------------------------------------------

    def _keyboard_for_step(self, step: str) -> dict:
        rows = [
            [{"text": label, "callback_data": f"WIZ:{step}:{id_interno}"}]
            for label, _, id_interno in OPCOES[step]
        ]
        return {"inline_keyboard": rows}

    def _keyboard_confirm(self) -> dict:
        return {
            "inline_keyboard": [
                [{"text": "INICIAR CAMPANHA", "callback_data": "WIZ:confirm:yes"}],
                [{"text": "Recomeçar",        "callback_data": "WIZ:restart:yes"}],
            ]
        }

    # -----------------------------------------------------------------------
    # Lógica do wizard
    # -----------------------------------------------------------------------

    async def _send_step(self, session: aiohttp.ClientSession, step: str):
        await self._send(session, TITULOS[step], self._keyboard_for_step(step))

    def _diagnostico_versao(self) -> str:
        """Diagnóstico definitivo: prova qual código está realmente carregado."""
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            git_hash = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=repo_dir, capture_output=True, text=True, timeout=10,
            ).stdout.strip() or "?"
        except Exception:
            git_hash = "?"

        try:
            import mkt_agent_01
            mkt_file = mkt_agent_01.__file__
            src = open(mkt_file, encoding="utf-8").read()
            src_hash = hashlib.md5(src.encode("utf-8")).hexdigest()[:8]
            tem_card_layout = "✅" if "_card_layout" in src else "❌ (CÓDIGO ANTIGO!)"
        except Exception as e:
            mkt_file = f"erro: {e}"
            src_hash = "?"
            tem_card_layout = "?"

        return (
            f"*Versão em execução:*\n"
            f"Fábrica: v{MEDIA_FACTORY_VERSION}\n"
            f"Orquestrador: v{ORCHESTRATOR_VERSION}\n"
            f"git: `{git_hash}`\n\n"
            f"*Código real carregado:*\n"
            f"arquivo: `{mkt_file}`\n"
            f"hash fonte: `{src_hash}`\n"
            f"layout novo (_card_layout): {tem_card_layout}"
        )

    async def _handle_approval_update(self, session: aiohttp.ClientSession, upd: dict) -> bool:
        """Roteia callbacks/texto de aprovação para a campanha em execução.
        Retorna True se o update foi consumido pelo fluxo de aprovação."""
        pa = self.pending_approval
        if not pa:
            return False

        if cb := upd.get("callback_query"):
            data = cb.get("data", "")
            code = data.split(":")[0] if ":" in data else ""
            if code not in ("A", "M", "R"):
                return False
            print(f"[Approval] callback code={code} job={pa.get('job_id')} data={data}")

            # Toast instantâneo (não depende de Markdown/mensagem — sempre visível)
            toast = {"A": "Aprovado ✅", "R": "Rejeitado ❌", "M": "Envie o texto da melhoria ✏️"}[code]
            await self._answer_callback(session, cb["id"], text=toast)

            msg_id = cb.get("message", {}).get("message_id")
            chat_id = cb.get("message", {}).get("chat", {}).get("id")
            if msg_id and chat_id:
                await self._post(
                    session, "editMessageReplyMarkup",
                    chat_id=chat_id, message_id=msg_id, reply_markup={"inline_keyboard": []},
                )

            # Confirmações em texto plano (job_id tem underscores que quebram Markdown)
            if code == "A":
                await self._send(session, f"✅ Aprovado! (Job {pa['job_id']})", parse_mode=None)
                self._resolve_approval(pa, {"action": "approve"})
            elif code == "R":
                await self._send(session, f"❌ Rejeitado! (Job {pa['job_id']})", parse_mode=None)
                self._resolve_approval(pa, {"action": "reject"})
            elif code == "M":
                pa["awaiting_text"] = True
                await self._send(
                    session,
                    "✏️ Descreva a melhoria (responda em texto):\n\n"
                    "• Layout/card (texto cortado)\n"
                    "• Copy (headline, roteiro)\n"
                    "• Imagem/cena",
                    parse_mode=None,
                )
            return True

        if msg := upd.get("message"):
            if not pa.get("awaiting_text"):
                return False
            texto = msg.get("text", "").strip()
            if texto and not texto.startswith("/"):
                print(f"[Approval] improve text job={pa.get('job_id')}: {texto[:60]}")
                await self._send(session, f"📝 Recebido! Regenerando... (Job {pa['job_id']})", parse_mode=None)
                self._resolve_approval(pa, {"action": "improve", "prompt": texto})
                return True

        return False

    def _resolve_approval(self, pa: dict, decision: dict):
        try:
            pa["queue"].put_nowait(decision)
        except _queue.Full:
            pass

    async def _handle_command(self, session: aiohttp.ClientSession, text: str):
        cmd = text.strip().lower().split()[0]

        if cmd == "/nova":
            if self.session.running:
                await self._send(session, "Já existe uma campanha em execução. Use /status para verificar.")
                return
            self.session.reset()
            self.session.step = STEPS[0]
            await self._send(session, "Iniciando nova campanha — siga as etapas abaixo:")
            await self._send_step(session, STEPS[0])

        elif cmd == "/status":
            if self.session.running:
                await self._send(session, "Campanha em execução. Aguarde o preview de aprovação.")
            elif self.session.step == "idle":
                await self._send(session, "Nenhuma campanha ativa. Use /nova para iniciar.")
            else:
                idx = STEPS.index(self.session.step) + 1 if self.session.step in STEPS else "?"
                await self._send(session, f"Wizard em andamento — etapa {idx}/6. Selecione uma opção.")

        elif cmd == "/cancelar":
            self.session.reset()
            await self._send(session, "Sessão reiniciada. Use /nova para começar.")

        elif cmd == "/atualizar":
            await self._handle_update(session)

        elif cmd == "/versao":
            await self._send(session, self._diagnostico_versao())

        elif cmd == "/ajuda":
            await self._send(
                session,
                "*Comandos disponíveis:*\n\n"
                "/nova — iniciar nova campanha\n"
                "/status — verificar status atual\n"
                "/cancelar — cancelar e reiniciar\n"
                "/atualizar — baixar código novo do GitHub e reiniciar\n"
                "/versao — exibir versão do código em execução\n"
                "/ajuda — esta mensagem",
            )

    async def _handle_callback(self, session: aiohttp.ClientSession, cb: dict):
        data  = cb.get("data", "")
        cb_id = cb["id"]

        # Callback de aprovação (A:/M:/R:) que chegou aqui => não há aprovação ativa
        if data[:1] in ("A", "M", "R") and ":" in data:
            print(f"[Approval] callback SEM aprovação ativa: {data} (pending={self.pending_approval})")
            await self._answer_callback(
                session, cb_id,
                text="Esta aprovação expirou ou já foi respondida.",
                show_alert=True,
            )
            return

        if not data.startswith("WIZ:"):
            return

        parts = data.split(":", 2)
        if len(parts) < 3:
            return
        _, step, value = parts

        await self._answer_callback(session, cb_id)

        if step == "restart":
            self.session.reset()
            self.session.step = STEPS[0]
            await self._send(session, "Reiniciando wizard...")
            await self._send_step(session, STEPS[0])
            return

        if step == "confirm" and value == "yes":
            async with self._pipeline_lock:
                if self.session.running:
                    await self._send(session, "⚠️ Campanha já em execução. Aguarde o preview.")
                    return
                config = self.session.to_config()
                self.session.running = True
                self.session.step = "running"
                msg_id = cb.get("message", {}).get("message_id")
                chat_id = cb.get("message", {}).get("chat", {}).get("id")

            # Remove o teclado inline para bloquear novos cliques no mesmo botão
            if msg_id and chat_id:
                await self._post(
                    session, "editMessageReplyMarkup",
                    chat_id=chat_id, message_id=msg_id, reply_markup={"inline_keyboard": []},
                )
            await self._send(session, "✅ Campanha iniciada! Aguarde o preview para aprovação...")
            t = threading.Thread(target=self._run_pipeline, args=(config,), daemon=True)
            self.session.thread = t
            t.start()
            return

        if step not in STEPS:
            return

        msg_id = cb.get("message", {}).get("message_id")
        chat_id = cb.get("message", {}).get("chat", {}).get("id")

        # Clique numa etapa já concluída: apenas remove o teclado obsoleto (sem poluir o chat)
        if self.session.step != step:
            if msg_id and chat_id:
                await self._post(
                    session, "editMessageReplyMarkup",
                    chat_id=chat_id, message_id=msg_id, reply_markup={"inline_keyboard": []},
                )
            return

        # Registra a escolha e desativa o teclado desta etapa (impede recliques/duplicatas)
        self.session.selections[step] = value
        if msg_id and chat_id:
            await self._post(
                session, "editMessageText",
                chat_id=chat_id, message_id=msg_id,
                text=f"{TITULOS[step]}\n\n✅ *{self._label_for(step, value)}*",
                parse_mode="Markdown",
            )

        idx = STEPS.index(step)
        if idx + 1 < len(STEPS):
            next_step = STEPS[idx + 1]
            self.session.step = next_step
            await self._send_step(session, next_step)
        else:
            self.session.step = "confirm"
            await self._send(session, self.session.summary(), self._keyboard_confirm())

    def _label_for(self, step: str, value: str) -> str:
        for label, _val, id_interno in OPCOES.get(step, []):
            if id_interno == value:
                return label
        return value

    # -----------------------------------------------------------------------
    # Atualização remota via git pull + restart
    # -----------------------------------------------------------------------

    async def _handle_update(self, session: aiohttp.ClientSession):
        """Executa git pull e reinicia o processo do bot."""
        if self.session.running:
            await self._send(session, "⚠️ Campanha em execução. Aguarde o fim antes de atualizar.")
            return

        await self._send(session, "🔄 Verificando atualizações no GitHub...")
        repo_dir = os.path.dirname(os.path.abspath(__file__))

        try:
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            saida = (result.stdout + result.stderr).strip()[:1000]
        except subprocess.TimeoutExpired:
            await self._send(session, "❌ git pull demorou demais (timeout 60s).")
            return
        except Exception as e:
            await self._send(session, f"❌ Erro ao executar git pull: {e}")
            return

        if result.returncode != 0:
            await self._send(session, f"❌ git pull falhou:\n```\n{saida}\n```")
            return

        if "Already up to date" in saida:
            await self._send(session, f"✅ Código já está atualizado:\n```\n{saida}\n```")
            return

        await self._send(session, f"✅ Código atualizado:\n```\n{saida}\n```\n\n♻️ Reiniciando bot...")
        # Pequena pausa para garantir que a mensagem seja entregue antes do restart
        await asyncio.sleep(2)
        # Substitui o processo atual pelo mesmo script — reinício limpo sem perder o PID do systemd
        os.execv(sys.executable, [sys.executable] + sys.argv)

    # -----------------------------------------------------------------------
    # Execução do pipeline em thread separada
    # -----------------------------------------------------------------------

    def _run_pipeline(self, config: dict):
        try:
            from campaign_orchestrator import CampaignOrchestrator
            orch = CampaignOrchestrator()
            bridge = BotApprovalBridge(self)
            orch.execute_automated_pipeline(config=config, telegram_override=bridge)
        except Exception as e:
            print(f"[Bot] Erro no pipeline: {e}")
            self._notify_error(str(e))
        finally:
            self.session.running = False
            self.session.step = "idle"
            self.pending_approval = None

    def _notify_error(self, msg: str):
        async def _do():
            async with aiohttp.ClientSession() as s:
                await self._post(
                    s, "sendMessage",
                    chat_id=self.chat_id,
                    text=f"Erro no pipeline: {msg}",
                )
        try:
            asyncio.run(_do())
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Loop principal de polling
    # -----------------------------------------------------------------------

    async def run(self):
        print("[Bot] Guardian AI Campaign Bot iniciado. Envie /nova no Telegram.")
        offset = 0
        async with aiohttp.ClientSession() as session:
            # Descartar updates antigos acumulados (timeout=0 → retorno imediato)
            updates = await self._get_updates(session, -1, timeout=0)
            if updates:
                offset = updates[-1]["update_id"] + 1

            await self._send(session, "Bot iniciado. Use /nova para criar uma campanha.")

            while True:
                try:
                    updates = await self._get_updates(session, offset)
                except Exception as e:
                    print(f"[Bot] Erro ao buscar updates: {e}")
                    await asyncio.sleep(5)
                    continue

                for upd in updates:
                    offset = upd["update_id"] + 1
                    try:
                        # Valida origem (mesmo chat) antes de qualquer roteamento
                        chat = str(
                            upd.get("message", {}).get("chat", {}).get("id", "")
                            or upd.get("callback_query", {}).get("message", {}).get("chat", {}).get("id", "")
                        )
                        if chat and chat != self.chat_id:
                            continue

                        # Aprovação de campanha tem prioridade sobre o wizard
                        if await self._handle_approval_update(session, upd):
                            continue

                        if msg := upd.get("message"):
                            text = msg.get("text", "")
                            if text.startswith("/"):
                                await self._handle_command(session, text)

                        elif cb := upd.get("callback_query"):
                            await self._handle_callback(session, cb)
                    except Exception as e:
                        print(f"[Bot] Erro ao processar update: {e}")


def main():
    bot = CampaignBot()
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
