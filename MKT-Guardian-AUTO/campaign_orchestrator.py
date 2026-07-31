import os
import json
import random
import re
import time
import uuid
from google import genai
from google.genai import types
from dotenv import load_dotenv

from mkt_agent_01 import MediaFactory
from traffic_manager import TrafficManager
from agent_memory import AgentMemory
from feedback_router import classify_improvement, describe_plan
from visual_variety import VisualVarietyEngine
from channel_presets import resolve_channel_preset, format_preset_summary
from tts_narration import strip_written_site_urls, card_solucao_text, NARRATION_CLOSING
from build_info import ORCHESTRATOR_VERSION, print_build_banner
from campaign_context_engine import CampaignContextEngine
from story_approval import format_story_telegram, story_keyboard

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

class CampaignOrchestrator:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    def __init__(self):
        os.chdir(self.BASE_DIR)
        load_dotenv(os.path.join(self.BASE_DIR, ".env"))
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = os.getenv("GEMINI_MODEL_TEXTO", "gemini-3.1-flash-lite")

        self.context_path = os.path.join(self.BASE_DIR, "contexto_negocio", "guardian_base.json")
        self.context_data = self._load_business_context()
        self.md_context = self._load_markdown_context()

        self.media_factory = MediaFactory()
        self.traffic_manager = TrafficManager()
        self.memory = AgentMemory(self.BASE_DIR)
        self.visual_variety = VisualVarietyEngine(self.BASE_DIR)
        self.context_engine = CampaignContextEngine(self.BASE_DIR)
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
        for nome in ("GOLPES WHATSAPP.md", "PLANO MKT Guardian AUTO.md"):
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

    def _build_cta_button(
        self, config: dict, genero_campanha: str = "neutro", campaign_ctx: dict | None = None
    ) -> str:
        if campaign_ctx and campaign_ctx.get("cta_template"):
            cta = campaign_ctx["cta_template"]
            if campaign_ctx.get("narrativa_parental") and genero_campanha == "feminino":
                return cta.replace("SEUS FILHOS", "SUA FILHA").replace("SEU FILHO", "SUA FILHA")
            if campaign_ctx.get("narrativa_parental") and genero_campanha == "masculino":
                return cta.replace("SEUS FILHOS", "SEU FILHO").replace("SUA FILHA", "SEU FILHO")
            return cta
        publico_slug = config.get("publico_slug", "")
        if publico_slug == "escolas":
            return (
                "PROTEJA SEUS ALUNOS — PAIS USEM GUARDIAN AI. PLANOS PARA GRUPOS DE ALUNOS"
            )
        publico_id = config.get("publico_id", "massa")
        if publico_id == "pais":
            if genero_campanha == "feminino":
                return "TESTE GRÁTIS — PROTEJA o WhatsApp da SUA FILHA, AGORA!"
            if genero_campanha == "masculino":
                return "TESTE GRÁTIS — PROTEJA o WhatsApp do SEU FILHO, AGORA!"
            return "TESTE GRÁTIS — PROTEJA o WhatsApp dos SEUS FILHOS, AGORA!"
        if publico_id == "idosos":
            return "TESTE GRÁTIS — PROTEJA SEU WHATSAPP AGORA!"
        if publico_id == "profissionais":
            return "TESTE GRÁTIS — PROTEJA SEU WHATSAPP BUSINESS AGORA!"
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
        text = re.sub(r"\bdo sua\b", "da sua", text, flags=re.IGNORECASE)
        text = re.sub(r"\bno sua\b", "na sua", text, flags=re.IGNORECASE)
        text = re.sub(r"\bo sua\b", "a sua", text, flags=re.IGNORECASE)
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
        if not cap:
            return ""
        lines = ["CAPACIDADES REAIS DO GUARDIAN AI (NUNCA VIOLAR):"]
        for item in cap.get("faz", []):
            lines.append(f"  ✅ {item}")
        for item in cap.get("nao_faz", []):
            lines.append(f"  ❌ {item}")
        if cap.get("regra_criativo"):
            lines.append(f"  📌 {cap['regra_criativo']}")
        return "\n".join(lines)

    def _enforce_product_truth(self, creative_data: dict) -> dict:
        """Guardian AI detecta e alerta em conversas privadas — nunca bloqueia nem monitora grupos.

        Corrige apenas frases que ATRIBUEM ao produto uma capacidade que ele não tem
        (monitorar/detectar dentro do grupo). NÃO altera frases que já contrastam
        corretamente grupo x privado (ex.: "não é no grupo, é no privado"), pois essas
        são justamente os ganchos corretos definidos em campanha_context_matrix.json —
        um regex genérico de "no/do/em grupo" quebrava essas frases e gerava
        contradições do tipo "não acontece na conversa privada, é no privado".
        """
        capacidade_patterns = [
            (r"\binfiltrad\w+ no grupo\b", "contatando o aluno no privado"),
            (r"\bpredador\w* no grupo\b", "predador no privado do WhatsApp"),
            (r"\bdetecta\w*\s+(o |a )?invasor\w*\s+no grupo\b", "alerta sobre mensagem suspeita no privado"),
            (r"\bdetecta\w* (o |a )?invasor\b", "alerta sobre mensagem suspeita no privado"),
            (r"\bmonitora\w* grupos?\b", "alerta em conversas privadas"),
            (r"\b(detecta|alerta|notifica)\w*\s+(o |a )?grupo\b", r"\1 o usuário no privado"),
        ]
        for field in ("desenvolvimento_copy", "gancho_atencao_inicial", "chamada_para_acao_cta", "texto_card_notificacao"):
            if not creative_data.get(field):
                continue
            text = creative_data[field]
            text = re.sub(r"\bbloque\w+\b", "alerta", text, flags=re.IGNORECASE)
            text = re.sub(r"\bimpede\b", "alerta", text, flags=re.IGNORECASE)
            for pattern, repl in capacidade_patterns:
                text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
            # Rede de segurança: se a substituição criar "privad..." repetido perto
            # (ex.: "...conversa privada, é no privado"), remove a redundância.
            text = re.sub(
                r"\b(conversa privada|chat privado)\b([^.!?]{0,20})\bno privado\b",
                r"\1\2",
                text,
                flags=re.IGNORECASE,
            )
            if field == "desenvolvimento_copy":
                text = strip_written_site_urls(text)
            creative_data[field] = self._fix_pt_artifacts(text)

        creative_data["texto_card_solucao"] = card_solucao_text()
        return creative_data

    def _sanitize_headline(
        self, creative_data: dict, campaign_ctx: dict, config: dict
    ) -> dict:
        """Substitui manchetes contraditórias ou quebradas por gancho rotativo do combo."""
        headline = (creative_data.get("gancho_atencao_inicial") or "").strip()
        broken = [
            r"privad[oa][^.!?]{0,30}privad[oa]",  # "privada... privado" redundante
            r"conversa privada[^.!?]{0,25}no privado",
            r"chat privado[^.!?]{0,25}no privado",
            r"não acontece[^.!?]{0,40}no privado",
        ]
        if any(re.search(p, headline, re.IGNORECASE) for p in broken):
            gancho = self._pick_rotated_gancho(campaign_ctx, config, advance=False)
            if gancho:
                creative_data["gancho_atencao_inicial"] = gancho.upper()
                print(f"⚠️ Manchete corrigida → {creative_data['gancho_atencao_inicial']}")
        return creative_data

    def _ganchos_state_path(self) -> str:
        return os.path.join(self.BASE_DIR, "contexto_negocio", "memoria", "ganchos_rotacao.json")

    def _load_ganchos_state(self) -> dict:
        path = self._ganchos_state_path()
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_ganchos_state(self, state: dict) -> None:
        try:
            with open(self._ganchos_state_path(), "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _pick_rotated_gancho(
        self, campaign_ctx: dict, config: dict, advance: bool = True
    ) -> str | None:
        """Rotaciona ganchos do combo para evitar sempre a mesma manchete."""
        cached = config.get("_gancho_rotativo")
        if cached:
            return cached

        ganchos = [g for g in (campaign_ctx.get("ganchos") or []) if g]
        if not ganchos:
            return None

        if not advance:
            return ganchos[0]

        combo = f"{config.get('publico_slug', '')}:{config.get('golpe_id', '')}"
        state = self._load_ganchos_state()
        last_idx = int(state.get(combo, -1))
        next_idx = (last_idx + 1) % len(ganchos)
        gancho = ganchos[next_idx]

        state[combo] = next_idx
        self._save_ganchos_state(state)
        config["_gancho_rotativo"] = gancho
        print(f"🎯 Gancho rotativo ({next_idx + 1}/{len(ganchos)}): {gancho[:70]}...")

        return gancho

    def _align_card_message(
        self, creative_data: dict, config: dict, campaign_ctx: dict, golpe_obj: dict
    ) -> dict:
        """Garante que o card golpista reflita o tipo de ameaça da campanha."""
        golpe_id = config.get("golpe_id", "")
        frase_ref = (campaign_ctx.get("frase_golpista") or golpe_obj.get("frase_golpista", "")).strip()
        card = (creative_data.get("texto_card_notificacao") or "").strip()
        if not frase_ref:
            return creative_data

        sinais_por_golpe = {
            "grooming": ("foto", "segredo", "bonit", "perf", "conta", "manda", "lind"),
            "pix_fantasma": ("pix", "transfer", "urgent", "pag", "dinheiro", "valor"),
            "falso_parente": ("pix", "número", "troquei", "salva", "filho", "neto"),
            "falsa_central": ("banco", "central", "senha", "conta", "bloque"),
            "phishing": ("clique", "link", "http", "bit.ly", "confirm", "cadastr"),
            "clonagem_whatsapp": ("código", "codigo", "sms", "verific", "6 dígit", "6 digit"),
        }
        sinais = sinais_por_golpe.get(golpe_id, ())
        if sinais and not any(s in card.lower() for s in sinais):
            creative_data["texto_card_notificacao"] = frase_ref
            print(f"⚠️ Card golpista alinhado ao contexto ({golpe_id})")
        return creative_data

    def _inject_phone_message_in_scene(
        self, creative_data: dict, campaign_ctx: dict, golpe_obj: dict
    ) -> dict:
        """Instrui o gerador de imagem/vídeo a mostrar a mensagem exata do golpe na tela do celular."""
        msg = (creative_data.get("texto_card_notificacao") or "").strip()
        if not msg:
            msg = (campaign_ctx.get("frase_golpista") or golpe_obj.get("frase_golpista", "")).strip()
        if not msg:
            return creative_data
        msg_show = msg[:140] + ("…" if len(msg) > 140 else "")
        clause = (
            f'Phone screen MUST show readable WhatsApp 1:1 chat with this exact suspicious '
            f'incoming message in a green bubble (Portuguese): "{msg_show}"'
        )
        creative_data["phone_screen_clause"] = clause
        cena = creative_data.get("direcao_arte_emocional", "")
        if msg_show[:40].lower() not in cena.lower():
            creative_data["direcao_arte_emocional"] = f"{cena.rstrip()}. {clause}"
        return creative_data

    def _build_ambiente(self, publico_slug: str) -> str:
        if publico_slug == "empresarios":
            return (
                "Clean organized Brazilian small business interior — neighborhood shop, commercial counter, "
                "back office with invoices or stock shelves, pleasant natural daylight, relatable working commerce, "
                "NOT home kitchen, NOT residential cooking area, NOT luxury corporate skyscraper."
            )
        if publico_slug == "escolas":
            return (
                "Clean Brazilian school administrative office or staff room, bulletin board, books, "
                "pleasant daylight, professional educational environment, NOT home kitchen, NOT bedroom."
            )
        if publico_slug == "idosos":
            return (
                "Clean well-kept Brazilian home living room, tidy painted walls, pleasant natural daylight, "
                "comfortable modest middle-income retirement setting — neat appearance, not kitchen, "
                "not worn-out poverty, not peeling paint."
            )
        ambientes = [
            (
                "Clean well-kept Brazilian home living room with sofa and TV stand, tidy painted walls, "
                "pleasant natural daylight, middle-income comfort — not luxury mansion, not poverty."
            ),
            (
                "Bright Brazilian home balcony or varanda with simple furniture, plants, tidy walls, "
                "natural daylight, neat middle-income apartment aesthetic."
            ),
            (
                "Organized Brazilian home office corner or dining table used as desk, tidy shelves, "
                "pleasant daylight, clean casual professional-at-home feel."
            ),
            (
                "Modern modest Brazilian kitchen-living open plan, clean counters, painted walls, "
                "natural light — neat and dignified, not luxury, not poverty signals."
            ),
        ]
        idx = hash(publico_slug) % len(ambientes)
        return ambientes[idx]

    def _build_publico_scene(self, publico_slug: str, golpe_id: str, genero: str = "") -> str | None:
        """Cena visual alinhada ao ICP; sobrescreve direção genérica do golpe quando necessário.
        `genero` ('feminino'/'masculino') força a coerência com o tratamento do golpe (Mãe/Pai)."""
        wa = (
            "authentic WhatsApp chat with green message bubbles visible on phone screen, "
            "worried focused expression, documentary photorealistic, "
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
            cena_mulher = (
                "Documentary photorealistic photo of a Brazilian senior woman (65-82) with reading glasses "
                f"on sofa checking {wa} scam message pretending to be a relative, "
            )
            cena_homem = (
                "Documentary photorealistic photo of a Brazilian senior man (65-82) on a living room "
                f"armchair reading {wa} urgent fake message pretending to be a relative, "
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

    def _detect_visual_gender(self, creative_data: dict) -> str:
        """Gênero da PESSOA retratada, inferido do tratamento do golpe (Mãe/Pai/Vó/Vô).
        Evita incoerência entre narrativa ('MÃE') e imagem (homem)."""
        alvo = (
            creative_data.get("texto_card_notificacao", "") + " "
            + creative_data.get("gancho_atencao_inicial", "") + " "
            + creative_data.get("desenvolvimento_copy", "")
        ).lower()
        fem = bool(re.search(r"\bm[ãa]e\b|\bvov[óo]\b|\bav[óo]\b|\btitia\b|\bsogra\b", alvo))
        masc = bool(re.search(r"\bpai\b|\bvov[ôo]\b|\bav[ôo]\b|\btitio\b|\bsogro\b", alvo))
        if fem and not masc:
            return "feminino"
        if masc and not fem:
            return "masculino"
        gc = creative_data.get("genero_campanha", "")
        return gc if gc in ("feminino", "masculino") else ""

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

    def _resolve_genero_campanha(self, creative_data: dict, config: dict) -> str:
        """Narrativa (Mãe/Pai) prevalece; caso neutro, alterna M/F entre campanhas."""
        genero_narrativa = self._detect_visual_gender(creative_data)
        publico_slug = config.get("publico_slug", "geral")
        if genero_narrativa:
            genero = genero_narrativa
        else:
            genero = self.visual_variety.next_alternating_gender(publico_slug)
        self.visual_variety.record_gender(genero, publico_slug)
        return genero

    def _build_art_direction(
        self, golpe_obj: dict, creative_data: dict, config: dict, campaign_ctx: dict | None = None
    ) -> str:
        golpe_id = config.get("golpe_id", "")
        publico_slug = config.get("publico_slug", "")
        genero_visual = self._detect_visual_gender(creative_data)

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
        creative_data = self._harmonize_gender_copy(creative_data, campaign_ctx)
        creative_data["genero_campanha"] = self._resolve_genero_campanha(creative_data, config)
        creative_data["tipo_midia_selecionada"] = config["midia"]
        creative_data["canal_veiculacao_selecionado"] = config["canal"]
        creative_data["direcao_arte_emocional"] = self._build_art_direction(
            golpe_obj, creative_data, config, campaign_ctx
        )
        creative_data = self._align_card_message(creative_data, config, campaign_ctx, golpe_obj)
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
            config, creative_data.get("genero_campanha", "neutro"), campaign_ctx
        )
        creative_data["publico_id"] = config.get("publico_id", "massa")
        creative_data["publico_slug"] = config.get("publico_slug", creative_data["publico_id"])
        creative_data["campaign_combo"] = campaign_ctx.get("combo_key", "")
        preset = resolve_channel_preset(config.get("canal", ""), config.get("midia", ""))
        creative_data["preset_midia"] = preset
        creative_data = self._enforce_product_truth(creative_data)
        return self._sanitize_headline(creative_data, campaign_ctx, config)

    def _generate_creative_data(
        self, config: dict, golpe_obj: dict, instrucoes_extras: str = ""
    ) -> dict | None:
        framework = self.context_data.get("COPYWRITING_FRAMEWORK", {})
        campaign_ctx = config.get("_campaign_context", {})
        ganchos_ref = campaign_ctx.get("ganchos") or golpe_obj.get("ganchos", [golpe_obj.get("gancho_modelo", "")])
        frase_golpista = campaign_ctx.get("frase_golpista") or golpe_obj.get("frase_golpista", "")
        publico_slug = config.get("publico_slug", "")
        golpe_id = config.get("golpe_id", "")
        produto = self.context_data.get("PRODUTO_E_POSICIONAMENTO", {})
        foco_whatsapp = produto.get(
            "foco_exclusivo",
            "Guardian AI protege EXCLUSIVAMENTE o WhatsApp — pessoal e WhatsApp Business.",
        )

        gancho_prioritario = self._pick_rotated_gancho(campaign_ctx, config, advance=True)

        memoria_txt = self.memory.format_for_prompt(
            publico=publico_slug,
            golpe=golpe_id,
        )
        preset = resolve_channel_preset(config.get("canal", ""), config.get("midia", ""))
        contexto_injetado = (
            f"DIRETRIZES DE CAMPANHA SELECIONADAS:\n"
            f"- Público-Alvo: {config['publico']}\n"
            f"- Slug ICP: {publico_slug}\n"
            f"- Ameaça/Golpe Abordado: {config['golpe']}\n"
            f"- Frase real que o golpista enviaria no WhatsApp (base para o card): {frase_golpista}\n"
            f"- Ganchos de referência (inspire-se, não copie literalmente): {' | '.join(ganchos_ref)}\n"
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
        if memoria_txt:
            contexto_injetado += f"\nMEMÓRIA — REGRAS APRENDIDAS (prioridade máxima):\n{memoria_txt}\n"
        if instrucoes_extras:
            contexto_injetado += (
                f"\nINSTRUÇÕES DE MELHORIA DO ADMINISTRADOR (prioridade absoluta):\n"
                f"{instrucoes_extras}\n"
            )

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
            "- Ele DETECTA ameaças em conversas PRIVADAS (1:1) do WhatsApp e ENVIA ALERTA imediato.\n"
            "- NÃO monitora grupos do WhatsApp — golpes em campanha devem ser em chat privado.\n"
            "- Nome da marca: sempre 'Guardian AI' (pronúncia em inglês).\n"
            "- NUNCA inclua URL, domínio ou guardian-ai.app na narração.\n\n"
            + "REGRAS OBRIGATÓRIAS DE OUTPUT (JSON estrito):\n"
            "1. gancho_atencao_inicial: MANCHETE visceral em MAIÚSCULAS, máx 10 palavras. "
            "Contraste GRUPO x PRIVADO de forma clara (ex.: 'NÃO É NO GRUPO — É NO PRIVADO DO ALUNO'). "
            "PROIBIDO frases contraditórias como 'não acontece na conversa privada, é no privado'.\n"
            f"2. desenvolvimento_copy: Roteiro PAS com {preset['copy_duration']}. "
            f"Tom: {preset['copy_tone']}.{regra_chars} "
            f"Mencione Guardian AI como solução de detecção e alerta. "
            f"NÃO inclua URL na narração — o fechamento será adicionado automaticamente.\n"
            "3. chamada_para_acao_cta: Comando curto em MAIÚSCULAS.\n"
            "4. texto_card_notificacao: APENAS a mensagem REAL do golpista no WhatsApp — "
            "use a frase_golpista do contexto como base, adaptando só o tom informal.\n"
            "5. frase_destaque_golpista: Frase-chave do golpista para destacar no card.\n"
            "6. genero_personagem_visual: DEVE respeitar GUARDRAILS e o protagonista do CONTEXTO NARRATIVO "
            "(escola=diretor/professor; empresa=comerciante; pais=pai/mãe; idoso=65+).\n"
            "7. texto_card_solucao: IGNORE este campo — será substituído automaticamente por: "
            f"'{card_solucao_text()}'\n"
            "8. publico_alvo_icp: Descrição resumida do público.\n"
            "Retorne JSON estrito."
        )

        config_creative = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
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
                    "texto_card_solucao": {"type": "STRING"},
                    "publico_alvo_icp": {"type": "STRING"},
                },
                "required": [
                    "gancho_atencao_inicial", "desenvolvimento_copy", "chamada_para_acao_cta",
                    "texto_card_notificacao", "frase_destaque_golpista", "genero_personagem_visual",
                    "texto_card_solucao", "publico_alvo_icp",
                ],
            },
        )

        for tentativa in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contexto_injetado,
                    config=config_creative,
                )
                dados = json.loads(response.text)
                return self._finalize_creative_data(dados, config, golpe_obj)
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
        print("Descreva o que mudar. Exemplos:")
        print("  • Produto: não falar em grupos — Guardian alerta só no privado (1:1)")
        print("  • Headline mais urgente / roteiro mais curto")
        print("  • Trocar personagem ou cenário (ex.: diretor escolar, não mãe)")
        print("  • Ajustar mensagem do golpista ou CTA")
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
        print(f"Headline: {creative_data.get('gancho_atencao_inicial', '')}")
        print(f"\nRoteiro: {creative_data.get('desenvolvimento_copy', '')[:400]}")
        print(f"\nCTA botão: {creative_data.get('texto_botao_conversao', creative_data.get('chamada_para_acao_cta', ''))}")
        print(f"\n🎬 Arquivo para revisar: {asset_path}")
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
                return True, creative_data

            acao = self._solicitar_aprovacao_estoria(config, creative_data, revisao, story_attempt)
            print(f"📋 Decisão estória: {acao.get('action')}")

            if acao["action"] == "retry":
                continue

            if acao["action"] == "approve":
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
                instrucoes = feedback
                self.memory.registrar_correcao(
                    config.get("publico_slug", ""),
                    config.get("golpe_id", ""),
                    f"[estoria-pre-producao] {feedback}",
                    self._story_job_id(config, revisao, story_attempt),
                    story_attempt,
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
        p_escolhido = input("Digite o número da opção desejada: ").strip()
        publico_final = opcoes_publico.get(p_escolhido, "Idosos e aposentados vulneráveis.")
        publico_id = mapa_publico_id.get(p_escolhido, "massa")
        publico_slug = mapa_publico_slug.get(p_escolhido, "geral")

        # 2. SELEÇÃO DO TIPO DE GOLPE
        print("\n⚠️ ETAPA 2: Selecione o TIPO DE GOLPE a ser abordado:")
        print("[1] Falso Parente / Novo Número (Engenharia Social)")
        print("[2] Golpe do PIX / Fraude Financeira")
        print("[3] Falsa Central Bancária / Falso Atendente")
        print("[4] Grooming / Aliciamento Digital de Menores")
        print("[5] Links de Phishing / Páginas Clonadas")
        print("[6] Clonagem de WhatsApp (Roubo de código SMS)")
        opcoes_golpe = {
            "1": "Golpe do Falso Parente / Novo Número no WhatsApp pedindo dinheiro urgente.",
            "2": "Golpe do PIX e transferências bancárias sob indução mecânica ou pânico.",
            "3": "Golpe da Falsa Central Bancária simulando atendimento institucional de segurança.",
            "4": "Grooming / Aliciamento digital de menores e exposição de crianças em redes e jogos online.",
            "5": "Links maliciosos de Phishing e páginas clonadas projetadas para roubo de senhas.",
            "6": "Clonagem de WhatsApp via engenharia social e roubo do código SMS de verificação."
        }
        mapa_golpe_id = {
            "1": "falso_parente", "2": "pix_fantasma", "3": "falsa_central",
            "4": "grooming", "5": "phishing", "6": "clonagem_whatsapp"
        }
        g_escolhido = input("Digite o número da opção desejada: ").strip()
        golpe_final = opcoes_golpe.get(g_escolhido, "Fraudes gerais no WhatsApp.")
        golpe_id = mapa_golpe_id.get(g_escolhido, "pix_fantasma")

        # 3. SELEÇÃO DA MÍDIA
        print("\n🖼️ ETAPA 3: Selecione o TIPO DE MÍDIA visual:")
        print("[1] Imagem Estática Premium (Feed do Instagram / Facebook Ads)")
        print("[2] Vídeo Comercial Animado (Reels / TikTok / YouTube Shorts)")
        m_escolhido = input("Digite o número da opção desejada: ").strip()
        midia_final = "Imagem Estática Square (1080x1080)" if m_escolhido == "1" else "Vídeo Vertical Animado"

        # 4. SELEÇÃO DO CANAL (VEICULAÇÃO / PRESET DE ÁUDIO)
        print("\n🎙️ ETAPA 4: Selecione o CANAL DE VEICULAÇÃO (Define o comportamento do Áudio):")
        print("[1] Meta Ads (Instagram/Facebook - Áudio pausado e focado em leitura)")
        print("[2] TikTok / YouTube Shorts (Áudio rápido, urgente e com trilha de suspense)")
        c_escolhido = input("Digite o número da opção desejada: ").strip()
        canal_final = "Meta Ads (Instagram/Facebook)" if c_escolhido == "1" else "TikTok / YouTube Shorts"

        # 5. SELEÇÃO DO OBJETIVO CONVERSÃO
        print("\n📈 ETAPA 5: Selecione o OBJETIVO DE CONVERSÃO técnico:")
        print("[1] Instalação Direta do Aplicativo (App Installs)")
        print("[2] Geração de Leads / Cadastro (Formulários de captação)")
        o_escolhido = input("Digite o número da opção desejada: ").strip()
        objetivo_final = "Instalação do Aplicativo (Downloads)" if o_escolhido == "1" else "Geração de Leads Qualificados"

        print("\n📲 ETAPA 6: Fluxo após gerar o criativo:")
        print("[1] Apenas salvar arquivos localmente (sem aprovação, sem Telegram)")
        print("[2] Salvar + Aprovação via Telegram (recomendado)")
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
            "objetivo": objetivo_final,
            "aprovacao_telegram": fluxo["aprovacao_telegram"],
            "aprovacao_terminal": fluxo["aprovacao_terminal"],
            "postar_instagram": fluxo["postar_instagram"],
        }

    def execute_automated_pipeline(self, config: dict | None = None, telegram_override=None):
        if config is None:
            config = self.show_interactive_menu()

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
        config["_campaign_context"] = campaign_ctx
        print(self.context_engine.summary_line(campaign_ctx))
        if self._story_approval_enabled():
            print("📋 Aprovação da estória ATIVA — vídeo/áudio só após você aprovar o roteiro.")
        preset = resolve_channel_preset(config.get("canal", ""), config.get("midia", ""))
        print(f"📐 Preset de produção: {format_preset_summary(preset)}")

        if config.get("aprovacao_telegram"):
            if telegram_override is not None:
                self.telegram = telegram_override
                print("📲 Aprovação via bot Telegram (loop único).")
            else:
                self._init_telegram()
        if config.get("postar_instagram"):
            if "tiktok" in config.get("canal", "").lower():
                self._init_tiktok_publisher()
            else:
                self._init_publisher()

        memoria_resumo = self.memory.format_for_prompt(
            publico=config.get("publico_slug", ""),
            golpe=config.get("golpe_id", ""),
            limit_correcoes=3,
        )
        if memoria_resumo:
            print(f"🧠 Memória carregada ({len(memoria_resumo.splitlines())} regras aprendidas)")

        instrucoes_melhoria = ""
        assets_resultado = {}
        creative_data = {}
        aprovado = False
        recompose_next = False
        reapply_audio_next = False

        for revisao in range(self.max_revisoes + 1):
            if recompose_next:
                print(f"\n🔧 Recompondo overlay (feedback de layout — revisão {revisao})...")
                creative_data["overlay_card_font_size"] = 20
                assets_resultado = self.media_factory.reapply_overlay_only(creative_data, assets_resultado)
                recompose_next = False
            elif reapply_audio_next:
                print(f"\n🔊 Regerando narração (pronúncia do site — revisão {revisao})...")
                assets_resultado = self.media_factory.reapply_audio_only(creative_data, assets_resultado)
                reapply_audio_next = False
            else:
                if revisao > 0:
                    print(f"\n🔄 Revisão {revisao}/{self.max_revisoes} — regerando campanha...")
                ok_estoria, creative_data = self._gerar_e_aprovar_estoria(
                    config, golpe_obj, instrucoes_melhoria, revisao
                )
                if not ok_estoria or not creative_data:
                    return
                assets_resultado = self.media_factory.generate_campaign_assets(creative_data)

            usar_telegram_aprovacao = bool(config.get("aprovacao_telegram") and self.telegram)
            # Se o Telegram foi solicitado mas não inicializou (ex.: token ausente), cai para o
            # terminal em vez de pular a aprovação — evita publicar automaticamente sem ninguém revisar.
            usar_terminal_aprovacao = bool(
                config.get("aprovacao_terminal")
                or (config.get("aprovacao_telegram") and not self.telegram)
            )
            if not (usar_telegram_aprovacao or usar_terminal_aprovacao):
                aprovado = True
                break

            asset_path = self._resolve_primary_asset(assets_resultado)
            if not asset_path:
                print("❌ Nenhum asset visual gerado para aprovação.")
                return

            video_path = assets_resultado.get("commercial_video_file", "")
            if config.get("midia") == "imagem" and (
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
                )
                print(f"📲 Decisão Telegram: {acao['action']}")
            else:
                acao = self._aprovar_asset_terminal(creative_data, config, job_id, asset_path)
                while acao["action"] == "retry":
                    acao = self._aprovar_asset_terminal(creative_data, config, job_id, asset_path)
                print(f"🖥️ Decisão terminal: {acao['action']}")

            if acao["action"] == "approve":
                self.memory.registrar_aprovado(
                    config.get("publico_slug", ""),
                    config.get("golpe_id", ""),
                    assets_resultado.get("basename", job_id),
                    creative_data["gancho_atencao_inicial"],
                    asset_path,
                )
                aprovado = True
                break

            if acao["action"] == "improve":
                if revisao >= self.max_revisoes:
                    print(f"❌ Limite de {self.max_revisoes} revisões atingido.")
                    return
                if self.telegram:
                    self.telegram.notificar_sync(
                        f"⏳ Job `{job_id}` em regeneração — "
                        "ignore botões de previews anteriores até o novo preview chegar."
                    )
                feedback = acao.get("prompt", "")
                plan = classify_improvement(feedback)
                print(f"🔧 Plano de correção: {describe_plan(plan)}")

                self.memory.registrar_correcao(
                    config.get("publico_slug", ""),
                    config.get("golpe_id", ""),
                    f"[{describe_plan(plan)}] {feedback}",
                    assets_resultado.get("basename", ""),
                    revisao,
                )

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

                if self.telegram:
                    self.telegram.notificar_sync(
                        f"📝 Regerando *{describe_plan(plan)}* com suas instruções..."
                    )
                instrucoes_melhoria = feedback
                continue

            motivo = acao.get("motivo", acao["action"])
            self.memory.registrar_rejeitado(
                config.get("publico_slug", ""),
                config.get("golpe_id", ""),
                assets_resultado.get("basename", ""),
                motivo,
            )
            print(f"❌ Campanha encerrada: {motivo}")
            return

        if not aprovado:
            return

        self.traffic_manager.structure_advertising_campaign(creative_data, assets_resultado)

        if config.get("postar_instagram"):
            asset_path = self._resolve_primary_asset(assets_resultado)
            canal_tiktok = "tiktok" in config.get("canal", "").lower()
            if not asset_path:
                print("⚠️ Nenhum asset disponível para publicar.")
            elif canal_tiktok:
                if not self.tiktok_publisher:
                    aviso = "⚠️ Publicação TikTok não configurada (verifique TIKTOK_ACCESS_TOKEN no .env)."
                    print(aviso)
                    if self.telegram:
                        self.telegram.notificar_sync(aviso)
                else:
                    caption = self._montar_caption_instagram(creative_data)
                    try:
                        resultado = self.tiktok_publisher.publish_video(asset_path, caption)
                        if resultado.get("ok"):
                            msg = f"✅ Publicado no TikTok!\nID: `{resultado.get('publish_id', '')}`"
                            print(msg)
                            if self.telegram:
                                self.telegram.notificar_sync(msg)
                        else:
                            print(f"❌ Falha ao publicar no TikTok: {resultado.get('erro')}")
                    except NotImplementedError as e:
                        aviso = (
                            f"⚠️ Publicação automática no TikTok ainda não está pronta ({e}).\n"
                            f"O arquivo está salvo em: {asset_path}"
                        )
                        print(aviso)
                        if self.telegram:
                            self.telegram.notificar_sync(aviso)
            elif self.publisher:
                caption = self._montar_caption_instagram(creative_data)
                resultado = self.publisher.postar_asset(asset_path, caption)
                if resultado.get("ok"):
                    msg = f"✅ Publicado no Instagram!\nID: `{resultado.get('post_id')}`"
                    print(msg)
                    if self.telegram:
                        self.telegram.notificar_sync(msg)
                else:
                    print(f"❌ Falha ao publicar: {resultado.get('erro')}")
            else:
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
