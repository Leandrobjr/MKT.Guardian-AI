"""Regeneração segura de assets solicitados pelo Desktop."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from campaign_catalog import CampaignCatalog
from campaign_history import CampaignHistory
from campaign_coherence import align_headline_gender_with_roteiro
from channel_presets import resolve_channel_preset
from env_loader import load_project_env
from mkt_agent_01 import MediaFactory
from opencode_client import HybridAIClient
from supabase_campaign_bridge import SupabaseCampaignBridge
from tts_narration import resolve_overlay_cta
from visual_quality_audit import GeminiVisualQualityAuditor


class CampaignRevisionError(RuntimeError):
    """Erro ao aplicar uma solicitação de ajuste editorial."""


class CampaignRevisionService:
    """Regera visual, audita e devolve a campanha para aprovação."""

    _CTA_BY_PUBLICO = {
        "idosos": "TESTE GRÁTIS — PROTEJA SEU WHATSAPP AGORA!",
        "pais": "TESTE GRÁTIS — PROTEJA O WHATSAPP DOS SEUS FILHOS!",
        "empresarios": "TESTE GRÁTIS — PROTEJA SEU WHATSAPP BUSINESS!",
        "escolas": "TESTE GRÁTIS — PROTEJA O WHATSAPP DA SUA ESCOLA!",
    }
    _LAYOUT_FEEDBACK_MARKERS = (
        "card",
        "mensagem final",
        "headline",
        "manchete",
        "pronome",
        "gênero",
        "genero",
        "endereço",
        "endereco",
        "site",
        "grafia",
        "fonte",
        "tamanho",
        "visualização",
        "visualizacao",
    )

    _SERIOUS_EXPRESSION_RULE = (
        "The protagonist must have a worried, serious and tense expression compatible "
        "with receiving a bank fraud alert: furrowed eyebrows, pressed lips and focused "
        "eyes on the phone. Absolutely no smile, happiness, contentment or relaxed pose."
    )

    _PHONE_SCREEN_RULE = (
        "Exactly one physical smartphone, fully inside the frame with visible margin. "
        "Use a softly defocused WhatsApp-style interface with no readable words, "
        "letters, logos, UI labels, chat bubbles, or message text inside the scene-base. "
        "The exact message is rendered only by the post-production compositor."
    )

    def __init__(
        self,
        base_dir: str,
        *,
        catalog: CampaignCatalog,
        bridge: SupabaseCampaignBridge,
    ) -> None:
        load_project_env()
        self.base_dir = os.path.realpath(base_dir)
        self.catalog = catalog
        self.bridge = bridge
        self.history = CampaignHistory(self.base_dir)

    def _history_snapshot(self, campaign_id: str) -> dict[str, Any]:
        rows = [
            row
            for row in self.history.get_recent(limit=100)
            if row.get("campaign_id") == campaign_id
        ]
        if not rows:
            raise CampaignRevisionError(
                "Snapshot local da campanha não encontrado para regeneração."
            )
        return rows[-1]

    @staticmethod
    def _asset_paths(current: dict[str, Any]) -> dict[str, str]:
        asset_path = str(current.get("asset_path") or "")
        if not asset_path:
            raise CampaignRevisionError("Asset local da campanha não encontrado.")
        path = Path(asset_path)
        basename = path.stem
        output_dir = path.parent
        work_dir = output_dir / "_work"
        return {
            "basename": basename,
            "commercial_video_file": str(path) if path.suffix.lower() == ".mp4" else "",
            "static_image_file": str(output_dir / f"{basename}.jpg"),
            "base_image_file": str(output_dir / f"{basename}_base.jpg"),
            "audio_file": str(output_dir / f"{basename}.mp3"),
            "kling_raw_file": str(work_dir / f"{basename}_kling_raw.mp4"),
        }

    def _build_creative(
        self,
        campaign: dict[str, Any],
        current: dict[str, Any],
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        reference = snapshot.get("visual_reference") or {}
        frase = str(snapshot.get("frase_golpista") or "")
        publico = str(campaign.get("publico") or current.get("publico") or "")
        golpe = str(campaign.get("golpe") or current.get("golpe") or "")
        canal = str(campaign.get("canal") or current.get("canal") or "")
        midia = str(campaign.get("midia") or current.get("midia") or "")
        preset = resolve_channel_preset(canal, midia)
        cena = " ".join(
            item
            for item in (
                str(snapshot.get("ambiente") or ""),
                str(reference.get("enquadramento") or ""),
            )
            if item
        )
        regras = {
            "regras_obrigatorias": [
                self._PHONE_SCREEN_RULE,
                self._SERIOUS_EXPRESSION_RULE,
            ],
            "proibicoes": [
                *(reference.get("rejeitado") or []),
                "readable text, chat bubbles, message text or logos inside the phone screen",
                "smiling, happy, content or relaxed facial expression",
            ],
            "estilo_fotografico": reference.get("estilo_fotografico", ""),
        }
        cena = f"{cena}. {self._SERIOUS_EXPRESSION_RULE}"
        headline = self._resolve_headline(campaign, current, snapshot)
        cta = self._CTA_BY_PUBLICO.get(
            publico,
            "TESTE GRÁTIS — PROTEJA SEU WHATSAPP AGORA!",
        )
        creative = {
            "campaign_id": campaign.get("campaign_id"),
            "publico_slug": publico,
            "golpe_id": golpe,
            "canal_veiculacao_selecionado": canal,
            "tipo_midia_selecionada": midia,
            "preset_midia": preset,
            "gancho_atencao_inicial": headline,
            "desenvolvimento_copy": campaign.get("roteiro") or current.get("roteiro") or "",
            "texto_card_notificacao": frase,
            "frase_destaque_golpista": frase,
            "direcao_arte_emocional": cena,
            "regras_visuais": regras,
            "phone_screen_clause": self._PHONE_SCREEN_RULE,
            "visual_reference": reference,
            "visual_reference_id": snapshot.get("visual_reference_id", ""),
            "ambiente_cena": snapshot.get("ambiente", ""),
            "link_conversao": "https://guardian-ai.app",
            "texto_botao_conversao": cta,
            "chamada_para_acao_cta": cta,
            "creative_brief": {
                "publico": publico,
                "golpe": golpe,
                "personagem": reference.get("persona_id", ""),
                "cenario": snapshot.get("ambiente", ""),
            },
        }
        creative["chamada_para_acao_cta"] = resolve_overlay_cta(creative)
        creative["texto_botao_conversao"] = creative["chamada_para_acao_cta"]
        return creative

    @staticmethod
    def _resolve_headline(
        campaign: dict[str, Any],
        current: dict[str, Any],
        snapshot: dict[str, Any],
    ) -> str:
        """Preserva a headline editorial escolhida antes de uma revisão."""
        metadata = campaign.get("metadata") or {}
        for value in (
            snapshot.get("headline_escolhida"),
            metadata.get("headline"),
            current.get("headline"),
            snapshot.get("headline"),
        ):
            text = str(value or "").strip()
            if text:
                roteiro = str(
                    campaign.get("roteiro")
                    or current.get("roteiro")
                    or snapshot.get("copy_hook")
                    or ""
                )
                return align_headline_gender_with_roteiro(text, roteiro)
        return ""

    @classmethod
    def _caption_with_headline(
        cls,
        campaign: dict[str, Any],
        headline: str,
        cta: str,
        url: str,
    ) -> str:
        caption = cls._caption_with_cta(campaign, cta, url)
        lines = caption.splitlines()
        if lines:
            lines[0] = headline
            return "\n".join(lines)
        return f"{headline}\n\n{cta} — {url}"

    @classmethod
    def _is_layout_only_feedback(cls, feedback: str) -> bool:
        text = (feedback or "").casefold()
        for restriction in (
            "não alterar a cena",
            "nao alterar a cena",
            "não mudar a cena",
            "nao mudar a cena",
            "não alterar o fundo",
            "nao alterar o fundo",
        ):
            text = text.replace(restriction, "")
        return (
            any(marker in text for marker in cls._LAYOUT_FEEDBACK_MARKERS)
            and not any(
                marker in text
                for marker in (
                    "alterar a cena",
                    "mudar a cena",
                    "trocar a cena",
                    "alterar o fundo",
                    "mudar o fundo",
                    "trocar o fundo",
                    "alterar personagem",
                    "trocar personagem",
                    "regenerar personagem",
                    "personagem",
                    "expressão",
                    "expressao",
                    "sorriso",
                    "sorrindo",
                    "feliz",
                    "contente",
                    "preocupada",
                    "preocupado",
                    "seriedade",
                    "séria",
                    "seria",
                    "tensa",
                    "tenso",
                    "rosto",
                    "melhorar o rosto",
                    "trocar o telefone",
                    "gerar outra imagem",
                    "nova imagem",
                )
            )
        )

    @staticmethod
    def _caption_with_cta(campaign: dict[str, Any], cta: str, url: str) -> str:
        caption = str(campaign.get("legenda") or "")
        lines = caption.splitlines()
        for index, line in enumerate(lines):
            if "teste grátis" in line.casefold():
                lines[index] = f"{cta} — {url}"
                break
        return "\n".join(lines)

    @staticmethod
    def _qa_evidence(audit: Any) -> dict[str, Any]:
        return {
            "multimodal_available": bool(audit.enabled and not audit.skipped),
            "multimodal_passed": bool(audit.passed),
            "overall_score": audit.overall_score,
            "model": audit.model,
            "provider": audit.provider,
            "findings": [finding.__dict__ for finding in audit.findings],
            "recommended_stage": audit.recommended_stage,
        }

    def _persist_revision(
        self,
        campaign: dict[str, Any],
        current: dict[str, Any],
        creative: dict[str, Any],
        assets: dict[str, Any],
        audit: Any,
    ) -> dict[str, Any]:
        assets["qa_evidence"] = self._qa_evidence(audit)
        revision = int(current.get("version", 0)) + 1
        config = {
            "_campaign_id": campaign.get("campaign_id"),
            "publico_slug": campaign.get("publico", ""),
            "golpe_id": campaign.get("golpe", ""),
            "canal": campaign.get("canal", ""),
            "midia": campaign.get("midia", ""),
            "preset_midia": creative.get("preset_midia") or {},
            "_revision": revision,
            "_caption": creative.get("caption") or campaign.get("legenda", ""),
        }
        record = self.catalog.update(
            str(campaign["campaign_id"]),
            "AGUARDANDO_APROVACAO_FINAL",
            config,
            creative,
            assets,
            revision=revision,
            actor="linux_worker_revision",
        )
        self.bridge.sync_campaign(record)
        return {
            "status": "AGUARDANDO_APROVACAO_FINAL",
            "campaign_id": campaign.get("campaign_id"),
            "version": record.get("version"),
            "provider": audit.provider,
            "qa_score": audit.overall_score,
        }

    def apply(
        self,
        campaign: dict[str, Any],
        current: dict[str, Any],
        feedback: str,
    ) -> dict[str, Any]:
        snapshot = self._history_snapshot(str(campaign.get("campaign_id") or ""))
        creative = self._build_creative(campaign, current, snapshot)
        prior_assets = self._asset_paths(current)
        client = None
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if api_key:
            from google import genai

            client = genai.Client(api_key=api_key)
        router = HybridAIClient(
            client,
            gemini_text_model=os.getenv("GEMINI_MODEL_TEXTO", "gemini-3.6-flash"),
            gemini_vision_model=os.getenv("GEMINI_MODEL_QA", "gemini-3.6-flash"),
        ) if client else None
        auditor = (
            GeminiVisualQualityAuditor(
                client,
                model=os.getenv("GEMINI_MODEL_QA", "gemini-3.6-flash"),
                enabled=True,
                required=True,
                vision_router=router,
            )
            if client and router
            else None
        )
        if auditor is None:
            raise CampaignRevisionError("GEMINI_API_KEY não configurada para QA.")

        factory = MediaFactory()
        cta = creative["chamada_para_acao_cta"]
        creative["caption"] = self._caption_with_headline(
            campaign,
            creative["gancho_atencao_inicial"],
            cta,
            creative["link_conversao"],
        )
        creative.update(
            {
                "overlay_cta_font_size": 20,
                "overlay_url_font_size": 26,
                "overlay_url_bottom_padding": 26,
            }
        )
        audit_config = {
            "canal": campaign.get("canal", ""),
            "midia": campaign.get("midia", ""),
        }
        if self._is_layout_only_feedback(feedback):
            creative.update(
                {
                    "texto_botao_conversao": cta,
                    "chamada_para_acao_cta": cta,
                    "link_conversao": "https://guardian-ai.app",
                    "overlay_cta_font_size": 20,
                    "overlay_url_font_size": 26,
                    "overlay_url_bottom_padding": 26,
                    "caption": self._caption_with_headline(
                        campaign,
                        creative["gancho_atencao_inicial"],
                        cta,
                        "https://guardian-ai.app",
                    ),
                }
            )
            assets = factory.reapply_overlay_only(creative, prior_assets)
            if not assets.get("recomposed"):
                raise CampaignRevisionError(
                    "A fábrica não conseguiu recompor o card sem alterar a cena."
                )
            audit = None
            for _ in range(2):
                audit = auditor.audit(creative, audit_config, assets)
                if audit.passed:
                    break
            if not audit.passed:
                raise CampaignRevisionError(
                    f"Card reprovado pela QA multimodal ({audit.overall_score}/10)."
                )
            return self._persist_revision(
                campaign, current, creative, assets, audit
            )

        assets: dict[str, Any] = {}
        audit = None
        last_findings = ""
        for attempt in range(1, 3):
            retry_feedback = feedback
            if attempt > 1:
                retry_feedback = (
                    f"{feedback}. REFAÇA A IMAGEM. A QA reprovou a tentativa anterior: "
                    f"{last_findings}"
                )
            assets = factory.regenerate_visual_only(
                creative,
                prior_assets,
                retry_feedback,
                visual_auditor=auditor,
                audit_config=audit_config,
            )
            if not assets.get("visual_regenerated"):
                raise CampaignRevisionError("A fábrica não conseguiu regenerar o visual.")
            audit = auditor.audit(creative, audit_config, assets)
            if audit.passed:
                break
            last_findings = "; ".join(
                finding.reason
                for finding in audit.findings
                if not finding.ok
            )[:1200]
        if audit is None or not audit.passed:
            score = audit.overall_score if audit else "indisponível"
            raise CampaignRevisionError(
                f"Nova versão reprovada pela QA multimodal ({score}/10). "
                f"Achados: {last_findings or 'sem detalhes'}"
            )
        return self._persist_revision(campaign, current, creative, assets, audit)
