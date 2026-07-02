"""
Bot de Aprovação via Telegram — Guardian AI

Fluxo:
  1. Envia o asset (vídeo ou imagem) para o chat do Telegram.
  2. Apresenta 3 botões: APROVAR / MELHORAR / REJEITAR.
  3. Aguarda resposta (polling assíncrono).
  4. MELHORAR: admin envia texto de revisão.
  5. APROVAR: sinaliza para o orquestrador publicar ou concluir.
  6. REJEITAR: descarta o job.
"""

import asyncio
import json
import os
import time

import aiohttp
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_API = "https://api.telegram.org/bot"


class TelegramApproval:
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self._base = f"{TELEGRAM_API}{self.token}"

        if not self.token or not self.chat_id:
            raise EnvironmentError(
                "TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID precisam estar no .env\n"
                "Crie um bot em @BotFather e obtenha o Chat ID via @userinfobot"
            )

    async def _post(self, session: aiohttp.ClientSession, method: str, **kwargs) -> dict:
        url = f"{self._base}/{method}"
        async with session.post(url, json=kwargs, timeout=aiohttp.ClientTimeout(total=30)) as r:
            return await r.json()

    async def _get_updates(self, session: aiohttp.ClientSession, offset: int) -> list:
        url = f"{self._base}/getUpdates"
        params = {"offset": offset, "timeout": 5, "allowed_updates": ["callback_query", "message"]}
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
                data = await r.json()
                return data.get("result", [])
        except Exception:
            return []

    async def _enviar_asset(
        self, session: aiohttp.ClientSession, asset_path: str, caption: str, teclado: dict
    ) -> dict:
        is_video = asset_path.lower().endswith(".mp4")
        method = "sendVideo" if is_video else "sendPhoto"
        field = "video" if is_video else "photo"

        data = aiohttp.FormData()
        data.add_field("chat_id", str(self.chat_id))
        data.add_field("caption", caption[:1024])
        data.add_field("parse_mode", "Markdown")
        data.add_field("reply_markup", json.dumps(teclado))

        with open(asset_path, "rb") as f:
            content = f.read()
        data.add_field(
            field,
            content,
            filename=os.path.basename(asset_path),
            content_type="video/mp4" if is_video else "image/jpeg",
        )

        async with session.post(f"{self._base}/{method}", data=data, timeout=aiohttp.ClientTimeout(total=120)) as r:
            return await r.json()

    async def _enviar_audio(self, session: aiohttp.ClientSession, audio_path: str, caption: str) -> dict:
        """Envia arquivo de áudio (narração) via sendAudio."""
        if not audio_path or not os.path.exists(audio_path):
            return {}
        data = aiohttp.FormData()
        data.add_field("chat_id", str(self.chat_id))
        data.add_field("caption", caption[:1024])
        data.add_field("parse_mode", "Markdown")
        with open(audio_path, "rb") as f:
            content = f.read()
        data.add_field(
            "audio",
            content,
            filename=os.path.basename(audio_path),
            content_type="audio/mpeg",
        )
        async with session.post(f"{self._base}/sendAudio", data=data, timeout=aiohttp.ClientTimeout(total=60)) as r:
            return await r.json()

    async def enviar_para_aprovacao(
        self,
        asset_path: str,
        headline: str,
        copy: str,
        job_id: str,
        timeout_segundos: int = 3600,
        audio_path: str | None = None,
    ) -> dict:
        if not os.path.exists(asset_path):
            print(f"❌ [Telegram] Asset não encontrado: {asset_path}")
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

        async with aiohttp.ClientSession() as session:
            print(f"📲 [Telegram] Enviando para aprovação (Job {job_id})...")
            resp = await self._enviar_asset(session, asset_path, caption, teclado)
            if not resp.get("ok"):
                print(f"❌ [Telegram] Falha ao enviar: {resp}")
                return {"action": "reject", "motivo": "telegram_falhou"}

            updates = await self._get_updates(session, offset=0)
            last_id = updates[-1]["update_id"] if updates else 0
            awaiting_text = False
            start = time.time()

            print(f"⏳ [Telegram] Aguardando resposta (timeout: {timeout_segundos // 60} min)...")

            while time.time() - start < timeout_segundos:
                await asyncio.sleep(3)
                updates = await self._get_updates(session, offset=last_id + 1)

                for upd in updates:
                    last_id = upd["update_id"]

                    if cb := upd.get("callback_query"):
                        data = cb.get("data", "")
                        if job_id not in data:
                            continue
                        await self._post(session, "answerCallbackQuery", callback_query_id=cb["id"])
                        code = data.split(":")[0]

                        if code == "A":
                            await self._post(
                                session, "sendMessage", chat_id=self.chat_id,
                                text=f"✅ Aprovado! (Job {job_id})",
                            )
                            return {"action": "approve"}

                        if code == "R":
                            await self._post(
                                session, "sendMessage", chat_id=self.chat_id,
                                text=f"❌ Rejeitado. (Job {job_id})",
                            )
                            return {"action": "reject"}

                        if code == "M":
                            awaiting_text = True
                            await self._post(
                                session, "sendMessage", chat_id=self.chat_id,
                                text=(
                                    "Descreva a melhoria (responda em texto):\n\n"
                                    "• Layout/card (texto cortado): ex. quebrar texto do card\n"
                                    "• Copy (headline, roteiro): ex. headline mais urgente\n"
                                    "• Imagem/cena: ex. trocar cozinha por loja"
                                ),
                            )

                    elif awaiting_text and (msg := upd.get("message")):
                        texto = msg.get("text", "").strip()
                        if texto and not texto.startswith("/"):
                            await self._post(
                                session, "sendMessage", chat_id=self.chat_id,
                                text=f"📝 Recebido! Regenerando... (Job {job_id})",
                            )
                            return {"action": "improve", "prompt": texto}

            await self._post(
                session, "sendMessage", chat_id=self.chat_id,
                text=f"⏱️ Timeout — Job {job_id} não aprovado a tempo.",
            )
            return {"action": "timeout"}

    def aprovar_sincronamente(
        self,
        asset_path: str,
        headline: str,
        copy: str,
        job_id: str,
        timeout_segundos: int = 3600,
        audio_path: str | None = None,
    ) -> dict:
        return asyncio.run(
            self.enviar_para_aprovacao(asset_path, headline, copy, job_id, timeout_segundos, audio_path)
        )

    async def notificar(self, mensagem: str):
        async with aiohttp.ClientSession() as session:
            await self._post(
                session, "sendMessage", chat_id=self.chat_id,
                text=mensagem, parse_mode="Markdown",
            )

    def notificar_sync(self, mensagem: str):
        asyncio.run(self.notificar(mensagem))
