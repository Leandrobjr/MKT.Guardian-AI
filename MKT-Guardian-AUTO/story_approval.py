"""Formatação compartilhada para aprovação da estória (pré-produção)."""

from __future__ import annotations


def format_story_telegram(creative_data: dict, config: dict, job_id: str) -> str:
    copy = creative_data.get("desenvolvimento_copy", "")
    copy_show = copy if len(copy) <= 900 else copy[:900] + "..."
    cena = creative_data.get("direcao_arte_emocional", "")
    cena_show = cena if len(cena) <= 400 else cena[:400] + "..."
    combo = creative_data.get("campaign_combo", config.get("_campaign_context", {}).get("combo_key", ""))
    return (
        "*APROVAÇÃO DA ESTÓRIA* (antes de vídeo/áudio)\n\n"
        f"*Combo:* `{combo}`\n"
        f"*Público:* {config.get('publico', '—')}\n"
        f"*Golpe:* {config.get('golpe', '—')}\n\n"
        f"*Headline:* {creative_data.get('gancho_atencao_inicial', '')}\n\n"
        f"*Roteiro:* {copy_show}\n\n"
        f"*Card golpista:* {creative_data.get('texto_card_notificacao', '')}\n"
        f"*Personagem:* {creative_data.get('genero_personagem_visual', '')}\n"
        f"*CTA botão:* {creative_data.get('texto_botao_conversao', '')}\n\n"
        f"*Cena (resumo):* {cena_show}\n\n"
        f"Job: `{job_id}`\n"
        "_Nenhum vídeo/áudio será gerado até você aprovar._"
    )


def story_keyboard(job_id: str) -> dict:
    return {
        "inline_keyboard": [
            [{"text": "✅ APROVAR ESTÓRIA", "callback_data": f"A:{job_id}"}],
            [{"text": "✏️ SOLICITAR CORREÇÃO (envie texto)", "callback_data": f"M:{job_id}"}],
            [{"text": "❌ REJEITAR", "callback_data": f"R:{job_id}"}],
        ]
    }
