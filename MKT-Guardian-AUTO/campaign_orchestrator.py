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
from tts_narration import strip_written_site_urls, normalize_card_solucao, NARRATION_CLOSING
from build_info import ORCHESTRATOR_VERSION, print_build_banner

try:
    from telegram_approval import TelegramApproval
except ImportError:
    TelegramApproval = None

try:
    from meta_publisher import MetaPublisher
except ImportError:
    MetaPublisher = None

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
        self.max_revisoes = int(os.getenv("MAX_REVISOES", "3"))
        self.telegram_timeout = int(os.getenv("TELEGRAM_TIMEOUT", "3600"))
        self.telegram = None
        self.publisher = None

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

    def _build_cta_button(self, config: dict, genero_campanha: str = "neutro") -> str:
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

    def _enforce_product_truth(self, creative_data: dict) -> dict:
        """Guardian AI detecta e alerta — nunca bloqueia apps, mensagens ou celular."""
        for field in ("desenvolvimento_copy", "gancho_atencao_inicial", "chamada_para_acao_cta"):
            if creative_data.get(field):
                text = creative_data[field]
                text = re.sub(r"\bbloque\w+\b", "alerta", text, flags=re.IGNORECASE)
                text = re.sub(r"\bimpede\b", "alerta", text, flags=re.IGNORECASE)
                if field == "desenvolvimento_copy":
                    text = strip_written_site_urls(text)
                creative_data[field] = self._fix_pt_artifacts(text)

        sol = creative_data.get("texto_card_solucao", "")
        creative_data["texto_card_solucao"] = normalize_card_solucao(sol)
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
                "modest comfortable retirement setting — not kitchen, not worn-out poverty, not peeling paint."
            )
        return (
            "Clean well-kept Brazilian home, tidy painted walls, pleasant natural daylight, "
            "relatable working-class comfort — not luxury mansion, not worn-out poverty, not peeling paint."
        )

    def _build_publico_scene(self, publico_slug: str, golpe_id: str) -> str | None:
        """Cena visual alinhada ao ICP; sobrescreve direção genérica do golpe quando necessário."""
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
                    f"{wa} suspicious phishing link in WhatsApp group message, diplomas on wall, "
                ),
                "clonagem_whatsapp": (
                    "Documentary photorealistic photo of a Brazilian school coordinator at office desk "
                    f"with alarmed expression reading {wa} fake WhatsApp verification code message, "
                ),
            }
            padrao = (
                "Documentary photorealistic photo of a Brazilian school principal or teacher (40-55) "
                "in an administrative office "
                f"holding smartphone with {wa} suspicious WhatsApp message, educational setting, "
            )
            return por_golpe.get(golpe_id, padrao)

        if publico_slug == "idosos":
            variants = [
                (
                    "Documentary photorealistic photo of a Brazilian senior man (65-75) on a living room "
                    f"armchair reading {wa} urgent fake PIX payment message, "
                ),
                (
                    "Documentary photorealistic photo of a Brazilian senior woman (58-72) with reading glasses "
                    f"on sofa checking {wa} scam message pretending to be bank or relative, "
                ),
                (
                    "Documentary photorealistic photo of elderly Brazilian couple at a simple dining table, "
                    f"one showing the other {wa} suspicious WhatsApp conversation, "
                ),
            ]
            return random.choice(variants)

        if publico_slug == "pais":
            por_golpe = {
                "falso_parente": random.choice([
                    (
                        "Documentary photorealistic photo of a Brazilian mother (40-52) at home "
                        f"reading {wa} message from fake son or daughter asking urgent PIX, "
                    ),
                    (
                        "Documentary photorealistic photo of a Brazilian father (40-55) in living room "
                        f"staring at {wa} fake relative emergency message, "
                    ),
                ]),
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

    def _build_art_direction(self, golpe_obj: dict, creative_data: dict, config: dict) -> str:
        golpe_id = config.get("golpe_id", "")
        publico_slug = config.get("publico_slug", "")
        msg = creative_data.get("texto_card_notificacao", "").lower()
        genero = creative_data.get("genero_personagem_visual", "").lower()

        cena_publico = self._build_publico_scene(publico_slug, golpe_id)
        base = cena_publico or golpe_obj.get("direcao_arte_emocional", "")
        ambiente = self._build_ambiente(publico_slug)

        if golpe_id == "grooming":
            feminino = any(w in msg for w in ("linda", "princesa", "gata", "manda uma foto")) or "menina" in genero
            masculino = any(w in msg for w in ("lindo", "mano", "cara")) or "menino" in genero
            if feminino:
                base = (
                    "Documentary photorealistic photo of a Brazilian mother checking her teenage "
                    "daughter's smartphone, daughter (girl, 12-15) visible in background on bed, "
                    "WhatsApp chat on phone screen with suspicious message, worried mother expression, "
                )
            elif masculino:
                base = (
                    "Documentary photorealistic photo of a Brazilian mother checking her teenage "
                    "son's smartphone, son (boy, 12-15) visible in background, "
                    "WhatsApp chat on phone with suspicious message, worried mother expression, "
                )
            else:
                base = (
                    "Documentary photorealistic photo of a Brazilian parent checking a teenager's "
                    "smartphone, WhatsApp chat with suspicious grooming message visible, "
                )

        return f"{base} {ambiente}"

    def _harmonize_gender_copy(self, creative_data: dict) -> dict:
        """Alinha filho/filha e linda/lindo entre mensagem, narração, CTA e cena visual."""
        genero = creative_data.get("genero_personagem_visual", "").lower()
        msg = creative_data.get("texto_card_notificacao", "").lower()
        feminino = "menina" in genero or "filha" in genero or "linda" in msg or "princesa" in msg
        masculino = "menino" in genero or ("filho" in genero and "filha" not in genero) or (
            "lindo" in msg and "linda" not in msg
        )

        if feminino:
            creative_data["genero_campanha"] = "feminino"
            if not genero:
                creative_data["genero_personagem_visual"] = "menina adolescente brasileira"
        elif masculino:
            creative_data["genero_campanha"] = "masculino"
            creative_data["genero_personagem_visual"] = genero or "menino adolescente brasileiro"
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
        creative_data = self._harmonize_gender_copy(creative_data)
        creative_data["tipo_midia_selecionada"] = config["midia"]
        creative_data["canal_veiculacao_selecionado"] = config["canal"]
        creative_data["direcao_arte_emocional"] = self._build_art_direction(golpe_obj, creative_data, config)
        creative_data = self.visual_variety.enrich(creative_data, config, self.context_data)

        if config.get("publico_slug") == "empresarios":
            creative_data.setdefault(
                "genero_personagem_visual",
                "empresário ou comerciante brasileiro, 35-55 anos, ambiente comercial",
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
                "diretor ou professora brasileiro em ambiente escolar",
            )

        creative_data = self._merge_regras_visuais(creative_data)
        creative_data["golpe_nome"] = golpe_obj.get("nome", config["golpe"])
        creative_data["link_conversao"] = produto.get("url_oficial", "https://guardian-ai.app")
        creative_data["texto_botao_conversao"] = self._build_cta_button(
            config, creative_data.get("genero_campanha", "neutro")
        )
        creative_data["publico_id"] = config.get("publico_id", "massa")
        creative_data["publico_slug"] = config.get("publico_slug", creative_data["publico_id"])
        preset = resolve_channel_preset(config.get("canal", ""), config.get("midia", ""))
        creative_data["preset_midia"] = preset
        return self._enforce_product_truth(creative_data)

    def _generate_creative_data(
        self, config: dict, golpe_obj: dict, instrucoes_extras: str = ""
    ) -> dict | None:
        framework = self.context_data.get("COPYWRITING_FRAMEWORK", {})
        ganchos_ref = golpe_obj.get("ganchos", [golpe_obj.get("gancho_modelo", "")])
        frase_golpista = golpe_obj.get("frase_golpista", "")
        produto = self.context_data.get("PRODUTO_E_POSICIONAMENTO", {})
        foco_whatsapp = produto.get(
            "foco_exclusivo",
            "Guardian AI protege EXCLUSIVAMENTE o WhatsApp — pessoal e WhatsApp Business.",
        )

        memoria_txt = self.memory.format_for_prompt()
        preset = resolve_channel_preset(config.get("canal", ""), config.get("midia", ""))
        contexto_injetado = (
            f"DIRETRIZES DE CAMPANHA SELECIONADAS:\n"
            f"- Público-Alvo: {config['publico']}\n"
            f"- Ameaça/Golpe Abordado: {config['golpe']}\n"
            f"- Frase real que o golpista enviaria no WhatsApp (base para o card): {frase_golpista}\n"
            f"- Ganchos de referência (inspire-se, não copie literalmente): {' | '.join(ganchos_ref)}\n"
            f"- Canal de Distribuição: {config['canal']}\n"
            f"- Tipo de Mídia: {config['midia']}\n"
            f"- Preset técnico: {preset['label']}\n"
            f"- Duração alvo da narração: {preset['copy_duration']}\n"
            f"- Tom de voz do roteiro: {preset['copy_tone']}\n"
            f"- Objetivo de Conversão: {config['objetivo']}\n\n"
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
            "- Ele DETECTA ameaças no WhatsApp e ENVIA ALERTA imediato para o usuário verificar.\n"
            "- Nome da marca: sempre 'Guardian AI' (pronúncia em inglês).\n"
            "- NUNCA inclua URL, domínio ou guardian-ai.app na narração.\n\n"
            + "REGRAS OBRIGATÓRIAS DE OUTPUT (JSON estrito):\n"
            "1. gancho_atencao_inicial: MANCHETE visceral em MAIÚSCULAS, máx 10 palavras.\n"
            f"2. desenvolvimento_copy: Roteiro PAS com {preset['copy_duration']}. "
            f"Tom: {preset['copy_tone']}.{regra_chars} "
            f"Mencione Guardian AI como solução de detecção e alerta. "
            f"NÃO inclua URL na narração — o fechamento será adicionado automaticamente.\n"
            "3. chamada_para_acao_cta: Comando curto em MAIÚSCULAS.\n"
            "4. texto_card_notificacao: APENAS a mensagem REAL do golpista no WhatsApp.\n"
            "5. frase_destaque_golpista: Frase-chave do golpista para destacar no card.\n"
            "6. genero_personagem_visual: DEVE combinar com o público-alvo da campanha.\n"
            "7. texto_card_solucao: Guardian AI detectou e enviou um ALERTA imediato ao usuário! "
            "(NUNCA diga que bloqueou, impediu ou cancelou mensagens.)\n"
            "8. publico_alvo_icp: Descrição resumida do público.\n"
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
        return f"{headline}\n\n{copy[:800]}\n\n{cta}\n\n🔗 Assine agora: {url}\n\n{hashtags}"

    def _print_creative_summary(self, creative_data: dict) -> None:
        print("\n📝 CAMPANHA ESTRUTURADA PELOS AGENTES:")
        print(f"🔥 HEADLINE: {creative_data['gancho_atencao_inicial']}")
        print(f"📖 ROTEIRO: {creative_data['desenvolvimento_copy'][:200]}...")
        print(f"👤 Gênero: {creative_data.get('genero_campanha', 'neutro')}")
        print(f"🔘 CTA: {creative_data['texto_botao_conversao']}")
        print(f"🎬 Cena: {creative_data['direcao_arte_emocional'][:120]}...\n")

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
        mapa_publico_id = {"1": "idosos", "2": "pais", "3": "profissionais", "4": "profissionais"}
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
        print("[1] Apenas salvar arquivos localmente (sem Telegram)")
        print("[2] Salvar + Aprovação via Telegram (recomendado)")
        print("[3] Salvar + Telegram + Postar no Instagram após APROVAR")
        f_escolhido = input("Digite o número da opção desejada: ").strip()
        fluxo_map = {
            "1": {"aprovacao_telegram": False, "postar_instagram": False},
            "2": {"aprovacao_telegram": True, "postar_instagram": False},
            "3": {"aprovacao_telegram": True, "postar_instagram": True},
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
            "postar_instagram": fluxo["postar_instagram"],
        }

    def execute_automated_pipeline(self):
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
        preset = resolve_channel_preset(config.get("canal", ""), config.get("midia", ""))
        print(f"📐 Preset de produção: {format_preset_summary(preset)}")

        if config.get("aprovacao_telegram"):
            self._init_telegram()
        if config.get("postar_instagram"):
            self._init_publisher()

        memoria_resumo = self.memory.format_for_prompt(limit_correcoes=3)
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
                print("\n🧠 [Agente Redator Sênior] Escrevendo copies de alta conversão...")
                creative_data = self._generate_creative_data(config, golpe_obj, instrucoes_melhoria)
                if not creative_data:
                    print("❌ Falha crítica: impossível gerar roteiro.")
                    return
                self._print_creative_summary(creative_data)
                assets_resultado = self.media_factory.generate_campaign_assets(creative_data)

            if not config.get("aprovacao_telegram") or not self.telegram:
                aprovado = True
                break

            asset_path = self._resolve_primary_asset(assets_resultado)
            if not asset_path:
                print("❌ Nenhum asset visual gerado para aprovação.")
                return

            job_id = f"{assets_resultado.get('basename', uuid.uuid4().hex[:8])}_r{revisao}"
            acao = self.telegram.aprovar_sincronamente(
                asset_path=asset_path,
                headline=creative_data["gancho_atencao_inicial"],
                copy=creative_data["desenvolvimento_copy"],
                job_id=job_id,
                timeout_segundos=self.telegram_timeout,
            )
            print(f"📲 Decisão Telegram: {acao['action']}")

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

        if config.get("postar_instagram") and self.publisher:
            asset_path = self._resolve_primary_asset(assets_resultado)
            if asset_path:
                caption = self._montar_caption_instagram(creative_data)
                resultado = self.publisher.postar_asset(asset_path, caption)
                if resultado.get("ok"):
                    if self.telegram:
                        self.telegram.notificar_sync(
                            f"✅ Publicado no Instagram!\nID: `{resultado.get('post_id')}`"
                        )
                else:
                    print(f"❌ Falha ao publicar: {resultado.get('erro')}")

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
        if config.get("aprovacao_telegram"):
            print("✅ Status: APROVADO pelo administrador")
        print("======================================================================\n")

if __name__ == "__main__":
    orchestrator = CampaignOrchestrator()
    orchestrator.execute_automated_pipeline()
