import os
import json
import random
import re
import time
import uuid
from dataclasses import asdict
from google import genai
from google.genai import types
from env_loader import load_project_env

from mkt_agent_01 import MediaFactory
from traffic_manager import TrafficManager
from agent_memory import AgentMemory
from campaign_history import CampaignHistory
from creative_asset_audit import audit_creative_assets, format_audit_result
from creative_brief import HeadlineRotator, build_creative_brief
from feedback_router import (
    classify_improvement,
    correction_tag,
    describe_plan,
    extract_card_message_edit,
    format_menu_conflict,
)
from visual_quality_audit import GeminiVisualQualityAuditor
from visual_variety import VisualVarietyEngine
from channel_presets import (
    format_preset_summary,
    is_video_media,
    resolve_channel_preset,
    validate_channel_media,
)
from tts_narration import strip_written_site_urls, card_solucao_text, NARRATION_CLOSING
from build_info import ORCHESTRATOR_VERSION, print_build_banner
from campaign_coherence import (
    describe_protagonist,
    format_nexo_prompt_block,
    infer_protagonist_gender,
    is_coherent_for_campaign,
    is_coherent,
    is_gender_coherent,
    nexo_score,
    pick_coherent_gancho,
    _gender_from_personagem_field,
    _gender_from_roteiro,
    infer_recipient_gender,
    is_ambiguous_pix_headline,
)
from campaign_context_engine import CampaignContextEngine
from campaign_contract import (
    CampaignContractCatalog,
    CampaignContractError,
    VALID_PUBLICO_SLUGS,
    validate_creative_contract,
)
from scam_library import ScamLibrary
from campaign_catalog import CampaignCatalog
from story_approval import format_story_telegram, story_keyboard
from storyboard import build_storyboard, format_storyboard_compact, format_storyboard_prompt
from copy_lexicon import CopyLexicon
from manual_export import export_tiktok_package

try:
    from telegram_approval import TelegramApproval
except ImportError:
    TelegramApproval = None

try:
    from meta_publisher import MetaPublisher
except ImportError:
    MetaPublisher = None

try:
    from tiktok_publisher import TikTokPublisher
except ImportError:
    TikTokPublisher = None

try:
    from supabase_campaign_bridge import SupabaseBridgeError, SupabaseCampaignBridge
except ImportError:
    SupabaseBridgeError = None
    SupabaseCampaignBridge = None

class CampaignOrchestrator:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    def __init__(self):
        os.chdir(self.BASE_DIR)
        load_project_env()
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = os.getenv("GEMINI_MODEL_TEXTO", "gemini-3.1-flash-lite")
        qa_enabled = os.getenv("GEMINI_QA_ENABLED", "true").lower() in (
            "1", "true", "yes"
        )
        qa_required = os.getenv("GEMINI_QA_REQUIRED", "false").lower() in (
            "1", "true", "yes"
        )
        self.visual_quality_auditor = GeminiVisualQualityAuditor(
            self.client if self.api_key else None,
            model=os.getenv("GEMINI_MODEL_QA", "gemini-3.6-flash"),
            enabled=qa_enabled and bool(self.api_key),
            required=qa_required,
            minimum_score=float(os.getenv("GEMINI_QA_MIN_SCORE", "7.0")),
        )

        self.context_path = os.path.join(self.BASE_DIR, "contexto_negocio", "guardian_base.json")
        self.context_data = self._load_business_context()
        self.copy_lexicon = self._load_copy_lexicon()
        self.lexicon_guard = CopyLexicon(self.BASE_DIR)
        self.md_context = self._load_markdown_context()

        self.media_factory = MediaFactory()
        self.traffic_manager = TrafficManager()
        self.memory = AgentMemory(self.BASE_DIR)
        self.history = CampaignHistory(self.BASE_DIR)
        self.catalog = CampaignCatalog(self.BASE_DIR)
        self.headline_rotator = HeadlineRotator(self.BASE_DIR, self.history)
        self.visual_variety = VisualVarietyEngine(self.BASE_DIR, self.history)
        self.scam_library = ScamLibrary(self.BASE_DIR, self.history)
        self.contract_catalog = CampaignContractCatalog(self.BASE_DIR)
        self.context_engine = CampaignContextEngine(self.BASE_DIR)
        self.supabase_bridge = None
        if SupabaseCampaignBridge is not None:
            try:
                self.supabase_bridge = SupabaseCampaignBridge.from_env(self.BASE_DIR)
            except (EnvironmentError, SupabaseBridgeError) as exc:
                print(f"⚠️ Ponte Supabase desativada: {exc}")
        self.max_revisoes = int(os.getenv("MAX_REVISOES", "3"))
        self.telegram_timeout = int(os.getenv("TELEGRAM_TIMEOUT", "3600"))
        self.telegram = None
        self.publisher = None
        self.tiktok_publisher = None

    def _init_telegram(self) -> bool:
        if TelegramApproval is None:
            print("⚠️ telegram_approval.py não encontrado — aprovação desativada.")
            return False
        try:
            self.telegram = TelegramApproval()
            return True
        except EnvironmentError as e:
            print(f"⚠️ Telegram desativado: {e}")
            return False

    def _init_publisher(self) -> bool:
        if MetaPublisher is None:
            print("⚠️ meta_publisher.py não encontrado — publicação desativada.")
            return False
        try:
            self.publisher = MetaPublisher()
            preflight = self.publisher.preflight()
            if not preflight.get("ok"):
                print(f"⚠️ Meta desativado no preflight: {preflight.get('erro', 'falha desconhecida')}")
                self.publisher = None
                return False
            return True
        except EnvironmentError as e:
            print(f"⚠️ Meta Publisher desativado: {e}")
            return False

    def _init_tiktok_publisher(self) -> bool:
        if TikTokPublisher is None:
            print("⚠️ tiktok_publisher.py não encontrado — publicação TikTok desativada.")
            return False
        try:
            self.tiktok_publisher = TikTokPublisher()
            return True
        except EnvironmentError as e:
            print(f"⚠️ TikTok Publisher desativado: {e}")
            return False

    def _load_markdown_context(self) -> str:
        """Carrega documentos estratégicos de contexto_negocio/ para enriquecer o copy."""
        ctx_dir = os.path.join(self.BASE_DIR, "contexto_negocio")
        partes = []
        for nome in (
            "GOLPES WHATSAPP.md",
            "GOLPES WHATSAPP.md.local.bak",
            "PLANO MKT Guardian AUTO.md",
        ):
            caminho = os.path.join(ctx_dir, nome)
            if os.path.exists(caminho):
                try:
                    with open(caminho, "r", encoding="utf-8") as f:
                        partes.append(f"--- {nome} ---\n{f.read()}")
                except Exception as e:
                    print(f"⚠️ Não foi possível ler {nome}: {e}")
        return "\n\n".join(partes)

    def _load_business_context(self) -> dict:
        if not os.path.exists(self.context_path):
            return {}
        try:
            with open(self.context_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Erro ao ler JSON de contexto: {e}")
            return {}

    def _load_copy_lexicon(self) -> dict:
        path = os.path.join(self.BASE_DIR, "contexto_negocio", "copy_lexicon.json")
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️ Erro ao ler léxico de copy: {e}")
            return {}

    def _build_cta_button(
        self,
        config: dict,
        genero_campanha: str = "neutro",
        campaign_ctx: dict | None = None,
        creative_data: dict | None = None,
    ) -> str:
        narrative = " ".join(
            str((creative_data or {}).get(field) or "")
            for field in (
                "gancho_atencao_inicial",
                "desenvolvimento_copy",
                "texto_card_notificacao",
            )
        ).lower()
        child_gender = ""
        has_female_child = bool(re.search(r"\b(filha|menina)\b", narrative))
        has_male_child = bool(re.search(r"\b(filho|menino)\b", narrative))
        if has_female_child and not has_male_child:
            child_gender = "feminino"
        elif has_male_child and not has_female_child:
            child_gender = "masculino"

        if campaign_ctx and campaign_ctx.get("cta_template"):
            cta = campaign_ctx["cta_template"]
            if campaign_ctx.get("narrativa_parental") and child_gender == "feminino":
                return self._fix_pt_artifacts(
                    cta.replace("SEUS FILHOS", "SUA FILHA").replace("SEU FILHO", "SUA FILHA")
                )
            if campaign_ctx.get("narrativa_parental") and child_gender == "masculino":
                return self._fix_pt_artifacts(
                    cta.replace("SEUS FILHOS", "SEU FILHO").replace("SUA FILHA", "SEU FILHO")
                )
            return self._fix_pt_artifacts(cta)
        publico_slug = config.get("publico_slug", "")
        if publico_slug == "escolas":
            return (
                "PROTEJA SEUS ALUNOS — PAIS USEM GUARDIAN AI. PLANOS PARA GRUPOS DE ALUNOS"
            )
        if publico_slug == "pais":
            if child_gender == "feminino":
                return "TESTE GRÁTIS — PROTEJA O WhatsApp da SUA FILHA, AGORA!"
            if child_gender == "masculino":
                return "TESTE GRÁTIS — PROTEJA O WhatsApp do SEU FILHO, AGORA!"
            return "TESTE GRÁTIS — PROTEJA O WhatsApp dos SEUS FILHOS, AGORA!"
        if publico_slug == "idosos":
            return "TESTE GRÁTIS — PROTEJA SEU WHATSAPP AGORA!"
        if publico_slug == "empresarios":
            return "TESTE GRÁTIS — PROTEJA SEU WHATSAPP BUSINESS AGORA!"
        if publico_slug == "escolas":
            return "PROTEJA SEUS ALUNOS — PAIS USEM GUARDIAN AI. PLANOS PARA GRUPOS DE ALUNOS"
        return "TESTE GRÁTIS — PROTEJA SEU WHATSAPP AGORA!"

    def _apply_gender_pt(self, text: str, feminino: bool) -> str:
        if not text:
            return text
        if feminino:
            pairs = [
                ("NO WHATSAPP DO SEU FILHO", "NO WHATSAPP DA SUA FILHA"),
                ("No WhatsApp do seu filho", "No WhatsApp da sua filha"),
                ("WHATSAPP DO SEU FILHO", "WHATSAPP DA SUA FILHA"),
                ("WhatsApp do SEU FILHO", "WhatsApp da SUA FILHA"),
                ("WhatsApp do seu filho", "WhatsApp da sua filha"),
                ("segurança do seu filho", "segurança da sua filha"),
                ("Segurança do seu filho", "Segurança da sua filha"),
                ("para o seu filho", "para a sua filha"),
                ("Para o seu filho", "Para a sua filha"),
                ("proteja seu filho", "proteja sua filha"),
                ("Proteja seu filho", "Proteja sua filha"),
                ("DO SEU FILHO", "DA SUA FILHA"),
                ("do seu filho", "da sua filha"),
                ("Do seu filho", "Da sua filha"),
                ("no seu filho", "na sua filha"),
                ("No seu filho", "Na sua filha"),
                ("SEU FILHO", "SUA FILHA"),
                ("Seu filho", "Sua filha"),
                ("seu filho", "sua filha"),
            ]
        else:
            pairs = [
                ("NO WHATSAPP DA SUA FILHA", "NO WHATSAPP DO SEU FILHO"),
                ("No WhatsApp da sua filha", "No WhatsApp do seu filho"),
                ("WHATSAPP DA SUA FILHA", "WHATSAPP DO SEU FILHO"),
                ("WhatsApp da SUA FILHA", "WhatsApp do SEU FILHO"),
                ("WhatsApp da sua filha", "WhatsApp do seu filho"),
                ("segurança da sua filha", "segurança do seu filho"),
                ("Segurança da sua filha", "Segurança do seu filho"),
                ("para a sua filha", "para o seu filho"),
                ("Para a sua filha", "Para o seu filho"),
                ("proteja sua filha", "proteja seu filho"),
                ("Proteja sua filha", "Proteja seu filho"),
                ("DA SUA FILHA", "DO SEU FILHO"),
                ("da sua filha", "do seu filho"),
                ("Da sua filha", "Do seu filho"),
                ("na sua filha", "no seu filho"),
                ("Na sua filha", "No seu filho"),
                ("SUA FILHA", "SEU FILHO"),
                ("Sua filha", "Seu filho"),
                ("sua filha", "seu filho"),
            ]
        pairs.sort(key=lambda p: len(p[0]), reverse=True)
        for old, new in pairs:
            text = text.replace(old, new)
        return self._fix_pt_artifacts(text)

    def _fix_pt_artifacts(self, text: str) -> str:
        """Corrige artefatos de concordância após substituição mecânica."""
        text = re.sub(
            r"\b(PROTEJA)\s+(o|a|os|as)\b",
            lambda match: f"{match.group(1)} {match.group(2).upper()}",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\bdo sua\b", "da sua", text, flags=re.IGNORECASE)
        text = re.sub(r"\bno sua\b", "na sua", text, flags=re.IGNORECASE)
        text = re.sub(r"\bo sua\b", "a sua", text, flags=re.IGNORECASE)
        text = re.sub(r"\bdos SEU\b", "do SEU", text)
        text = re.sub(r"\bdos seu\b", "do seu", text)
        text = re.sub(r"\bdos Seu\b", "do Seu", text)
        text = re.sub(r"\bdos SUA\b", "da SUA", text)
        text = re.sub(r"\bdos sua\b", "da sua", text)
        text = re.sub(r"\bdos Sua\b", "da Sua", text)
        text = re.sub(
            r"\balerta (?:o )?seu acesso\b",
            "obtém acesso indevido",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"(Guardian AI[^.!?]*[.!?]\s*)Ela\s+(detecta|alerta|monitora|envia|avisa)",
            r"\1Ele \2",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"(O app[^.!?]*[.!?]\s*)Ela\s+(detecta|alerta|monitora|envia|avisa)",
            r"\1Ele \2",
            text,
            flags=re.IGNORECASE,
        )
        return text

    def _format_product_capabilities_for_prompt(self) -> str:
        cap = self.context_data.get("PRODUTO_E_POSICIONAMENTO", {}).get("capacidades_reais", {})
        lexicon = self.copy_lexicon
        if not cap and not lexicon:
            return ""
        lines = ["CAPACIDADES REAIS DO GUARDIAN AI (NUNCA VIOLAR):"]
        for item in cap.get("faz", []):
            lines.append(f"  ✅ {item}")
        for item in cap.get("nao_faz", []):
            lines.append(f"  ❌ {item}")
        if cap.get("regra_criativo"):
            lines.append(f"  📌 {cap['regra_criativo']}")
        proibidas = lexicon.get("expressoes_proibidas", [])
        if proibidas:
            lines.append("")
            lines.append("GUIA LEXICAL OBRIGATÓRIO — NÃO USAR:")
            for item in proibidas:
                padroes = ", ".join(f'"{p}"' for p in item.get("padroes", []))
                lines.append(f"  ❌ {padroes} — {item.get('motivo', '')}")
        sugeridas = lexicon.get("expressoes_sugeridas", [])
        if sugeridas:
            lines.append("")
            lines.append("GUIA LEXICAL OBRIGATÓRIO — PREFERIR:")
            for item in sugeridas:
                lines.append(f"  ✅ \"{item.get('usar', '')}\"")
        lines.append("")
        lines.append(self.lexicon_guard.format_for_prompt())
        return "\n".join(lines)

    def _enforce_product_truth(self, creative_data: dict) -> dict:
        """Guardian AI detecta e alerta no chat do WhatsApp — nunca bloqueia nem monitora grupos.

        Corrige apenas frases que ATRIBUEM ao produto uma capacidade que ele não tem
        (monitorar/detectar dentro do grupo). NÃO altera frases que já contrastam
        corretamente grupo x chat do WhatsApp (ex.: "não é no grupo, é no chat do WhatsApp"), pois essas
        são justamente os ganchos corretos definidos em campanha_context_matrix.json —
        um regex genérico de "no/do/em grupo" quebrava essas frases e gerava
            contradições do tipo "não acontece em grupos; acontece no chat do WhatsApp".
        """
        capacidade_patterns = [
            (r"\binfiltrad\w+ no grupo\b", "contatando o aluno no chat do WhatsApp"),
            (r"\bpredador\w* no grupo\b", "predador no chat do WhatsApp"),
            (r"\bdetecta\w*\s+(o |a )?invasor\w*\s+no grupo\b", "alerta sobre mensagem suspeita no chat do WhatsApp"),
            (r"\bdetecta\w* (o |a )?invasor\b", "alerta sobre mensagem suspeita no chat do WhatsApp"),
            (r"\bmonitora\w* grupos?\b", "detecta ameaças e envia alerta no chat do WhatsApp"),
            (r"\b(detecta|alerta|notifica)\w*\s+(o |a )?grupo\b", r"\1 o usuário no chat do WhatsApp"),
            (r"\bmonitora\w*\s+(suas\s+|essas\s+|as\s+)?conversas\s+privadas\b", "detecta ameaças e envia um alerta imediato"),
            (r"\bchat\s+privado\b", "chat do WhatsApp"),
            (r"\bconversa\s+privada\b", "conversa no WhatsApp"),
        ]
        for field in ("desenvolvimento_copy", "gancho_atencao_inicial", "chamada_para_acao_cta"):
            if not creative_data.get(field):
                continue
            text = creative_data[field]
            text = re.sub(r"\bbloque\w+\b", "alerta", text, flags=re.IGNORECASE)
            text = re.sub(r"\bimpede\b", "alerta", text, flags=re.IGNORECASE)
            for pattern, repl in capacidade_patterns:
                text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
            # Rede de segurança: se a substituição criar "privad..." repetido perto
            # (ex.: "...conversa no WhatsApp, é no chat do WhatsApp"), remove a redundância.
            text = re.sub(
                r"\b(conversa no WhatsApp|chat do WhatsApp)\b([^.!?]{0,20})\bno privado\b",
                r"\1\2",
                text,
                flags=re.IGNORECASE,
            )
            if field == "desenvolvimento_copy":
                text = strip_written_site_urls(text)
            creative_data[field] = self._fix_pt_artifacts(text)

        creative_data["texto_card_solucao"] = card_solucao_text()
        protected_card = creative_data.get("texto_card_notificacao")
        lexical_data = dict(creative_data)
        lexical_data.pop("texto_card_notificacao", None)
        creative_data, violations = self.lexicon_guard.sanitize_creative(lexical_data)
        if protected_card is not None:
            creative_data["texto_card_notificacao"] = protected_card
        if violations:
            resumo = ", ".join(
                f"{item['campo']}={item['expressao']!r}" for item in violations[:3]
            )
            print(f"⚠️ Violações lexicais remanescentes: {resumo}")
        return creative_data

    def _sanitize_headline(
        self, creative_data: dict, campaign_ctx: dict, config: dict
    ) -> dict:
        return self.headline_rotator.apply_headline_diversity(
            creative_data, campaign_ctx, config
        )

    def _sanitize_headline_semantics(
        self, creative_data: dict, campaign_ctx: dict, config: dict | None = None
    ) -> dict:
        headline = (creative_data.get("gancho_atencao_inicial") or "").strip()
        contract = (config or {}).get("_campaign_contract") or {}
        phrase = (campaign_ctx.get("frase_golpista") or "").casefold()

        if contract.get("mecanismo") == "transferencia_pix_autorizada":
            canonical_type_id = contract.get("canonical_type_id")
            corrected_headline = re.sub(
                r"\bdifícil\s+recuperar\b",
                "difícil de recuperar",
                headline,
                flags=re.IGNORECASE,
            )
            if corrected_headline != headline:
                creative_data["gancho_atencao_inicial"] = corrected_headline
                creative_data["headline_escolhida"] = corrected_headline
                headline = corrected_headline
            uppercase_headline = headline.upper()
            if uppercase_headline != headline:
                creative_data["gancho_atencao_inicial"] = uppercase_headline
                creative_data["headline_escolhida"] = uppercase_headline
                headline = uppercase_headline
            normalized = re.sub(r"\s+", " ", headline.casefold()).strip()
            if re.search(r"\bperdeu o valor transferido\b", normalized):
                headline = "PIX ENVIADO AO GOLPISTA PODE SER DIFÍCIL DE RECUPERAR"
                creative_data["gancho_atencao_inicial"] = headline
                creative_data["headline_escolhida"] = headline
                normalized = headline.casefold()
            if "amigo" in phrase:
                safe = "PIX PEDIDO POR AMIGO NO WHATSAPP PODE SER GOLPE"
            elif any(term in phrase for term in ("mãe", "mae", "filho", "filha", "neto", "parente")):
                safe = "PIX PEDIDO POR FAMILIAR NO WHATSAPP PODE SER GOLPE"
            else:
                safe = "PEDIDO DE PIX NO WHATSAPP PODE SER GOLPE"
            force_specialized_headline = False
            if canonical_type_id == "qr_code_pix":
                safe = "QR CODE FALSO PODE DESVIAR SEU PAGAMENTO"
                valid_patterns = ("qr code",)
                force_specialized_headline = True
            elif canonical_type_id == "boleto_falso":
                safe = "BOLETO FALSO PODE DESVIAR SEU PAGAMENTO"
                valid_patterns = ("boleto", "qr code")
                force_specialized_headline = True
            elif canonical_type_id == "falsa_cobranca_empresarial":
                safe = "COBRANÇA FALSA PODE DESVIAR SEU PAGAMENTO"
                valid_patterns = ("cobrança", "cobranca")
                force_specialized_headline = True
            else:
                valid_patterns = (
                    "pix pedido por",
                    "pix enviado ao golpista",
                    "valor transferido",
                    "difícil de recuperar",
                )
            if canonical_type_id == "voz_clonada":
                if (config or {}).get("publico_slug") == "pais":
                    safe = "VOZ CLONADA PODE PEDIR PIX EM NOME DE SEU FILHO!"
                else:
                    safe = "VOZ CLONADA PODE PEDIR PIX EM NOME DE UM FAMILIAR!"
            if force_specialized_headline and headline != safe:
                creative_data["gancho_atencao_inicial"] = safe
                creative_data["headline_escolhida"] = safe
                print(f"📌 Headline financeira ajustada para: {safe}")
                return creative_data
            invalid_patterns = (
                r"\bpix que você (receber|fizer|enviar)\b",
                r"\bpix\b.*\bpode fazer você perder\b",
                r"\bpix\b.*\b(roubar|roubou|esvaziar|esvaziou)\b",
            )
            structurally_valid = any(pattern in normalized for pattern in valid_patterns)
            structurally_invalid = any(
                re.search(pattern, normalized, flags=re.IGNORECASE)
                for pattern in invalid_patterns
            )
            if structurally_invalid or not structurally_valid:
                creative_data["gancho_atencao_inicial"] = safe
                creative_data["headline_escolhida"] = safe
                print(f"📌 Headline de PIX ajustada para: {safe}")
                return creative_data

        if not is_ambiguous_pix_headline(headline):
            return creative_data

        if "amigo" in phrase:
            safe = "PIX PEDIDO POR AMIGO NO WHATSAPP PODE SER GOLPE"
        elif any(term in phrase for term in ("mãe", "mae", "filho", "neto", "parente")):
            safe = "PIX PEDIDO POR FAMILIAR NO WHATSAPP PODE SER GOLPE"
        elif any(term in phrase for term in ("banco", "conta", "bloqueada", "bloqueio")):
            safe = "FALSO ALERTA DE BANCO PODE DESVIAR SEU PIX"
        else:
            safe = "UM GOLPISTA PODE DESVIAR O PIX PEDIDO NO WHATSAPP"

        creative_data["gancho_atencao_inicial"] = safe
        creative_data["headline_escolhida"] = safe
        print(f"📌 Headline ambígua substituída por: {safe}")
        return creative_data

    def _align_card_message(
        self, creative_data: dict, config: dict, campaign_ctx: dict, golpe_obj: dict
    ) -> dict:
        """Card golpista = frase da variante selecionada (nexo com roteiro e cena)."""
        explicit_card = (config.get("_card_message_override") or "").strip()
        if explicit_card:
            if creative_data.get("texto_card_notificacao", "").strip() != explicit_card:
                creative_data["texto_card_notificacao"] = explicit_card
                print("📌 Card golpista preservado conforme edição explícita do admin.")
            return creative_data
        if config.get("_preserve_card_message"):
            return creative_data

        frase_ref = (campaign_ctx.get("frase_golpista") or golpe_obj.get("frase_golpista", "")).strip()
        if not frase_ref:
            return creative_data
        card = (creative_data.get("texto_card_notificacao") or "").strip()
        if card.lower() != frase_ref.lower():
            creative_data["texto_card_notificacao"] = frase_ref
            if card:
                print("📌 Card golpista sincronizado com variante do golpe (nexo da campanha).")
        return creative_data

    def _enforce_campaign_nexo(
        self, creative_data: dict, campaign_ctx: dict, config: dict
    ) -> dict:
        """Valida nexo roteiro ↔ card; substitui manchete incoerente."""
        frase = (campaign_ctx.get("frase_golpista") or "").strip()
        roteiro = (creative_data.get("desenvolvimento_copy") or "").strip()
        headline = (creative_data.get("gancho_atencao_inicial") or "").strip()
        if not frase or not roteiro:
            return creative_data

        score = nexo_score(roteiro, frase, headline)
        if is_coherent(roteiro, frase, headline):
            return creative_data

        ganchos = [g for g in (campaign_ctx.get("ganchos") or []) if g]
        if ganchos:
            alt, _ = pick_coherent_gancho(ganchos, frase)
            if alt:
                creative_data["gancho_atencao_inicial"] = alt.upper()
                creative_data["headline_escolhida"] = alt
                print(
                    f"[!] Nexo fraco ({score:.0%}) — manchete alinhada ao card: {alt[:70]}..."
                )
        config["_nexo_retry"] = True
        return creative_data

    def _inject_phone_message_in_scene(
        self, creative_data: dict, campaign_ctx: dict, golpe_obj: dict
    ) -> dict:
        """Instrui o gerador a mostrar WhatsApp sem delegar texto legível à imagem."""
        msg = (creative_data.get("texto_card_notificacao") or "").strip()
        if not msg:
            msg = (campaign_ctx.get("frase_golpista") or golpe_obj.get("frase_golpista", "")).strip()
        if not msg:
            return creative_data
        clause = (
            "STRICT DEVICE COUNT: show exactly ONE physical smartphone in the entire image, "
            "the ordinary-sized phone held naturally by the person. No other phone-shaped "
            "object is allowed anywhere. Keep this single smartphone and its screen fully "
            "inside the frame, never cropped by any edge, with visible margin around it and "
            "entirely within the upper 60 percent of the image; its bottom edge must stay above "
            "all lower-third graphics and cards. Its display must remain small in the composition and use "
            "a softly defocused WhatsApp-style interface with no readable words, letters, "
            "logos, or UI labels. Do not create an enlarged or oversized phone mockup, "
            "second smartphone, duplicated device, floating screen, interface close-up, "
            "picture-in-picture, callout, notification bubble, or device behind the cards. "
            "The compositor will add the suspicious message after image generation."
        )
        creative_data["phone_screen_clause"] = clause
        cena = creative_data.get("direcao_arte_emocional", "")
        if "softly defocused interface" not in cena.lower():
            creative_data["direcao_arte_emocional"] = f"{cena.rstrip()}. {clause}"
        return creative_data

    def _build_ambiente(self, publico_slug: str) -> str:
        return self.visual_variety.pick_ambiente(publico_slug)

    def _build_publico_scene(self, publico_slug: str, golpe_id: str, genero: str = "") -> str | None:
        """Cena visual alinhada ao ICP; sobrescreve direção genérica do golpe quando necessário.
        `genero` ('feminino'/'masculino') força a coerência com o tratamento do golpe (Mãe/Pai)."""
        wa = (
            "a fully visible smartphone held naturally within the frame, with a softly "
            "blurred WhatsApp-style interface and no readable screen text, worried focused "
            "expression, documentary photorealistic, "
        )
        if publico_slug == "empresarios":
            por_golpe = {
                "pix_fantasma": (
                    "Documentary photorealistic photo of a Brazilian shop owner or entrepreneur (35-55, "
                    "polo shirt or store apron) behind a neighborhood store counter with products and cash register, "
                    f"holding smartphone showing {wa} urgent fake bank PIX scam message, active retail workspace, "
                ),
                "falsa_central": (
                    "Documentary photorealistic photo of a Brazilian small business owner at a commercial desk "
                    f"with notebook and receipts, reading {wa} fake bank security message on WhatsApp Business, "
                ),
                "clonagem_whatsapp": (
                    "Documentary photorealistic photo of a Brazilian entrepreneur in a shop back office "
                    f"looking alarmed at smartphone showing {wa} WhatsApp SMS verification code scam, "
                ),
                "falso_parente": (
                    "Documentary photorealistic photo of a Brazilian merchant at their store counter "
                    f"checking {wa} message from fake relative asking urgent PIX, customers area blurred behind, "
                ),
                "phishing": (
                    "Documentary photorealistic photo of a Brazilian business owner hesitating before a suspicious link "
                    f"inside {wa} fake prize message, sitting at commercial desk with computer monitor off to side, "
                ),
            }
            padrao = (
                "Documentary photorealistic photo of a Brazilian entrepreneur or shopkeeper (35-55) "
                "at a commercial workspace — store counter, delivery desk, or small office — "
                f"holding smartphone with {wa} WhatsApp Business conversation, professional casual attire, "
            )
            return por_golpe.get(golpe_id, padrao)

        if publico_slug == "escolas":
            por_golpe = {
                "phishing": (
                    "Documentary photorealistic photo of a Brazilian school director or teacher (40-55) "
                    "in a school administrative office reviewing "
                    f"{wa} suspicious phishing link in PRIVATE WhatsApp message (1:1 chat), diplomas on wall, "
                ),
                "clonagem_whatsapp": (
                    "Documentary photorealistic photo of a Brazilian school coordinator at office desk "
                    f"with alarmed expression reading {wa} fake WhatsApp verification code in private chat, "
                ),
                "grooming": (
                    "Documentary photorealistic photo of a Brazilian school director or pedagogical "
                    "coordinator (40-55) in school administrative office preparing parent safety communication, "
                    f"smartphone on desk showing example of suspicious PRIVATE 1:1 WhatsApp grooming message "
                    "(not a group chat), school diplomas on wall, professional educational setting, "
                ),
            }
            padrao = (
                "Documentary photorealistic photo of a Brazilian school principal or teacher (40-55) "
                "in an administrative office "
                f"holding smartphone with {wa} suspicious WhatsApp message, educational setting, "
            )
            return por_golpe.get(golpe_id, padrao)

        if publico_slug == "idosos":
            por_golpe = {
                "falso_parente": "message pretending to be a relative",
                "pix_fantasma": "urgent PIX request or fake payment message",
                "falsa_central": "fake bank security message requesting password or code",
                "phishing": "suspicious link asking for registration or personal data",
                "clonagem_whatsapp": "fake WhatsApp verification code request",
                "link_malicioso": "malicious link or fake delivery notice",
                "falso_emprego": "fake job offer requesting a fee or documents",
                "falso_investimento": (
                    "fake investment or cryptocurrency offer promising unrealistic returns"
                ),
            }
            foco = por_golpe.get(golpe_id, "suspicious WhatsApp scam message")
            cena_mulher = (
                "Documentary photorealistic photo of a Brazilian senior woman (65-82) with reading glasses "
                f"on sofa checking {wa}{foco}, "
            )
            cena_homem = (
                "Documentary photorealistic photo of a Brazilian senior man (65-82) on a living room "
                f"armchair reading {wa}{foco}, "
            )
            if genero == "feminino":
                return cena_mulher
            if genero == "masculino":
                return cena_homem
            return random.choice([
                cena_homem,
                cena_mulher,
                (
                    "Documentary photorealistic photo of elderly Brazilian couple at a simple dining table, "
                    f"one showing the other {wa} suspicious WhatsApp conversation, "
                ),
            ])

        if publico_slug == "pais":
            mae_cena = (
                "Documentary photorealistic photo of a Brazilian mother (35-50) at home "
                f"reading {wa} message from fake son or daughter asking urgent PIX, "
            )
            pai_cena = (
                "Documentary photorealistic photo of a Brazilian father (35-50) in living room "
                f"staring at {wa} fake relative emergency message, "
            )
            if genero == "feminino":
                falso_parente_cena = mae_cena
            elif genero == "masculino":
                falso_parente_cena = pai_cena
            else:
                falso_parente_cena = random.choice([mae_cena, pai_cena])
            por_golpe = {
                "falso_parente": falso_parente_cena,
                "grooming": (
                    "Documentary photorealistic photo of a Brazilian parent checking teenager's smartphone, "
                    f"{wa} suspicious grooming message visible, worried expression, "
                ),
                "pix_fantasma": random.choice([
                    (
                        "Documentary photorealistic photo of a Brazilian parent (38-50) at kitchen counter "
                        f"holding phone with {wa} urgent PIX scam, "
                    ),
                    (
                        "Documentary photorealistic photo of a Brazilian mother (35-48) in home office "
                        f"reacting to {wa} fake payment request, "
                    ),
                ]),
            }
            padrao = random.choice([
                (
                    "Documentary photorealistic photo of a Brazilian parent (35-50) at home "
                    f"holding smartphone with {wa} suspicious family-related scam, "
                ),
                (
                    "Documentary photorealistic photo of a Brazilian father or mother (38-52) "
                    f"in living room reading {wa} WhatsApp scam targeting parents, "
                ),
            ])
            return por_golpe.get(golpe_id, padrao)

        if publico_slug in ("massa", "geral"):
            profissoes = [
                (
                    "Documentary photorealistic photo of a Brazilian nurse (30-45) on break at hospital corridor "
                    f"checking {wa} suspicious message, "
                ),
                (
                    "Documentary photorealistic photo of a Brazilian delivery worker (25-40) on motorcycle "
                    f"stopped safely reading {wa} fake prize scam, "
                ),
                (
                    "Documentary photorealistic photo of a Brazilian office clerk (28-45) at modest desk "
                    f"with {wa} phishing link in WhatsApp chat, "
                ),
                (
                    "Documentary photorealistic photo of a Brazilian taxi driver (40-58) in parked car "
                    f"reading {wa} fake bank security message, "
                ),
                (
                    "Documentary photorealistic photo of a Brazilian woman (35-55) at supermarket checkout "
                    f"glancing at {wa} urgent PIX request on phone, "
                ),
            ]
            return random.choice(profissoes)

        return None

    def _sync_personagem_visual_to_roteiro(self, creative_data: dict) -> dict:
        """Alinha campo Personagem ao protagonista do roteiro (ex.: Dona Helena → Idosa)."""
        roteiro = creative_data.get("desenvolvimento_copy", "") or ""
        roteiro_gender = _gender_from_roteiro(roteiro)
        if not roteiro_gender:
            return creative_data
        field_gender = _gender_from_personagem_field(
            (creative_data.get("genero_personagem_visual") or "").lower()
        )
        if field_gender == roteiro_gender:
            return creative_data
        if roteiro_gender == "feminino":
            m = re.search(r"\bdona\s+(\w+)", roteiro, re.I)
            nome = m.group(1).capitalize() if m else "protagonista"
            creative_data["genero_personagem_visual"] = f"Idosa ({nome}, protagonista do roteiro)"
        else:
            m = re.search(r"\b(?:o\s+)?seu\s+(\w+)", roteiro, re.I)
            nome = m.group(1).capitalize() if m and m.group(1).lower() not in (
                "whatsapp", "celular", "pix", "link", "privado"
            ) else "protagonista"
            creative_data["genero_personagem_visual"] = f"Idoso ({nome}, protagonista do roteiro)"
        return creative_data

    def _apply_protagonist_gender_from_roteiro(self, creative_data: dict, config: dict) -> dict:
        """Fonte única de gênero — roteiro vence; alternância só se roteiro neutro."""
        contract_gender = config.get("_protagonist_gender")
        if contract_gender in ("feminino", "masculino"):
            inferred = infer_protagonist_gender(creative_data)
            if inferred and inferred != contract_gender:
                print(
                    f"⚠️ Gênero do texto diverge do contrato: "
                    f"{inferred} ≠ {contract_gender} — regenerando."
                )
            creative_data["genero_campanha"] = contract_gender
            persona = config.get("_protagonist_persona") or {}
            creative_data["protagonista_genero"] = contract_gender
            if persona.get("nome"):
                creative_data["protagonista_nome"] = persona["nome"]
            if persona.get("idade"):
                creative_data["protagonista_idade"] = persona["idade"]
            return creative_data

        locked = config.get("_genero_locked")
        if locked in ("feminino", "masculino"):
            creative_data["genero_campanha"] = locked
            return creative_data

        inferred = infer_protagonist_gender(creative_data)
        publico_slug = config.get("publico_slug", "geral")
        if inferred:
            prev = creative_data.get("genero_campanha", "")
            if prev and prev != inferred:
                print(
                    f"⚠️ Gênero alinhado ao roteiro: {prev} → {inferred} "
                    f"({describe_protagonist(creative_data)})"
                )
            creative_data["genero_campanha"] = inferred
            creative_data = self._sync_personagem_visual_to_roteiro(creative_data)
            self.visual_variety.record_gender(inferred, publico_slug)
            return creative_data

        genero = self.visual_variety.next_alternating_gender(publico_slug)
        creative_data["genero_campanha"] = genero
        self.visual_variety.record_gender(genero, publico_slug)
        return creative_data

    def _ensure_protagonist_gender_cue(self, creative_data: dict, config: dict) -> dict:
        """Explicita o gênero quando o roteiro usa apenas o nome do protagonista."""
        roteiro = creative_data.get("desenvolvimento_copy")
        gender = config.get("_protagonist_gender")
        persona = config.get("_protagonist_persona") or {}
        name = str(persona.get("nome") or "").strip()
        if (
            not isinstance(roteiro, str)
            or not roteiro.strip()
            or gender not in ("feminino", "masculino")
            or not name
            or re.search(
                rf"\b(?:dona|seu|senhor|senhora)\s+{re.escape(name)}\b",
                roteiro,
                flags=re.IGNORECASE,
            )
            or not re.search(rf"\b{re.escape(name)}\b", roteiro, flags=re.IGNORECASE)
        ):
            return creative_data

        treatment = "Dona" if gender == "feminino" else "Seu"
        updated, count = re.subn(
            rf"\b{re.escape(name)}\b",
            f"{treatment} {name}",
            roteiro,
            count=1,
            flags=re.IGNORECASE,
        )
        if count:
            creative_data["desenvolvimento_copy"] = updated
            print(f"📌 Protagonista explicitado no roteiro: {treatment} {name}.")
        return creative_data

    def _enforce_gender_coherence(self, creative_data: dict) -> dict:
        """Compat — delega para apply; mantido para chamadas legadas."""
        return creative_data

    def _detect_visual_gender(self, creative_data: dict) -> str:
        """Gênero da PESSOA retratada — roteiro, personagem e tratamento (Mãe/Pai/Seu/Dona)."""
        return infer_protagonist_gender(creative_data)

    def _format_guardrails_for_prompt(self, publico_slug: str = "") -> str:
        g = self.context_data.get("GUARDRAILS_PERSONAGENS", {})
        faixas = g.get("faixas_etarias", {})
        alt = g.get("alternancia_genero", {})
        lines = ["GUARDRAILS DE PERSONAGENS (OBRIGATÓRIO):"]
        if publico_slug == "escolas":
            lines.append("- Protagonista: diretor(a), coordenador(a) ou professor(a) (40-55 anos) em ambiente escolar.")
            lines.append("- NÃO use narrativa de pai/mãe em casa nem 'seu filho' como eixo da história.")
        elif publico_slug == "empresarios":
            lines.append("- Protagonista: empresário(a) ou comerciante (35-55 anos) em ambiente comercial.")
            lines.append("- NÃO use cena doméstica de cozinha ou quarto de adolescente.")
        elif publico_slug == "pais":
            for key in ("pais", "filhos"):
                f = faixas.get(key, {})
                if f.get("regra"):
                    lines.append(f"- {f.get('rotulo', key)}: {f['regra']}")
        elif publico_slug == "idosos":
            f = faixas.get("idosos", {})
            if f.get("regra"):
                lines.append(f"- {f.get('rotulo', 'idosos')}: {f['regra']}")
        else:
            for key in ("idosos", "pais", "filhos"):
                f = faixas.get(key, {})
                if f.get("regra"):
                    lines.append(f"- {f.get('rotulo', key)}: {f['regra']}")
        if alt.get("regra") and publico_slug not in ("escolas", "empresarios"):
            lines.append(f"- Alternância de sexo: {alt['regra']}")
            if alt.get("excecao"):
                lines.append(f"  Exceção: {alt['excecao']}")
        dv = self.context_data.get("DIRETRIZES_VISUAIS", {})
        lines.append(
            "- APARÊNCIA VISUAL: brasileiros bem apresentados, roupa casual limpa e cuidada, "
            "ambiente organizado classe média — sem sinais de pobreza extrema e sem luxo."
        )
        if dv.get("estilo_fotografico"):
            lines.append(f"- Estilo foto: {dv['estilo_fotografico']}")
        return "\n".join(lines)

    def _unlock_creative_if_requested(self, config: dict, feedback: str) -> None:
        """Libera travas de gênero/gancho quando o admin pede mudança narrativa explícita."""
        from feedback_router import _has_narrative_intent

        if not feedback or not _has_narrative_intent(feedback.lower()):
            return
        config.pop("_genero_locked", None)
        config.pop("_personagem_locked", None)
        config.pop("_gancho_rotativo", None)
        print("🔓 Travas de gênero/gancho removidas — aplicando sua instrução narrativa.")

    def _resolve_golpe_obj(self, golpe_id: str, fallback: dict | None = None) -> dict:
        obj = next(
            (g for g in self.context_data.get("TIPOS_DE_GOLPE", []) if g.get("id") == golpe_id),
            None,
        )
        return obj or fallback or {}

    def _refresh_campaign_context(self, config: dict, golpe_obj: dict) -> dict:
        """Re-resolve matriz + biblioteca de golpes (respeita narrative_override)."""
        override = config.get("narrative_override") or {}
        if (
            override.get("publico_slug")
            and override["publico_slug"] != config.get("publico_slug")
        ) or (
            override.get("golpe_id")
            and override["golpe_id"] != config.get("golpe_id")
        ):
            config.pop("narrative_override", None)
            print(
                "⚠️ Override incompatível removido: público e tipo devem permanecer "
                "atômicos durante a campanha."
            )
            override = {}
        pub = override.get("publico_slug") or config.get("publico_slug", "geral")
        golpe_id = override.get("golpe_id") or config.get("golpe_id", "")
        golpe_obj = self._resolve_golpe_obj(golpe_id, golpe_obj)
        allowed_variant_ids = self.contract_catalog.variant_ids_for_golpe(golpe_id)

        ctx = self.context_engine.resolve(pub, golpe_id, golpe_obj, self.context_data)
        ctx = self.scam_library.apply_to_context(
            ctx,
            golpe_id,
            pub,
            allowed_variant_ids=allowed_variant_ids,
        )
        if override:
            ctx["narrative_override_active"] = True
            if override.get("publico_slug"):
                ctx["effective_publico_slug"] = override["publico_slug"]
            if override.get("golpe_id"):
                ctx["effective_golpe_id"] = override["golpe_id"]
        config["_campaign_context"] = ctx
        return ctx

    def _apply_narrative_override(self, config: dict, feedback: str, golpe_obj: dict, plan: dict) -> dict | None:
        """Aplica override temporário de ICP/golpe — só com intenção explícita."""
        if plan.get("surgical_copy"):
            config.pop("narrative_override", None)
            print("✏️ Edição cirúrgica de copy — combo do menu mantido (pais+grooming etc.).")
            return None

        override = plan.get("narrative_override") or {}
        if not override.get("publico_slug") and not override.get("golpe_id"):
            config.pop("narrative_override", None)
            if plan.get("narrative"):
                print("📖 Instrução narrativa livre — combo do menu mantido.")
            return None

        requested_publico = override.get("publico_slug")
        requested_golpe = override.get("golpe_id")
        if (
            requested_publico
            and requested_publico != config.get("publico_slug")
        ) or (
            requested_golpe
            and requested_golpe != config.get("golpe_id")
        ):
            config.pop("narrative_override", None)
            print(
                "⚠️ Mudança de público ou tipo de golpe exige uma nova campanha; "
                "override rejeitado para impedir mistura de casting, cena e contrato."
            )
            return None

        config["narrative_override"] = override
        print(
            format_menu_conflict(
                config.get("publico_slug", ""),
                config.get("golpe_id", ""),
                override,
            )
        )
        ctx = self._refresh_campaign_context(config, golpe_obj)
        print(self.context_engine.summary_line(ctx))
        return override

    def _apply_golpe_variant(self, config: dict, golpe_obj: dict) -> dict:
        """Rotaciona variante de golpe (frase_golpista) mantendo golpe_id do menu."""
        golpe_id = config.get("golpe_id", "")
        pub = (config.get("narrative_override") or {}).get("publico_slug") or config.get("publico_slug", "")
        ctx = self._refresh_campaign_context(config, golpe_obj)
        print(
            f"🔄 Nova variante de golpe: {ctx.get('scam_variant_titulo', '')} — "
            f"{(ctx.get('frase_golpista') or '')[:65]}..."
        )
        return ctx

    def _regenerate_headline_only(
        self, creative_data: dict, config: dict, golpe_obj: dict, feedback: str = ""
    ) -> dict:
        """Troca manchete via rotator — mantém roteiro e prepara recomposição de overlay."""
        campaign_ctx = config.get("_campaign_context", {})
        if feedback.strip():
            config["_headline_feedback"] = feedback.strip()
        gancho, idx = self.headline_rotator.pick_gancho(campaign_ctx, config, advance=True)
        if gancho:
            creative_data["gancho_atencao_inicial"] = gancho
            creative_data["headline_escolhida"] = gancho
            ganchos_list = [g for g in (campaign_ctx.get("ganchos") or []) if g]
            pos = idx + 1 if idx >= 0 else 1
            total = len(ganchos_list) or "?"
            print(f"📰 Nova manchete ({pos}/{total}): {gancho[:80]}...")
        creative_data = self.headline_rotator.apply_headline_diversity(
            creative_data, campaign_ctx, config
        )
        return creative_data

    def _accumulate_instrucoes(self, config: dict, feedback: str, key: str = "_instrucoes_acumuladas") -> str:
        feedback = feedback.strip()
        if not feedback:
            return config.get(key, "")
        prev = config.get(key, "")
        merged = f"{prev}\n• {feedback}".strip() if prev else feedback
        config[key] = merged
        return merged

    def _lock_creative_identity(self, config: dict, creative_data: dict) -> None:
        """Preserva gênero/personagem após estória aprovada — evita troca na correção visual."""
        inferred = infer_protagonist_gender(creative_data)
        config["_genero_locked"] = inferred or creative_data.get("genero_campanha", "")
        config["_personagem_locked"] = creative_data.get("genero_personagem_visual", "")

    def _apply_locked_identity(self, creative_data: dict, config: dict) -> dict:
        genero = config.get("_genero_locked")
        if genero in ("feminino", "masculino"):
            creative_data["genero_campanha"] = genero
        personagem = config.get("_personagem_locked")
        if personagem:
            creative_data["genero_personagem_visual"] = personagem
        return creative_data

    def _resolve_genero_campanha(self, creative_data: dict, config: dict) -> str:
        """Deprecated internamente — use _apply_protagonist_gender_from_roteiro."""
        creative_data = self._apply_protagonist_gender_from_roteiro(creative_data, config)
        return creative_data.get("genero_campanha", "neutro")

    def _align_visual_relationship(self, creative_data: dict, campaign_ctx: dict) -> dict:
        """Mantém o vínculo visual igual ao vínculo descrito no card."""
        scene = creative_data.get("direcao_arte_emocional")
        if not isinstance(scene, str):
            return creative_data
        phrase = (campaign_ctx.get("frase_golpista") or "").casefold()
        if "amigo" in phrase:
            replacement = "pretending to be a friend"
        elif any(term in phrase for term in ("mãe", "mae", "filho", "filha", "neto", "parente")):
            replacement = "pretending to be a family member"
        elif any(term in phrase for term in ("banco", "conta", "bloqueada", "bloqueio")):
            replacement = "pretending to be the bank"
        else:
            return creative_data
        updated = re.sub(
            r"pretending to be a (?:fake )?relative",
            replacement,
            scene,
            flags=re.IGNORECASE,
        )
        if updated != scene:
            creative_data["direcao_arte_emocional"] = updated
        return creative_data

    def _align_parent_visual_gender(self, creative_data: dict, config: dict) -> dict:
        """Alinha o responsável visual ao casting e o filho ao roteiro."""
        if config.get("publico_slug") != "pais":
            return creative_data
        scene = creative_data.get("direcao_arte_emocional")
        gender = config.get("_protagonist_gender")
        if not isinstance(scene, str) or gender not in ("feminino", "masculino"):
            return creative_data

        narrative = " ".join(
            str(creative_data.get(field) or "")
            for field in (
                "gancho_atencao_inicial",
                "desenvolvimento_copy",
                "texto_card_notificacao",
            )
        )
        has_female_child = bool(re.search(r"\b(filha|menina)\b", narrative, re.IGNORECASE))
        has_male_child = bool(re.search(r"\b(filho|menino)\b", narrative, re.IGNORECASE))
        child_gender = (
            "feminino"
            if has_female_child and not has_male_child
            else "masculino"
            if has_male_child and not has_female_child
            else None
        )
        replacements = (
            (
                "masculino",
                (
                    (r"\bBrazilian mother\b", "Brazilian father"),
                    (r"\bworried mother\b", "worried father"),
                    (r"\bchecking her teenage\b", "checking his teenage"),
                ),
            ),
            (
                "feminino",
                (
                    (r"\bBrazilian father\b", "Brazilian mother"),
                    (r"\bworried father\b", "worried mother"),
                    (r"\bchecking his teenage\b", "checking her teenage"),
                ),
            ),
        )
        updated = scene
        for target_gender, rules in replacements:
            if gender != target_gender:
                continue
            for pattern, replacement in rules:
                updated = re.sub(pattern, replacement, updated, flags=re.IGNORECASE)
        if child_gender == "masculino":
            child_rules = (
                (r"\bteenage daughter's\b", "teenage son's"),
                (r"\bdaughter \(girl\b", "son (boy"),
            )
        elif child_gender == "feminino":
            child_rules = (
                (r"\bteenage son's\b", "teenage daughter's"),
                (r"\bson \(boy\b", "daughter (girl"),
            )
        else:
            child_rules = ()
        for pattern, replacement in child_rules:
            updated = re.sub(pattern, replacement, updated, flags=re.IGNORECASE)
        if updated != scene:
            creative_data["direcao_arte_emocional"] = updated
        return creative_data

    def _build_art_direction(
        self, golpe_obj: dict, creative_data: dict, config: dict, campaign_ctx: dict | None = None
    ) -> str:
        golpe_id = config.get("golpe_id", "")
        publico_slug = config.get("publico_slug", "")
        genero_visual = creative_data.get("genero_campanha", "")
        if genero_visual not in ("feminino", "masculino"):
            genero_visual = infer_protagonist_gender(creative_data)

        cena_publico = self._build_publico_scene(publico_slug, golpe_id, genero_visual)
        if campaign_ctx and campaign_ctx.get("direcao_arte_emocional"):
            base = campaign_ctx["direcao_arte_emocional"]
        elif cena_publico:
            base = cena_publico
        else:
            base = golpe_obj.get("direcao_arte_emocional", "")
        ambiente = self._build_ambiente(publico_slug)
        return f"{base} {ambiente}"

    def _harmonize_gender_copy(self, creative_data: dict, campaign_ctx: dict | None = None) -> dict:
        """Alinha filho/filha e linda/lindo — apenas em narrativas parentais (ICP pais)."""
        narrativa_parental = True if campaign_ctx is None else campaign_ctx.get("narrativa_parental", True)
        genero = creative_data.get("genero_personagem_visual", "").lower()
        msg = creative_data.get("texto_card_notificacao", "").lower()
        feminino = "menina" in genero or "filha" in genero or "linda" in msg or "princesa" in msg
        masculino = "menino" in genero or ("filho" in genero and "filha" not in genero) or (
            "lindo" in msg and "linda" not in msg
        )

        if narrativa_parental:
            if feminino:
                creative_data["genero_campanha"] = "feminino"
                if not genero:
                    creative_data["genero_personagem_visual"] = "menina adolescente brasileira (10-17 anos)"
            elif masculino:
                creative_data["genero_campanha"] = "masculino"
                creative_data["genero_personagem_visual"] = genero or "menino adolescente brasileiro (10-17 anos)"
            else:
                creative_data["genero_campanha"] = "neutro"

            if feminino or masculino:
                for field in (
                    "gancho_atencao_inicial",
                    "texto_card_solucao",
                    "desenvolvimento_copy",
                    "chamada_para_acao_cta",
                ):
                    if creative_data.get(field):
                        creative_data[field] = self._apply_gender_pt(creative_data[field], feminino=feminino)
        return creative_data

    def _sanitize_mechanism_claims(self, creative_data: dict, config: dict) -> dict:
        """Corrige consequências incompatíveis com o mecanismo do golpe."""
        contract = config.get("_campaign_contract") or {}
        if contract.get("mecanismo") != "transferencia_pix_autorizada":
            return creative_data

        replacements = (
            (r"\broubou a aposentadoria inteira\b", "fez a vítima perder apenas o valor enviado"),
            (r"\broubar sua aposentadoria\b", "fazer você perder apenas o valor enviado"),
            (r"\bperdeu a aposentadoria\b", "perdeu apenas o valor enviado"),
            (r"\bperder a aposentadoria\b", "perder apenas o valor enviado"),
            (r"\ba aposentadoria inteira\b", "o valor enviado"),
            (r"\baposentadoria inteira\b", "valor enviado"),
            (r"\ba aposentadoria sumiu\b", "o valor enviado foi perdido"),
            (r"\baposentadoria sumiu\b", "o valor enviado foi perdido"),
            (r"\ba aposentadoria sumiram\b", "o valor enviado foi perdido"),
            (r"\baposentadoria sumiram\b", "o valor enviado foi perdido"),
            (r"\ba economia de uma vida inteira\b", "o valor enviado"),
            (r"\beconomia de uma vida inteira\b", "valor enviado"),
            (r"\broubar suas economias\b", "fazer você perder apenas o valor enviado"),
            (r"\bperdeu suas economias\b", "perdeu apenas o valor enviado"),
            (r"\bperder suas economias\b", "perder apenas o valor enviado"),
            (r"\broubar sua economia\b", "fazer você perder apenas o valor enviado"),
            (r"\bperdeu sua economia\b", "perdeu apenas o valor enviado"),
            (r"\bperder sua economia\b", "perder apenas o valor enviado"),
            (r"\blevar suas economias\b", "fazer você perder apenas o valor enviado"),
            (r"\blevar sua economia\b", "fazer você perder apenas o valor enviado"),
            (r"\blevar seu dinheiro\b", "fazer você perder apenas o valor enviado"),
            (r"\broubar seu dinheiro\b", "fazer você perder apenas o valor enviado"),
            (r"\bnão volta mais\b", "pode ser difícil de recuperar"),
            (r"\bproteja sua aposentadoria\b", "proteja o valor antes de enviar"),
            (r"\bproteger sua poupança\b", "confirmar o pedido antes de fazer o PIX"),
            (r"\bproteja sua poupança\b", "confirme o pedido antes de fazer o PIX"),
            (r"\bperder sua poupança\b", "perder apenas o valor enviado"),
            (r"\blevar sua poupança\b", "fazer você perder apenas o valor enviado"),
            (r"\broubar sua poupança\b", "fazer você perder apenas o valor enviado"),
            (r"\besvaziou a conta\b", "fez a vítima perder o valor transferido"),
            (r"\besvaziar a conta\b", "fazer a vítima perder o valor transferido"),
            (r"\bconta zerada\b", "perdeu o valor enviado"),
            (r"\broubou todo o saldo\b", "fez a vítima perder o valor transferido"),
            (r"\bperder todo o saldo\b", "perder apenas o valor enviado"),
            (
                r"\bdrena(?:r)? (?:seu|o) capital de giro\b",
                "faz você perder o valor pago",
            ),
            (
                r"\bnão deixe seu faturamento cair em mãos erradas\b",
                "Não envie valores sem confirmar o destinatário",
            ),
            (
                r"\bantes de (?:qualquer )?clique\b",
                "antes de qualquer pagamento",
            ),
        )
        changed = False
        for field in ("gancho_atencao_inicial", "desenvolvimento_copy", "chamada_para_acao_cta"):
            text = creative_data.get(field)
            if not isinstance(text, str):
                continue
            original = text
            for pattern, replacement in replacements:
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            if text != original:
                creative_data[field] = text
                changed = True
        if changed:
            print("📌 Consequência ajustada: PIX autorizado implica perda apenas do valor enviado.")
        return creative_data

    def _merge_regras_visuais(self, creative_data: dict) -> dict:
        base = dict(self.context_data.get("DIRETRIZES_VISUAIS", {}))
        extra = creative_data.get("regras_visuais") or {}
        if extra.get("proibicoes"):
            base["proibicoes"] = list(base.get("proibicoes", [])) + list(extra["proibicoes"])
        for chave in ("estilo_fotografico", "regras_obrigatorias"):
            if extra.get(chave):
                base[chave] = extra[chave]
        creative_data["regras_visuais"] = base
        return creative_data

    def _finalize_creative_data(self, creative_data: dict, config: dict, golpe_obj: dict) -> dict:
        produto = self.context_data.get("PRODUTO_E_POSICIONAMENTO", {})
        campaign_ctx = config.get("_campaign_context", {})
        creative_data = self._apply_locked_identity(creative_data, config)
        creative_data = self._sanitize_mechanism_claims(creative_data, config)
        if not config.get("_protagonist_gender"):
            creative_data = self._harmonize_gender_copy(creative_data, campaign_ctx)
        creative_data = self._apply_protagonist_gender_from_roteiro(creative_data, config)
        creative_data = self._ensure_protagonist_gender_cue(creative_data, config)
        creative_data["tipo_midia_selecionada"] = config["midia"]
        creative_data["canal_veiculacao_selecionado"] = config["canal"]
        creative_data["direcao_arte_emocional"] = self._build_art_direction(
            golpe_obj, creative_data, config, campaign_ctx
        )
        creative_data = self._align_visual_relationship(creative_data, campaign_ctx)
        creative_data = self._align_parent_visual_gender(creative_data, config)
        creative_data = self._align_card_message(creative_data, config, campaign_ctx, golpe_obj)
        creative_data = self._enforce_campaign_nexo(creative_data, campaign_ctx, config)
        creative_data = self._inject_phone_message_in_scene(creative_data, campaign_ctx, golpe_obj)
        creative_data = self.visual_variety.enrich(creative_data, config, self.context_data)

        if config.get("publico_slug") == "empresarios":
            creative_data.setdefault(
                "genero_personagem_visual",
                campaign_ctx.get("persona_visual")
                or "empresário ou comerciante brasileiro, 35-55 anos, ambiente comercial",
            )
            creative_data["regras_visuais"] = {
                "proibicoes": [
                    "NO home kitchen, NO domestic cooking scene, NO housewife at stove, "
                    "NO residential kitchen table with food bowls.",
                ]
            }
        elif config.get("publico_slug") == "escolas":
            creative_data.setdefault(
                "genero_personagem_visual",
                campaign_ctx.get("persona_visual")
                or "diretor ou professora brasileiro em ambiente escolar",
            )
            creative_data["regras_visuais"] = {
                "proibicoes": [
                    "NO home bedroom with teenager on bed, NO parent checking child phone at home, "
                    "NO domestic kitchen scene — MUST be school administrative or educational setting.",
                ]
            }

        creative_data = self._merge_regras_visuais(creative_data)
        creative_data["golpe_nome"] = golpe_obj.get("nome", config["golpe"])
        creative_data["link_conversao"] = produto.get("url_oficial", "https://guardian-ai.app")
        creative_data["texto_botao_conversao"] = self._build_cta_button(
            config,
            creative_data.get("genero_campanha", "neutro"),
            campaign_ctx,
            creative_data,
        )
        creative_data["publico_id"] = config.get("publico_id", "massa")
        creative_data["publico_slug"] = config.get("publico_slug", creative_data["publico_id"])
        creative_data["campaign_combo"] = campaign_ctx.get("combo_key", "")
        preset = resolve_channel_preset(config.get("canal", ""), config.get("midia", ""))
        creative_data["preset_midia"] = preset
        creative_data["channel_metadata"] = dict(config.get("_channel_metadata") or {})
        creative_data["storyboard"] = list(config.get("_storyboard") or [])
        brief = dict(config.get("_creative_brief") or {})
        if creative_data.get("visual_reference"):
            brief["visual_reference"] = dict(creative_data["visual_reference"])
        creative_data["creative_brief"] = brief
        creative_data = self._enforce_product_truth(creative_data)
        creative_data = self._sanitize_headline(creative_data, campaign_ctx, config)
        creative_data = self._sanitize_headline_semantics(
            creative_data, campaign_ctx, config
        )
        return self._sanitize_mechanism_claims(creative_data, config)

    def _generate_creative_data(
        self, config: dict, golpe_obj: dict, instrucoes_extras: str = ""
    ) -> dict | None:
        framework = self.context_data.get("COPYWRITING_FRAMEWORK", {})
        campaign_ctx = config.get("_campaign_context", {})
        ganchos_ref = campaign_ctx.get("ganchos") or golpe_obj.get("ganchos", [golpe_obj.get("gancho_modelo", "")])
        frase_golpista = campaign_ctx.get("frase_golpista") or golpe_obj.get("frase_golpista", "")
        publico_slug = campaign_ctx.get("effective_publico_slug") or config.get("publico_slug", "")
        golpe_id = campaign_ctx.get("effective_golpe_id") or config.get("golpe_id", "")
        produto = self.context_data.get("PRODUTO_E_POSICIONAMENTO", {})
        contract_data = config.get("_campaign_contract") or {}
        consequence_rule = contract_data.get("consequencia", "")
        mechanism = contract_data.get("mecanismo", "")
        forbidden_claims = contract_data.get("termos_proibidos") or ()
        foco_whatsapp = produto.get(
            "foco_exclusivo",
            "Guardian AI protege EXCLUSIVAMENTE o WhatsApp — pessoal e WhatsApp Business.",
        )

        gancho_prioritario = None
        if not instrucoes_extras.strip() and not config.get("narrative_override"):
            ganchos_list = [g for g in (campaign_ctx.get("ganchos") or []) if g]
            if ganchos_list and frase_golpista:
                state = self.headline_rotator._load_state()
                combo = self.headline_rotator._combo_key(config)
                last_idx = int(state.get(combo, -1))
                gancho_prioritario, gancho_idx = pick_coherent_gancho(
                    ganchos_list, frase_golpista, start_idx=last_idx + 1
                )
                if gancho_prioritario and gancho_idx >= 0:
                    state[combo] = gancho_idx
                    self.headline_rotator._save_state(state)
                    config["_gancho_rotativo"] = gancho_prioritario
                    config["_gancho_rotativo_idx"] = gancho_idx
            else:
                gancho_prioritario, gancho_idx = self.headline_rotator.pick_gancho(
                    campaign_ctx, config, advance=True
                )
            if gancho_prioritario and ganchos_list:
                total = len(ganchos_list)
                pos = gancho_idx + 1 if gancho_idx >= 0 else 1
                print(f"🎯 Gancho com nexo ao card ({pos}/{total}): {gancho_prioritario[:70]}...")

        memoria_txt = self.memory.format_for_prompt(
            publico=publico_slug,
            golpe=golpe_id,
        )
        anti_repeat_txt = self.history.format_anti_repeticao(
            publico=publico_slug,
            golpe=golpe_id,
        )
        preset = resolve_channel_preset(config.get("canal", ""), config.get("midia", ""))
        brief = build_creative_brief(
            config,
            campaign_ctx,
            golpe_obj,
            preset,
            self.context_data,
        )
        storyboard = build_storyboard(brief.to_dict(), config, campaign_ctx)
        config["_storyboard"] = storyboard
        brief_data = brief.to_dict()
        brief_data["storyboard"] = storyboard
        config["_creative_brief"] = brief_data
        storyboard_block = format_storyboard_prompt(storyboard)

        bloco_admin = ""
        if instrucoes_extras.strip():
            bloco_admin = (
                "⚠️ INSTRUÇÕES DO ADMINISTRADOR (PRIORIDADE MÁXIMA — SOBRESCREVEM gancho rotativo, "
                "memória e sugestões automáticas se houver conflito):\n"
                f"{instrucoes_extras.strip()}\n\n"
            )

        contexto_injetado = (
            bloco_admin
            + brief.to_prompt_block()
            + (f"\n\n{storyboard_block}" if storyboard_block else "")
            + "\n\n"
            + f"DIRETRIZES DE CAMPANHA SELECIONADAS:\n"
            f"- Público-Alvo: {config['publico']}\n"
            f"- Slug ICP: {publico_slug}\n"
            f"- Ameaça/Golpe Abordado: {config['golpe']}\n"
            f"- Frase real que o golpista enviaria no WhatsApp (base para o card): {frase_golpista}\n"
            f"- O card é uma mensagem RECEBIDA pelo protagonista. O vocativo indica o destinatário: "
            f"'Mãe' exige protagonista mulher; 'Pai' exige protagonista homem. "
            f"Nunca confunda o personagem que recebe a mensagem com o golpista.\n"
            f"- Gênero do destinatário contratado: "
            f"{contract_data.get('recipient_gender') or 'não indicado; use o casting'}\n"
            f"{format_nexo_prompt_block(frase_golpista, campaign_ctx.get('scam_variant_titulo', ''))}"
            f"- Mecanismo e consequência obrigatórios: {mechanism or 'conforme a variante'} — "
            f"{consequence_rule or 'não invente consequências além do pretexto'}\n"
            + (
                f"- NUNCA afirmar nesta campanha: {', '.join(forbidden_claims)}\n"
                if forbidden_claims
                else ""
            )
            + f"- Ganchos de referência (inspire-se, não copie literalmente): {' | '.join(ganchos_ref)}\n"
            + (
                f"- GANCHO PRIORITÁRIO DESTA CAMPANHA (ângulo obrigatório, palavras novas): "
                f"{gancho_prioritario}\n"
                if gancho_prioritario
                else ""
            )
            + f"- Canal de Distribuição: {config['canal']}\n"
            f"- Tipo de Mídia: {config['midia']}\n"
            f"- Preset técnico: {preset['label']}\n"
            f"- Duração alvo da narração: {preset['copy_duration']}\n"
            f"- Tom de voz do roteiro: {preset['copy_tone']}\n"
            f"- Objetivo de Conversão: {config['objetivo']}\n\n"
            f"{self.context_engine.format_for_prompt(campaign_ctx)}\n\n"
            f"{self._format_product_capabilities_for_prompt()}\n\n"
            f"{self._format_guardrails_for_prompt(publico_slug)}\n\n"
            f"CONTRATO DE PROTAGONISTA (NÃO ALTERAR):\n"
            f"- Nome obrigatório: {(config.get('_protagonist_persona') or {}).get('nome', 'definido pelo contrato')}\n"
            f"- Gênero obrigatório: {config.get('_protagonist_gender', 'definido pelo contrato')}\n"
            f"- Idade obrigatória: {(config.get('_protagonist_persona') or {}).get('idade', 'conforme guardrail')}\n"
            f"- O roteiro deve nomear esse protagonista e a headline deve concordar com ele.\n\n"
            f"FOCO DO PRODUTO (OBRIGATÓRIO):\n"
            f"- {foco_whatsapp}\n"
            f"- Toda narrativa deve mencionar WhatsApp explicitamente.\n\n"
            f"REGRAS DE TOM DE VOZ DA MARCA:\n"
            f"- Posicionamento: {produto.get('posicionamento_comercial')}\n"
            f"- Restrições Linguísticas: "
            f"{'; '.join(produto.get('tom_de_voz_obrigatorio', {}).get('regras_linguisticas', []))}\n\n"
            f"CONTEXTO ESTRATÉGICO DE NEGÓCIO:\n"
            f"{self.md_context[:12000] if self.md_context else ''}\n"
        )
        if anti_repeat_txt:
            contexto_injetado += f"\n{anti_repeat_txt}\n"
        if memoria_txt:
            contexto_injetado += f"\nMEMÓRIA — REGRAS APRENDIDAS:\n{memoria_txt}\n"
        if instrucoes_extras.strip():
            print(f"📌 Instrução do admin aplicada ao redator:\n{instrucoes_extras.strip()[:500]}")

        roteiro = framework.get("roteiro_narracao_modelo", {})
        roteiro_txt = "\n".join(f"   - {k}: {v}" for k, v in roteiro.items())
        limite_chars = preset.get("copy_max_chars")
        regra_chars = (
            f" MÁXIMO {limite_chars} caracteres no desenvolvimento_copy (contando espaços)."
            if limite_chars else ""
        )

        system_instruction = (
            "Você é o Maior Copywriter de Resposta Direta do Brasil, especialista em anúncios de alta "
            "conversão para o app Guardian AI — proteção EXCLUSIVA do WhatsApp (pessoal e Business). "
            "Seu objetivo é SENSIBILIZAR a dor do público e levá-lo a baixar o app IMEDIATAMENTE. "
            "Nunca use tom calmo ou institucional. Nunca fale de segurança genérica — sempre WhatsApp.\n\n"
            f"FRAMEWORK OBRIGATÓRIO: {framework.get('estrutura_obrigatoria', 'PAS')}\n"
            + ("PRINCÍPIOS:\n" + "\n".join(f"   - {p}" for p in framework.get("principios", [])) + "\n\n" if framework.get("principios") else "")
            + (f"ESTRUTURA DO ROTEIRO DE NARRAÇÃO:\n{roteiro_txt}\n\n" if roteiro_txt else "")
            + "CAPACIDADE DO PRODUTO (NUNCA VIOLAR):\n"
            "- Guardian AI NÃO bloqueia mensagens, apps nem configurações do celular.\n"
            "- Ele DETECTA ameaças em mensagens diretas (1:1) no chat do WhatsApp e ENVIA ALERTA imediato.\n"
            "- NÃO monitora grupos do WhatsApp — golpes em campanha devem ocorrer no chat do WhatsApp, não em grupos.\n"
            "- Nome da marca: sempre 'Guardian AI' (pronúncia em inglês).\n"
            "- NUNCA inclua URL, domínio ou guardian-ai.app na narração.\n\n"
            + (
                f"REGRA DE CONSEQUÊNCIA DO GOLPE: {consequence_rule}\n"
                f"EXPRESSÕES PROIBIDAS NESTA VARIANTE: {', '.join(forbidden_claims)}\n\n"
                if consequence_rule or forbidden_claims
                else ""
            )
            + "REGRAS OBRIGATÓRIAS DE OUTPUT (JSON estrito):\n"
            "1. gancho_atencao_inicial: MANCHETE visceral em MAIÚSCULAS, máx 10 palavras. "
            "Contraste GRUPO x PRIVADO de forma clara (ex.: 'NÃO É NO GRUPO — É NO PRIVADO DO ALUNO'). "
            "PROIBIDO frases contraditórias como 'não acontece em grupos; acontece no chat do WhatsApp'.\n"
            f"2. desenvolvimento_copy: Roteiro PAS com {preset['copy_duration']}. "
            f"Tom: {preset['copy_tone']}.{regra_chars} "
            f"Mencione Guardian AI como solução de detecção e alerta. "
            f"NÃO inclua URL na narração — o fechamento será adicionado automaticamente.\n"
            "3. chamada_para_acao_cta: Comando curto em MAIÚSCULAS.\n"
            "4. texto_card_notificacao: COPIE LITERALMENTE a frase_golpista do contexto "
            "(ajuste mínimo de informalidade se necessário — sem trocar o pretexto do golpe).\n"
            "5. frase_destaque_golpista: Frase-chave do golpista para destacar no card.\n"
            "6. genero_personagem_visual: DEVE ser coerente com o protagonista NOMEADO no desenvolvimento_copy "
            "(Dona Helena → 'Idosa (Helena...)'; Seu Carlos → 'Idoso (Carlos...)'). "
            "Respeite GUARDRAILS e o CONTEXTO NARRATIVO "
            "(escola=diretor/professor; empresa=comerciante; pais=pai/mãe; idoso=65+).\n"
            "7. texto_card_solucao: IGNORE este campo — será substituído automaticamente por: "
            f"'{card_solucao_text()}'\n"
            "8. publico_alvo_icp: Descrição resumida do público.\n"
            "9. protagonista_nome: copie o nome obrigatório do contrato.\n"
            "10. protagonista_genero: use exatamente 'feminino' ou 'masculino' conforme o contrato.\n"
            "11. protagonista_idade: copie a idade obrigatória do contrato.\n"
            "Se houver INSTRUÇÕES DO ADMINISTRADOR no início do prompt, elas VENCEM sobre "
            "gancho prioritário, ganchos de referência e memória.\n"
            "Retorne JSON estrito."
        )

        config_creative = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.45,
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "gancho_atencao_inicial": {"type": "STRING"},
                    "desenvolvimento_copy": {"type": "STRING"},
                    "chamada_para_acao_cta": {"type": "STRING"},
                    "texto_card_notificacao": {"type": "STRING"},
                    "frase_destaque_golpista": {"type": "STRING"},
                    "genero_personagem_visual": {"type": "STRING"},
                    "protagonista_nome": {"type": "STRING"},
                    "protagonista_genero": {"type": "STRING"},
                    "protagonista_idade": {"type": "INTEGER"},
                    "texto_card_solucao": {"type": "STRING"},
                    "publico_alvo_icp": {"type": "STRING"},
                },
                "required": [
                    "gancho_atencao_inicial", "desenvolvimento_copy", "chamada_para_acao_cta",
                    "texto_card_notificacao", "frase_destaque_golpista", "genero_personagem_visual",
                    "protagonista_nome", "protagonista_genero", "protagonista_idade",
                    "texto_card_solucao", "publico_alvo_icp",
                ],
            },
        )

        for tentativa in range(3):
            try:
                payload = contexto_injetado
                if tentativa > 0:
                    if frase_golpista:
                        payload += (
                            f"\n\n⚠️ RETENTATIVA {tentativa + 1}: o roteiro anterior NÃO descreveu "
                            f"o mesmo golpe da frase «{frase_golpista}». "
                            "Reescreva contando EXATAMENTE este pretexto — card e roteiro devem combinar.\n"
                        )
                    payload += (
                        "\n⚠️ RETENTATIVA: se o roteiro nomeia DONA/Maria/mãe/dela → genero_personagem_visual "
                        "DEVE ser idosa/mulher; se nomeia SEU Carlos/pai/dele → idoso/homem. "
                        "NUNCA misture protagonista feminino no texto com personagem masculino no campo 6.\n"
                    )
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=payload,
                    config=config_creative,
                )
                dados = json.loads(response.text)
                result = self._finalize_creative_data(dados, config, golpe_obj)
                copy = (result.get("desenvolvimento_copy") or "").strip()
                head = (result.get("gancho_atencao_inicial") or "").strip()
                nexo_ok = not frase_golpista or is_coherent_for_campaign(
                    copy,
                    frase_golpista,
                    head,
                    (config.get("_campaign_contract") or {}).get("canonical_type_id", ""),
                )
                genero_ok = is_gender_coherent(result)
                try:
                    contract = self.contract_catalog.build(
                        config,
                        config.get("_campaign_context", {}),
                        protagonista_gender=config.get("_protagonist_gender", ""),
                    )
                    contract_errors = validate_creative_contract(
                        result,
                        contract,
                        expected_gender=config.get("_protagonist_gender", ""),
                        expected_persona=config.get("_protagonist_persona"),
                    )
                except CampaignContractError as exc:
                    contract_errors = [str(exc)]
                _, lexical_violations = self.lexicon_guard.sanitize_creative(dict(result))
                lexical_ok = not lexical_violations
                contract_ok = not contract_errors
                if nexo_ok and genero_ok and lexical_ok and contract_ok:
                    expected_gender = config.get("_protagonist_gender", "")
                    if expected_gender in ("feminino", "masculino"):
                        self.visual_variety.record_gender(
                            expected_gender, config.get("publico_slug", "geral")
                        )
                    return result
                if not lexical_ok and tentativa < 2:
                    print(
                        "[!] Copy fora do léxico canônico "
                        f"({lexical_violations[0]['expressao']!r}) — regerando copy..."
                    )
                    continue
                if not genero_ok and tentativa < 2:
                    print(
                        "[!] Roteiro e gênero visual conflitantes "
                        f"({describe_protagonist(result)} vs gênero {result.get('genero_campanha')}) "
                        "— regerando copy..."
                    )
                    continue
                if not contract_ok and tentativa < 2:
                    print(
                        "[!] Contrato da campanha violado — regerando:\n"
                        + "\n".join(f"   • {error}" for error in contract_errors[:5])
                    )
                    continue
                if not contract_ok:
                    print(
                        "❌ Campanha bloqueada: contrato canônico não atendido.\n"
                        + "\n".join(f"   • {error}" for error in contract_errors[:8])
                    )
                    return None
                if not nexo_ok and tentativa < 2:
                    print(
                        f"[!] Nexo roteiro/card insuficiente ({nexo_score(copy, frase_golpista, head):.0%}) "
                        f"— regerando copy..."
                    )
                    continue
                print(
                    f"❌ Campanha bloqueada: nexo roteiro/card insuficiente "
                    f"({nexo_score(copy, frase_golpista, head):.0%})."
                )
                return None
            except Exception as e:
                if "429" in str(e):
                    time.sleep(15)
                else:
                    print(f"❌ Erro no Agente Criativo: {e}")
                    return None
        return None

    def _resolve_primary_asset(self, assets: dict) -> str:
        video = assets.get("commercial_video_file", "")
        if video and video not in ("N/A", "FALHOU", "Não solicitado", "Não solicitada"):
            if os.path.isfile(video):
                return video
        imagem = assets.get("static_image_file", "")
        if imagem and imagem not in ("N/A", "Não solicitada", "Não solicitado"):
            if os.path.isfile(imagem):
                return imagem
        return ""

    def _resolve_publish_asset(self, assets: dict, config: dict) -> str:
        """Feed estático: publica JPEG (IMAGE) em vez de MP4 (REELS) — evita falhas na Meta."""
        if not is_video_media(config.get("midia", "")):
            imagem = assets.get("static_image_file", "")
            if imagem and imagem not in ("N/A", "Não solicitada", "Não solicitado"):
                if os.path.isfile(imagem):
                    return imagem
        return self._resolve_primary_asset(assets)

    def _catalog_update(
        self,
        campaign_id: str,
        status: str,
        config: dict,
        creative_data: dict | None = None,
        assets: dict | None = None,
        *,
        revision: int = 0,
        platform: str = "",
        returned_id: str = "",
        error_message: str = "",
        actor: str = "orchestrator",
    ) -> dict:
        creative_data = creative_data or {}
        creative_data.setdefault("campaign_id", campaign_id)
        if creative_data.get("gancho_atencao_inicial"):
            config["_caption"] = self._montar_caption_instagram(creative_data)
        config["_revision"] = revision
        record = self.catalog.update(
            campaign_id,
            status,
            config,
            creative_data,
            assets or {},
            revision=revision,
            platform=platform,
            returned_id=returned_id,
            error_message=error_message,
            actor=actor,
        )
        if self.supabase_bridge is not None:
            try:
                self.supabase_bridge.sync_campaign(record)
            except SupabaseBridgeError as exc:
                print(f"⚠️ Falha ao sincronizar campanha no Supabase: {exc}")
        return record

    def _audit_assets_before_approval(
        self, creative_data: dict, config: dict, assets_resultado: dict
    ):
        audit = audit_creative_assets(
            creative_data,
            config,
            assets_resultado,
            history=self.history,
            visual_auditor=self.visual_quality_auditor,
        )
        print(f"\n{format_audit_result(audit)}")
        if audit.ok:
            return audit

        publico = config.get("publico_slug", "")
        golpe = config.get("golpe_id", "")
        basename = assets_resultado.get("basename", "")
        motivos = ", ".join(issue.code for issue in audit.blocking)
        self.memory.registrar_rejeitado(
            publico,
            golpe,
            basename,
            f"qa_automatica:{motivos}"[:240],
        )
        print("❌ Criativo bloqueado pela QA automática; não será aprovado/publicado.")
        if self.telegram:
            self.telegram.notificar_sync(
                "⚠️ Criativo bloqueado pela QA automática antes da aprovação: "
                f"{motivos}. Gere uma revisão antes de publicar."
            )
        return audit

    def _montar_caption_instagram(self, creative_data: dict) -> str:
        headline = creative_data.get("gancho_atencao_inicial", "")
        copy = creative_data.get("desenvolvimento_copy", "")
        cta = creative_data.get("chamada_para_acao_cta", "Baixe grátis")
        url = creative_data.get("link_conversao", "https://guardian-ai.app")
        hashtags = "#guardianai #segurancadigital #golpewhatsapp #whatsapp #pix #golpe"
        return f"{headline}\n\n{copy[:800]}\n\n{cta} — {url}\n\n{hashtags}"

    def _print_creative_summary(self, creative_data: dict) -> None:
        print("\n📝 CAMPANHA ESTRUTURADA PELOS AGENTES:")
        print(f"🔥 HEADLINE: {creative_data['gancho_atencao_inicial']}")
        print(f"📖 ROTEIRO: {creative_data['desenvolvimento_copy'][:200]}...")
        print(f"👤 Gênero: {creative_data.get('genero_campanha', 'neutro')}")
        print(f"🎭 Protagonista (roteiro): {describe_protagonist(creative_data)}")
        if not is_gender_coherent(creative_data):
            print("❌ INCOERÊNCIA: roteiro e gênero visual não combinam — não deveria chegar aqui.")
        if creative_data.get("campaign_combo"):
            print(f"🎯 Combo contexto: {creative_data['campaign_combo']}")
        print(f"🔘 CTA: {creative_data['texto_botao_conversao']}")
        print(f"🎬 Cena: {creative_data['direcao_arte_emocional'][:120]}...\n")

    def _story_approval_enabled(self) -> bool:
        return os.getenv("STORY_APPROVAL", "true").lower() in ("1", "true", "yes")

    def _story_job_id(self, config: dict, revisao: int, story_attempt: int) -> str:
        slug = config.get("publico_slug", "geral")
        golpe = config.get("golpe_id", "golpe")
        return f"story_{slug}_{golpe}_r{revisao}_s{story_attempt}"

    def _ler_melhoria_terminal(self) -> str:
        """Leitura de melhoria no terminal — equivalente ao MELHORAR do Telegram."""
        print("\n✏️ MELHORAR ESTÓRIA")
        print("Descreva o que mudar. Seja específico. Exemplos:")
        print("  • Estória: focar no golpe PIX com pai de família (não mãe)")
        print("  • Headline mais urgente / roteiro mais curto e com sentido real")
        print("  • Trocar protagonista para diretor escolar (ambiente escola)")
        print("  • Imagem: pessoa bem vestida, casa clara (só visual — diga 'imagem')")
        print("Digite sua melhoria (linha vazia + Enter para enviar):\n")
        lines: list[str] = []
        while True:
            line = input("> " if not lines else "  ")
            if not line.strip() and lines:
                break
            if line.strip():
                lines.append(line.strip())
        return " ".join(lines).strip()

    def _aprovar_estoria_terminal(self, creative_data: dict, config: dict, job_id: str) -> dict:
        print("\n" + "=" * 70)
        print("📋 APROVAÇÃO DA ESTÓRIA (antes de gerar vídeo/áudio — economiza APIs)")
        print("=" * 70)
        print(f"Combo: {creative_data.get('campaign_combo', '—')}")
        print(f"Headline: {creative_data.get('gancho_atencao_inicial', '')}")
        print(f"\nRoteiro:\n{creative_data.get('desenvolvimento_copy', '')}")
        print(f"\nCard golpista: {creative_data.get('texto_card_notificacao', '')}")
        print(f"Personagem: {creative_data.get('genero_personagem_visual', '')}")
        print(f"CTA botão: {creative_data.get('texto_botao_conversao', '')}")
        print(f"\nCena: {creative_data.get('direcao_arte_emocional', '')[:300]}...")
        print(f"\nJob: {job_id}")
        print("\n[1] ✅ Aprovar estória e produzir mídia")
        print("[2] ✏️ Melhorar estória (reescrever copy — sem custo de APIs)")
        print("[3] ❌ Rejeitar campanha")
        op = input("Escolha (1/2/3): ").strip()
        if op == "1":
            return {"action": "approve"}
        if op == "3":
            return {"action": "reject", "motivo": "estoria_rejeitada_terminal"}
        if op == "2":
            feedback = self._ler_melhoria_terminal()
            if feedback:
                return {"action": "improve", "prompt": feedback}
            print("⚠️ Melhoria vazia — tente novamente ou escolha [1] ou [3].")
            return {"action": "improve", "prompt": ""}  # loop continua pedindo
        print("⚠️ Opção inválida. Use 1, 2 ou 3.")
        return {"action": "retry"}

    def _aprovar_asset_terminal(
        self, creative_data: dict, config: dict, job_id: str, asset_path: str
    ) -> dict:
        """Aprovação final do criativo (vídeo/imagem pronto) direto no terminal (Desktop) —
        equivalente à aprovação do Telegram, executada antes do Gestor de Tráfego."""
        print("\n" + "=" * 70)
        print("📋 APROVAÇÃO FINAL DO CRIATIVO (vídeo/imagem pronto — antes do Gestor de Tráfego)")
        print("=" * 70)
        print(f"Canal: {config.get('canal', '—')}")
        print(f"Mídia: {config.get('midia', '—')}")
        print(f"Preset: {(creative_data.get('preset_midia') or {}).get('preset_id', '—')}")
        print(f"Headline: {creative_data.get('gancho_atencao_inicial', '')}")
        print(f"\nRoteiro: {creative_data.get('desenvolvimento_copy', '')[:400]}")
        print(f"\nLegenda:\n{self._montar_caption_instagram(creative_data)[:800]}")
        print(f"\nCTA botão: {creative_data.get('texto_botao_conversao', creative_data.get('chamada_para_acao_cta', ''))}")
        print(
            f"\nStoryboard: "
            f"{format_storyboard_compact(creative_data.get('storyboard') or [])}"
        )
        print(f"\n🎬 Arquivo para revisar: {asset_path}")
        print(f"Campaign ID: {config.get('_campaign_id', '—')} | Versão: {config.get('_revision', 0)}")
        print(f"Job: {job_id}")
        print("\n[1] ✅ Aprovar e seguir para publicação")
        print("[2] ✏️ Melhorar (reescrever copy — regenera vídeo/áudio)")
        print("[3] ❌ Rejeitar campanha")
        op = input("Escolha (1/2/3): ").strip()
        if op == "1":
            return {"action": "approve"}
        if op == "3":
            return {"action": "reject", "motivo": "asset_rejeitado_terminal"}
        if op == "2":
            feedback = self._ler_melhoria_terminal()
            if feedback:
                return {"action": "improve", "prompt": feedback}
            print("⚠️ Melhoria vazia — tente novamente ou escolha [1] ou [3].")
            return {"action": "retry"}
        print("⚠️ Opção inválida. Use 1, 2 ou 3.")
        return {"action": "retry"}

    def _solicitar_aprovacao_estoria(
        self, config: dict, creative_data: dict, revisao: int, story_attempt: int
    ) -> dict:
        job_id = self._story_job_id(config, revisao, story_attempt)
        if config.get("aprovacao_telegram") and self.telegram:
            if hasattr(self.telegram, "aprovar_estoria_sincronamente"):
                return self.telegram.aprovar_estoria_sincronamente(
                    creative_data, job_id, config, timeout_segundos=self.telegram_timeout
                )
        return self._aprovar_estoria_terminal(creative_data, config, job_id)

    def _gerar_e_aprovar_estoria(
        self,
        config: dict,
        golpe_obj: dict,
        instrucoes_base: str,
        revisao: int,
    ) -> tuple[bool, dict | None]:
        instrucoes = instrucoes_base
        story_attempt = 0

        while story_attempt <= self.max_revisoes:
            print("\n🧠 [Agente Redator Sênior] Escrevendo copies de alta conversão...")
            creative_data = self._generate_creative_data(config, golpe_obj, instrucoes)
            if not creative_data:
                return False, None
            self._print_creative_summary(creative_data)

            if not self._story_approval_enabled():
                self._lock_creative_identity(config, creative_data)
                return True, creative_data

            acao = self._solicitar_aprovacao_estoria(config, creative_data, revisao, story_attempt)
            print(f"📋 Decisão estória: {acao.get('action')}")

            if acao["action"] == "retry":
                continue

            if acao["action"] == "approve":
                self._lock_creative_identity(config, creative_data)
                if self.telegram:
                    self.telegram.notificar_sync("✅ *Estória aprovada* — iniciando produção de vídeo/áudio...")
                else:
                    print("✅ Estória aprovada — iniciando produção de vídeo/áudio...")
                return True, creative_data

            if acao["action"] in ("reject", "timeout"):
                self.memory.registrar_rejeitado(
                    config.get("publico_slug", ""),
                    config.get("golpe_id", ""),
                    self._story_job_id(config, revisao, story_attempt),
                    acao.get("motivo", acao["action"]),
                )
                return False, None

            if acao["action"] == "improve":
                feedback = acao.get("prompt", "").strip()
                if not feedback:
                    print("⚠️ Informe a melhoria (opção 2) ou escolha aprovar/rejeitar.")
                    continue
                story_attempt += 1
                if story_attempt > self.max_revisoes:
                    print(f"❌ Limite de {self.max_revisoes} revisões da estória atingido.")
                    return False, None
                instrucoes = self._accumulate_instrucoes(config, feedback, "_instrucoes_estoria")
                self._unlock_creative_if_requested(config, feedback)
                card_edit = extract_card_message_edit(feedback)
                if card_edit.get("exact"):
                    config["_card_message_override"] = card_edit["exact"]
                    config.pop("_preserve_card_message", None)
                elif card_edit.get("prefix"):
                    config["_preserve_card_message"] = True
                plan = classify_improvement(feedback)
                self._apply_narrative_override(config, feedback, golpe_obj, plan)
                if card_edit.get("exact"):
                    campaign_ctx = config.get("_campaign_context")
                    if isinstance(campaign_ctx, dict):
                        campaign_ctx["frase_golpista"] = card_edit["exact"]
                tagged = f"{correction_tag(plan)} {feedback}"
                self.memory.registrar_correcao(
                    config.get("publico_slug", ""),
                    config.get("golpe_id", ""),
                    tagged,
                    self._story_job_id(config, revisao, story_attempt),
                    story_attempt,
                    categoria=plan.get("primary_category", "narrativa"),
                )
                regras_aprendidas = self.memory.aprender_regra_de_feedback(feedback)
                if regras_aprendidas:
                    print(
                        "🧠 Regra linguística global aprendida: "
                        + ", ".join(regras_aprendidas)
                    )
                print(f"📝 Melhoria registrada — regerando estória (tentativa {story_attempt}/{self.max_revisoes})...")
                if self.telegram:
                    self.telegram.notificar_sync(
                        "📝 Regerando *estória* com sua melhoria (sem custo de vídeo/áudio)..."
                    )
                continue

        return False, None

    def show_interactive_menu(self) -> dict:
        """Exibe o painel interativo de configuração de campanha para o usuário."""
        print("\n======================================================================")
        print("⚙️ [PAINEL DE CONFIGURAÇÃO DE CAMPANHA - GUARDIAN AI]")
        print("======================================================================")
        
        # 1. SELEÇÃO DO PÚBLICO-ALVO
        print("\n👥 ETAPA 1: Selecione o PÚBLICO-ALVO (ICP):")
        print("[1] Idosos / Aposentados (Proteção de economias)")
        print("[2] Pais (Proteção de filhos menores)")
        print("[3] Empresários / Comerciantes (Contas jurídicas e boletos)")
        print("[4] Dirigentes e Professores de Escolas (Dados e ambiente escolar)")
        opcoes_publico = {
            "1": "Idosos e aposentados vulneráveis a fraudes financeiras e familiares.",
            "2": "Pais preocupados com a segurança, aliciamento (grooming) e integridade dos filhos na internet.",
            "3": "Empresários e donos de comércios expostos a golpes de boletos e clonagem de contas jurídicas.",
            "4": "Dirigentes, diretores e professores focados na segurança de dados escolares e ataques de phishing."
        }
        mapa_publico_id = {"1": "idosos", "2": "pais", "3": "profissionais", "4": "escolas"}
        mapa_publico_slug = {"1": "idosos", "2": "pais", "3": "empresarios", "4": "escolas"}
        while True:
            p_escolhido = input("Digite o número da opção desejada: ").strip()
            if p_escolhido in opcoes_publico:
                break
            print("❌ Opção de público inválida. Escolha 1, 2, 3 ou 4.")
        publico_final = opcoes_publico[p_escolhido]
        publico_id = mapa_publico_id[p_escolhido]
        publico_slug = mapa_publico_slug[p_escolhido]

        # 2. SELEÇÃO DO TIPO DE GOLPE
        print("\n⚠️ ETAPA 2: Selecione o TIPO DE GOLPE a ser abordado:")
        print("[1] Falso Parente / Novo Número (Engenharia Social)")
        print("[2] Golpe do PIX / Fraude Financeira")
        print("[3] Falsa Central Bancária / Falso Atendente")
        print("[4] Grooming / Aliciamento Digital de Menores")
        print("[5] Links de Phishing / Páginas Clonadas")
        print("[6] Clonagem de WhatsApp (Roubo de código SMS)")
        print("[7] Link Malicioso / Falsa Encomenda / APK falso")
        print("[8] Falso Emprego / Vaga Home Office")
        print("[9] Falso Investimento / Cripto / Grupo VIP")
        opcoes_golpe = {
            "1": "Golpe do Falso Parente / Novo Número no WhatsApp pedindo dinheiro urgente.",
            "2": "Golpe do PIX e transferências bancárias sob indução mecânica ou pânico.",
            "3": "Golpe da Falsa Central Bancária simulando atendimento institucional de segurança.",
            "4": "Grooming / Aliciamento digital de menores e exposição de crianças em redes e jogos online.",
            "5": "Links maliciosos de Phishing e páginas clonadas projetadas para roubo de senhas.",
            "6": "Clonagem de WhatsApp via engenharia social e roubo do código SMS de verificação.",
            "7": "Links maliciosos: promoções falsas, encomenda retida, APK falso ou atualização fraudulenta.",
            "8": "Golpe do falso emprego: vagas home office, taxa de admissão e captura de documentos.",
            "9": "Golpe do falso investimento: lucro garantido, cripto e grupos VIP no WhatsApp."
        }
        mapa_golpe_id = {
            "1": "falso_parente", "2": "pix_fantasma", "3": "falsa_central",
            "4": "grooming", "5": "phishing", "6": "clonagem_whatsapp",
            "7": "link_malicioso", "8": "falso_emprego", "9": "falso_investimento",
        }
        opcoes_compativeis = {
            key: label
            for key, label in opcoes_golpe.items()
            if self.scam_library.has_compatible_variant(
                mapa_golpe_id[key],
                publico_slug,
                self.contract_catalog.variant_ids_for_golpe(mapa_golpe_id[key]),
            )
        }
        print(
            "✅ Golpes compatíveis com este público: "
            + ", ".join(f"{key} ({mapa_golpe_id[key]})" for key in opcoes_compativeis)
        )
        while True:
            g_escolhido = input("Digite o número da opção desejada: ").strip()
            if g_escolhido in opcoes_compativeis:
                break
            print(
                "❌ Esse golpe não possui variante compatível com o público selecionado. "
                "Escolha uma das opções listadas."
            )
        golpe_final = opcoes_compativeis[g_escolhido]
        golpe_id = mapa_golpe_id[g_escolhido]

        while True:
            # 3. SELEÇÃO DA MÍDIA
            print("\n🖼️ ETAPA 3: Selecione o TIPO DE MÍDIA visual:")
            print("[1] Imagem Estática Premium (Feed do Instagram / Facebook Ads)")
            print("[2] Vídeo Comercial Animado (Reels / TikTok / YouTube Shorts)")
            m_escolhido = input("Digite o número da opção desejada: ").strip()
            midia_final = (
                "Imagem Estática Square (1080x1080)"
                if m_escolhido == "1"
                else "Vídeo Vertical Animado"
            )

            # 4. SELEÇÃO DO CANAL (VEICULAÇÃO / PRESET DE ÁUDIO)
            print("\n🎙️ ETAPA 4: Selecione o CANAL DE VEICULAÇÃO (Define o comportamento do Áudio):")
            print("[1] Meta Ads (Instagram/Facebook - Áudio pausado e focado em leitura)")
            print("[2] TikTok / YouTube Shorts (Áudio rápido, urgente e com trilha de suspense)")
            c_escolhido = input("Digite o número da opção desejada: ").strip()
            canal_final = (
                "Meta Ads (Instagram/Facebook)"
                if c_escolhido == "1"
                else "TikTok / YouTube Shorts"
            )
            channel_validation = validate_channel_media(canal_final, midia_final)
            if channel_validation.valid:
                break
            print("\n❌ Combinação de canal e mídia inválida:")
            for error in channel_validation.errors:
                print(f"   • {error}")
            print("Escolha novamente a mídia e o canal.")

        # 5. SELEÇÃO DO OBJETIVO CONVERSÃO
        print("\n📈 ETAPA 5: Selecione o OBJETIVO DE CONVERSÃO técnico:")
        print("[1] Instalação Direta do Aplicativo (App Installs)")
        print("[2] Geração de Leads / Cadastro (Formulários de captação)")
        o_escolhido = input("Digite o número da opção desejada: ").strip()
        objetivo_final = "Instalação do Aplicativo (Downloads)" if o_escolhido == "1" else "Geração de Leads Qualificados"

        print("\n📲 ETAPA 6: Fluxo após gerar o criativo:")
        print("[1] Apenas salvar arquivos localmente (sem aprovação, sem Telegram)")
        print("[2] Salvar + Aprovação via Telegram (recomendado)")
        if "tiktok" in canal_final.lower():
            print("[3] Salvar + Telegram + Exportar pacote TikTok após APROVAR")
            print("[4] Aprovar aqui mesmo (terminal) + Exportar pacote TikTok após APROVAR")
        else:
            print("[3] Salvar + Telegram + Postar automaticamente após APROVAR")
            print("[4] Aprovar aqui mesmo (terminal) + Postar automaticamente após APROVAR")
        f_escolhido = input("Digite o número da opção desejada: ").strip()
        fluxo_map = {
            "1": {"aprovacao_telegram": False, "aprovacao_terminal": False, "postar_instagram": False},
            "2": {"aprovacao_telegram": True, "aprovacao_terminal": False, "postar_instagram": False},
            "3": {"aprovacao_telegram": True, "aprovacao_terminal": False, "postar_instagram": True},
            "4": {"aprovacao_telegram": False, "aprovacao_terminal": True, "postar_instagram": True},
        }
        fluxo = fluxo_map.get(f_escolhido, fluxo_map["2"])

        return {
            "publico": publico_final,
            "publico_id": publico_id,
            "publico_slug": publico_slug,
            "golpe": golpe_final,
            "golpe_id": golpe_id,
            "midia": midia_final,
            "canal": canal_final,
            "preset_midia": channel_validation.preset,
            "preset_metadata": channel_validation.metadata,
            "objetivo": objetivo_final,
            "aprovacao_telegram": fluxo["aprovacao_telegram"],
            "aprovacao_terminal": fluxo["aprovacao_terminal"],
            "postar_instagram": fluxo["postar_instagram"],
        }

    def execute_automated_pipeline(self, config: dict | None = None, telegram_override=None):
        if config is None:
            config = self.show_interactive_menu()

        catalog_errors = self.contract_catalog.validate_catalog()
        if catalog_errors:
            print("❌ Catálogo canônico inválido:")
            for error in catalog_errors:
                print(f"   • {error}")
            return
        if config.get("publico_slug") not in VALID_PUBLICO_SLUGS:
            print(
                "❌ Público inválido. A campanha precisa usar um público canônico; "
                "'geral' não é permitido."
            )
            return

        channel_validation = validate_channel_media(
            config.get("canal", ""),
            config.get("midia", ""),
        )
        if not channel_validation.valid:
            print("❌ Configuração rejeitada antes das APIs:")
            for error in channel_validation.errors:
                print(f"   • {error}")
            if telegram_override and hasattr(telegram_override, "_notify_error"):
                telegram_override._notify_error(
                    "Combinação de canal e mídia inválida: "
                    + " ".join(channel_validation.errors)
                )
            return
        config["preset_midia"] = channel_validation.preset
        config["preset_metadata"] = channel_validation.metadata
        config["_channel_metadata"] = channel_validation.metadata
        campaign_id = self.catalog.create(config)
        print(f"🗂️ Campaign ID: {campaign_id}")

        print(f"🚀 [MKT GUARDIAN AI - ENGINE ORQUESTRAÇÃO v{ORCHESTRATOR_VERSION}] Iniciando Esteira...")
        print(f"📁 Diretório de trabalho: {self.BASE_DIR}")
        print(f"🧠 Modelo de copy: {self.model_name}")
        print_build_banner(self.BASE_DIR)
        print("======================================================================")

        golpe_obj = next(
            (g for g in self.context_data.get("TIPOS_DE_GOLPE", []) if g.get("id") == config.get("golpe_id")),
            {},
        )
        campaign_ctx = self.context_engine.resolve(
            config.get("publico_slug", "geral"),
            config.get("golpe_id", ""),
            golpe_obj,
            self.context_data,
        )
        campaign_ctx = self.scam_library.apply_to_context(
            campaign_ctx,
            config.get("golpe_id", ""),
            config.get("publico_slug", ""),
            allowed_variant_ids=self.contract_catalog.variant_ids_for_golpe(
                config.get("golpe_id", "")
            ),
        )
        recipient_gender = infer_recipient_gender(
            campaign_ctx.get("frase_golpista") or ""
        )
        config["_recipient_gender"] = recipient_gender
        config["_protagonist_gender"] = (
            recipient_gender
            or self.visual_variety.next_alternating_gender(config["publico_slug"])
        )
        config["_protagonist_persona"] = self.visual_variety.pick_persona(
            self.context_data,
            config.get("publico_id", config["publico_slug"]),
            config["publico_slug"],
            genero=config["_protagonist_gender"],
        )
        try:
            contract = self.contract_catalog.build(
                config,
                campaign_ctx,
                protagonista_gender=config["_protagonist_gender"],
            )
        except CampaignContractError as exc:
            print(f"❌ Campanha rejeitada pelo contrato canônico: {exc}")
            return
        config["_campaign_contract"] = asdict(contract)
        if campaign_ctx.get("scam_variant_titulo"):
            frase = (campaign_ctx.get("frase_golpista") or "")[:70]
            print(
                f"📚 Variante golpe: {campaign_ctx['scam_variant_titulo']} "
                f"({campaign_ctx.get('scam_variant_id', '')}) — {frase}..."
            )
        config["_campaign_context"] = campaign_ctx
        print(self.context_engine.summary_line(campaign_ctx))
        if self._story_approval_enabled():
            print("📋 Aprovação da estória ATIVA — vídeo/áudio só após você aprovar o roteiro.")
        preset = config["preset_midia"]
        print(f"📐 Preset de produção: {format_preset_summary(preset)}")

        if config.get("aprovacao_telegram"):
            if telegram_override is not None:
                self.telegram = telegram_override
                print("📲 Aprovação via bot Telegram (loop único).")
            else:
                self._init_telegram()
        if config.get("postar_instagram"):
            if "tiktok" in config.get("canal", "").lower():
                print("📦 TikTok configurado para upload manual pelo Ubuntu.")
            else:
                if not self._init_publisher():
                    self._catalog_update(
                        campaign_id,
                        "ERRO_PUBLICACAO",
                        config,
                        error_message="Preflight Meta não aprovado.",
                    )
                    return

        pub_slug = config.get("publico_slug", "")
        golpe_id = config.get("golpe_id", "")
        memoria_resumo = self.memory.format_for_prompt(
            publico=pub_slug,
            golpe=golpe_id,
            limit_correcoes=3,
        )
        if memoria_resumo:
            print(f"🧠 Memória carregada ({len(memoria_resumo.splitlines())} regras aprendidas)")
        hist_recent = self.history.get_recent(pub_slug, golpe_id, limit=5)
        if hist_recent:
            print(
                f"📚 Histórico combo {pub_slug}/{golpe_id}: "
                f"{len(hist_recent)} campanha(s) — anti-repetição ativo"
            )

        instrucoes_melhoria = ""
        assets_resultado = {}
        creative_data = {}
        aprovado = False
        recompose_next = False
        reapply_audio_next = False
        visual_only_next = False
        video_only_next = False
        visual_feedback = ""

        for revisao in range(self.max_revisoes + 1):
            if self._story_approval_enabled():
                self._catalog_update(
                    campaign_id,
                    "AGUARDANDO_APROVACAO_HISTORIA",
                    config,
                    creative_data,
                    assets_resultado,
                    revision=revisao,
                )
            if recompose_next:
                print(f"\n🔧 Recompondo overlay (feedback de layout — revisão {revisao})...")
                creative_data["overlay_card_font_size"] = 20
                assets_resultado = self.media_factory.reapply_overlay_only(creative_data, assets_resultado)
                recompose_next = False
            elif reapply_audio_next:
                print(f"\n🔊 Regerando narração (pronúncia do site — revisão {revisao})...")
                assets_resultado = self.media_factory.reapply_audio_only(creative_data, assets_resultado)
                reapply_audio_next = False
            elif video_only_next:
                print(f"\n🎞️ Regerando somente o vídeo (revisão {revisao})...")
                assets_resultado = self.media_factory.regenerate_video_only(
                    creative_data, assets_resultado, visual_feedback
                )
                video_only_next = False
                visual_feedback = ""
            elif visual_only_next:
                print(f"\n🎨 Regerando só imagem/vídeo (copy e áudio aprovados — revisão {revisao})...")
                creative_data = self._apply_locked_identity(creative_data, config)
                assets_resultado = self.media_factory.regenerate_visual_only(
                    creative_data, assets_resultado, visual_feedback
                )
                visual_only_next = False
                visual_feedback = ""
            else:
                if revisao > 0:
                    print(f"\n🔄 Revisão {revisao}/{self.max_revisoes} — regerando campanha...")
                ok_estoria, creative_data = self._gerar_e_aprovar_estoria(
                    config, golpe_obj, instrucoes_melhoria, revisao
                )
                if not ok_estoria or not creative_data:
                    self._catalog_update(
                        campaign_id,
                        "REJEITADA",
                        config,
                        creative_data,
                        assets_resultado,
                        revision=revisao,
                        error_message="Aprovação da história rejeitada ou sem conteúdo.",
                        actor="human",
                    )
                    return
                assets_resultado = self.media_factory.generate_campaign_assets(creative_data)
                self.visual_variety.print_qa_checklist(creative_data)
                self._catalog_update(
                    campaign_id,
                    "PRODUZIDA",
                    config,
                    creative_data,
                    assets_resultado,
                    revision=revisao,
                )

            audit = self._audit_assets_before_approval(
                creative_data, config, assets_resultado
            )
            if not audit.ok:
                if revisao >= self.max_revisoes:
                    print(f"❌ Limite de {self.max_revisoes} revisões de QA atingido.")
                    self._catalog_update(
                        campaign_id,
                        "REJEITADA",
                        config,
                        creative_data,
                        assets_resultado,
                        revision=revisao,
                        error_message="Limite de revisões de QA atingido.",
                    )
                    return
                stage = audit.recommended_stage or "copy"
                qa_feedback = "; ".join(
                    issue.message for issue in audit.blocking[:3]
                )
                print(f"🔧 QA direciona correção para: {stage}")
                self.memory.registrar_correcao(
                    config.get("publico_slug", ""),
                    config.get("golpe_id", ""),
                    f"qa_{stage}: {qa_feedback}"[:240],
                    assets_resultado.get("basename", ""),
                    revisao,
                    categoria=stage,
                )
                if stage == "layout":
                    recompose_next = True
                    creative_data["overlay_card_font_size"] = 20
                elif stage == "audio":
                    reapply_audio_next = True
                elif stage in ("imagem", "video"):
                    if stage == "video":
                        video_only_next = True
                    else:
                        visual_only_next = True
                    visual_feedback = qa_feedback
                else:
                    instrucoes_melhoria = (
                        "A QA final reprovou o criativo. Corrija somente o problema "
                        f"indicado na etapa {stage}: {qa_feedback}"
                    )
                continue

            usar_telegram_aprovacao = bool(config.get("aprovacao_telegram") and self.telegram)
            # Se o Telegram foi solicitado mas não inicializou (ex.: token ausente), cai para o
            # terminal em vez de pular a aprovação — evita publicar automaticamente sem ninguém revisar.
            usar_terminal_aprovacao = bool(
                config.get("aprovacao_terminal")
                or (config.get("aprovacao_telegram") and not self.telegram)
            )
            if not (usar_telegram_aprovacao or usar_terminal_aprovacao):
                asset_path = self._resolve_primary_asset(assets_resultado)
                if not asset_path:
                    self._catalog_update(
                        campaign_id,
                        "REJEITADA",
                        config,
                        creative_data,
                        assets_resultado,
                        revision=revisao,
                        error_message="Nenhum asset visual gerado.",
                    )
                    print("❌ Nenhum asset visual gerado.")
                    return
                self._catalog_update(
                    campaign_id,
                    "APROVADA",
                    config,
                    creative_data,
                    assets_resultado,
                    revision=revisao,
                    actor="automatic",
                )
                self.history.registrar_campanha(
                    creative_data,
                    config,
                    assets_resultado,
                    status="gerado",
                    revisao=revisao,
                    asset_path=asset_path,
                )
                self.history.registrar_campanha(
                    creative_data,
                    config,
                    assets_resultado,
                    status="aprovado",
                    revisao=revisao,
                    asset_path=asset_path,
                )
                aprovado = True
                break

            self._catalog_update(
                campaign_id,
                "AGUARDANDO_APROVACAO_FINAL",
                config,
                creative_data,
                assets_resultado,
                revision=revisao,
            )

            asset_path = self._resolve_primary_asset(assets_resultado)
            if not asset_path:
                print("❌ Nenhum asset visual gerado para aprovação.")
                self._catalog_update(
                    campaign_id,
                    "REJEITADA",
                    config,
                    creative_data,
                    assets_resultado,
                    revision=revisao,
                    error_message="Nenhum asset visual gerado para aprovação.",
                )
                return

            self.history.registrar_campanha(
                creative_data,
                config,
                assets_resultado,
                status="gerado",
                revisao=revisao,
                asset_path=asset_path,
            )

            video_path = assets_resultado.get("commercial_video_file", "")
            if not is_video_media(config.get("midia", "")) and (
                not video_path
                or not os.path.isfile(str(video_path))
                or str(video_path) in ("Não solicitado", "Não solicitada", "FALHOU")
            ):
                print("⚠️ MP4 estático ausente — preview será JPEG (sem áudio embutido no arquivo)")
                if self.telegram:
                    self.telegram.notificar_sync(
                        "⚠️ *Aviso:* MP4 não gerado (FFmpeg). Preview em *imagem JPEG* "
                        "— sem áudio mixado no arquivo. Layout atual; verifique FFmpeg no servidor."
                    )

            job_id = f"{assets_resultado.get('basename', uuid.uuid4().hex[:8])}_r{revisao}"

            if usar_telegram_aprovacao:
                audio_para_aprovacao = None
                if not asset_path.lower().endswith(".mp4"):
                    audio_file = assets_resultado.get("audio_file", "")
                    if audio_file and os.path.isfile(audio_file):
                        audio_para_aprovacao = audio_file
                acao = self.telegram.aprovar_sincronamente(
                    asset_path=asset_path,
                    headline=creative_data["gancho_atencao_inicial"],
                    copy=creative_data["desenvolvimento_copy"],
                    job_id=job_id,
                    timeout_segundos=self.telegram_timeout,
                    audio_path=audio_para_aprovacao,
                    metadata={
                        "canal": config.get("canal", ""),
                        "midia": config.get("midia", ""),
                        "legenda": self._montar_caption_instagram(creative_data),
                    },
                )
                print(f"📲 Decisão Telegram: {acao['action']}")
            else:
                acao = self._aprovar_asset_terminal(creative_data, config, job_id, asset_path)
                while acao["action"] == "retry":
                    acao = self._aprovar_asset_terminal(creative_data, config, job_id, asset_path)
                print(f"🖥️ Decisão terminal: {acao['action']}")

            if acao["action"] == "approve":
                self._catalog_update(
                    campaign_id,
                    "APROVADA",
                    config,
                    creative_data,
                    assets_resultado,
                    revision=revisao,
                    actor="human",
                )
                self.memory.registrar_aprovado(
                    config.get("publico_slug", ""),
                    config.get("golpe_id", ""),
                    assets_resultado.get("basename", job_id),
                    creative_data["gancho_atencao_inicial"],
                    asset_path,
                )
                self.history.registrar_campanha(
                    creative_data,
                    config,
                    assets_resultado,
                    status="aprovado",
                    revisao=revisao,
                    asset_path=asset_path,
                )
                aprovado = True
                break

            if acao["action"] == "improve":
                if revisao >= self.max_revisoes:
                    print(f"❌ Limite de {self.max_revisoes} revisões atingido.")
                    self._catalog_update(
                        campaign_id,
                        "REJEITADA",
                        config,
                        creative_data,
                        assets_resultado,
                        revision=revisao,
                        error_message="Limite de revisões humanas atingido.",
                    )
                    return
                if self.telegram:
                    self.telegram.notificar_sync(
                        f"⏳ Job `{job_id}` em regeneração — "
                        "ignore botões de previews anteriores até o novo preview chegar."
                    )
                feedback = acao.get("prompt", "")
                print(f"📌 Você pediu: {feedback}")
                plan = classify_improvement(feedback)
                print(f"🔧 Plano de correção: {describe_plan(plan)}")
                if plan.get("narrative"):
                    print("📖 Detectada mudança de ESTÓRIA — regerando copy completa (não só imagem).")
                self._apply_narrative_override(config, feedback, golpe_obj, plan)

                self._unlock_creative_if_requested(config, feedback)

                self.memory.registrar_correcao(
                    config.get("publico_slug", ""),
                    config.get("golpe_id", ""),
                    f"{correction_tag(plan)} {feedback}",
                    assets_resultado.get("basename", ""),
                    revisao,
                    categoria=plan.get("primary_category", "copy"),
                )

                if plan.get("headline_only") and creative_data:
                    if self.telegram:
                        self.telegram.notificar_sync(
                            "📰 *Manchete* — nova headline + overlay (roteiro mantido)..."
                        )
                    creative_data = self._regenerate_headline_only(
                        creative_data, config, golpe_obj, feedback
                    )
                    recompose_next = True
                    instrucoes_melhoria = ""
                    continue

                if plan.get("golpe") and not plan.get("narrative"):
                    self._apply_golpe_variant(config, golpe_obj)
                    if self.telegram:
                        self.telegram.notificar_sync(
                            "🔄 *Variante de golpe* — nova frase no card, regerando copy..."
                        )
                    instrucoes_melhoria = self._accumulate_instrucoes(
                        config, feedback, "_instrucoes_melhoria"
                    )
                    continue

                if plan["recompose_only"] or (
                    plan["layout"] and not plan["regenerate_copy"] and not plan["regenerate_visual"]
                ):
                    if self.telegram:
                        self.telegram.notificar_sync(
                            "🔧 *Layout detectado* — recompõe cards/quebra de texto "
                            "(sem regerar copy). Aguarde o novo preview..."
                        )
                    recompose_next = True
                    instrucoes_melhoria = ""
                    continue

                if plan.get("reapply_audio_only") or (
                    plan["regenerate_audio"]
                    and not plan["regenerate_copy"]
                    and not plan["regenerate_visual"]
                    and not plan["layout"]
                ):
                    if self.telegram:
                        self.telegram.notificar_sync(
                            "🔊 *Narração* — regerando áudio "
                            f"('{NARRATION_CLOSING}' — sem regerar copy/Kling). Aguarde..."
                        )
                    reapply_audio_next = True
                    instrucoes_melhoria = ""
                    continue

                if plan.get("visual_only") or (
                    plan["regenerate_visual"]
                    and not plan["regenerate_copy"]
                    and not plan["regenerate_audio"]
                ):
                    if self.telegram:
                        self.telegram.notificar_sync(
                            "🎨 *Visual* — nova imagem/vídeo mantendo copy e áudio aprovados..."
                        )
                    visual_only_next = True
                    visual_feedback = feedback
                    instrucoes_melhoria = ""
                    continue

                if self.telegram:
                    self.telegram.notificar_sync(
                        f"📝 Regerando *{describe_plan(plan)}* com suas instruções..."
                    )
                instrucoes_melhoria = self._accumulate_instrucoes(
                    config, feedback, "_instrucoes_melhoria"
                )
                continue

            motivo = acao.get("motivo", acao["action"])
            self.memory.registrar_rejeitado(
                config.get("publico_slug", ""),
                config.get("golpe_id", ""),
                assets_resultado.get("basename", ""),
                motivo,
            )
            self._catalog_update(
                campaign_id,
                "REJEITADA",
                config,
                creative_data,
                assets_resultado,
                revision=revisao,
                error_message=motivo,
                actor="human",
            )
            print(f"❌ Campanha encerrada: {motivo}")
            return

        if not aprovado:
            return

        self.traffic_manager.structure_advertising_campaign(creative_data, assets_resultado)
        self._catalog_update(
            campaign_id,
            "PRONTA_PARA_PUBLICAR",
            config,
            creative_data,
            assets_resultado,
            revision=revisao,
        )

        if config.get("postar_instagram"):
            asset_path = self._resolve_publish_asset(assets_resultado, config)
            canal_tiktok = "tiktok" in config.get("canal", "").lower()
            if not asset_path:
                print("⚠️ Nenhum asset disponível para publicar.")
                self._catalog_update(
                    campaign_id,
                    "ERRO_PUBLICACAO",
                    config,
                    creative_data,
                    assets_resultado,
                    revision=revisao,
                    error_message="Nenhum asset disponível para publicar.",
                )
            elif canal_tiktok:
                resultado = export_tiktok_package(
                    self.BASE_DIR,
                    assets_resultado,
                    creative_data,
                    open_browser=True,
                )
                if resultado.get("ok"):
                    self._catalog_update(
                        campaign_id,
                        "PRONTA_PARA_PUBLICAR",
                        config,
                        creative_data,
                        assets_resultado,
                        revision=revisao,
                        platform="TikTok Studio",
                    )
                    aviso = (
                        "📦 Pacote TikTok exportado para upload manual.\n"
                        f"📁 Pasta: {resultado['package_dir']}\n"
                        f"🎬 Vídeo: {resultado['video']}\n"
                        f"📝 Legenda: {resultado['caption']}\n"
                        "🌐 Página de upload aberta no navegador Ubuntu."
                    )
                    print(aviso)
                    if self.telegram:
                        self.telegram.notificar_sync(aviso)
                else:
                    self._catalog_update(
                        campaign_id,
                        "ERRO_PUBLICACAO",
                        config,
                        creative_data,
                        assets_resultado,
                        revision=revisao,
                        platform="TikTok Studio",
                        error_message=str(resultado.get("erro", "")),
                    )
                    print(f"❌ Falha ao exportar pacote TikTok: {resultado.get('erro')}")
            elif self.publisher:
                if not self.catalog.can_publish(campaign_id):
                    self._catalog_update(
                        campaign_id,
                        "ERRO_PUBLICACAO",
                        config,
                        creative_data,
                        assets_resultado,
                        revision=revisao,
                        platform="Instagram",
                        error_message="Catálogo bloqueou publicação fora de estado seguro.",
                    )
                    print("❌ Catálogo bloqueou publicação fora de estado seguro.")
                    return
                self._catalog_update(
                    campaign_id,
                    "PUBLICANDO",
                    config,
                    creative_data,
                    assets_resultado,
                    revision=revisao,
                    platform="Instagram",
                )
                caption = self._montar_caption_instagram(creative_data)
                if not is_video_media(config.get("midia", "")) and asset_path.lower().endswith((".jpg", ".jpeg", ".png")):
                    print(f"📤 [Meta] Publicando imagem estática (Feed): {os.path.basename(asset_path)}")
                resultado = self.publisher.postar_asset(asset_path, caption)
                if resultado.get("ok"):
                    self._catalog_update(
                        campaign_id,
                        "PUBLICADA",
                        config,
                        creative_data,
                        assets_resultado,
                        revision=revisao,
                        platform="Instagram",
                        returned_id=str(resultado.get("post_id", "")),
                    )
                    msg = f"✅ Publicado no Instagram!\nID: `{resultado.get('post_id')}`"
                    print(msg)
                    if self.telegram:
                        self.telegram.notificar_sync(msg)
                else:
                    self._catalog_update(
                        campaign_id,
                        "ERRO_PUBLICACAO",
                        config,
                        creative_data,
                        assets_resultado,
                        revision=revisao,
                        platform="Instagram",
                        error_message=str(resultado.get("erro", "")),
                    )
                    print(f"❌ Falha ao publicar: {resultado.get('erro')}")
            else:
                self._catalog_update(
                    campaign_id,
                    "ERRO_PUBLICACAO",
                    config,
                    creative_data,
                    assets_resultado,
                    revision=revisao,
                    error_message="Publicador Meta não configurado.",
                )
                print("⚠️ Publicador Meta não configurado.")

        print("\n======================================================================")
        print("🏁 [PIPELINE DA CAMPANHA CONCLUÍDO COM SUCESSO]")
        print("======================================================================")
        print(f"📛 Identificador: {assets_resultado.get('basename', 'N/A')}")
        print(f"🖼️ Arte: {assets_resultado.get('static_image_file', 'N/A')}")
        print(f"🎬 Vídeo: {assets_resultado.get('commercial_video_file', 'N/A')}")
        print(f"🎙️ Áudio: {assets_resultado.get('audio_file', 'N/A')}")
        print(f"🔗 Link: {creative_data.get('link_conversao', 'https://guardian-ai.app')}")
        print(f"🎯 Canal: {config['canal']}")
        print(f"📈 Objetivo: {config['objetivo']}")
        if usar_telegram_aprovacao:
            print("✅ Status: APROVADO pelo administrador (via Telegram)")
        elif usar_terminal_aprovacao:
            print("✅ Status: APROVADO pelo administrador (via terminal/Desktop)")
        print("======================================================================\n")

if __name__ == "__main__":
    orchestrator = CampaignOrchestrator()
    orchestrator.execute_automated_pipeline()
