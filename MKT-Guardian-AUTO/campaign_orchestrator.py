import os
import json
import re
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Importação dos submódulos do ecossistema Guardian AI
from mkt_agent_01 import MediaFactory
from traffic_manager import TrafficManager

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
            r"(Guardian AI[^.!?]*[.!?]\s*)Ela\s+(detecta|bloqueia|monitora|envia|avisa)",
            r"\1Ele \2",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"(O app[^.!?]*[.!?]\s*)Ela\s+(detecta|bloqueia|monitora|envia|avisa)",
            r"\1Ele \2",
            text,
            flags=re.IGNORECASE,
        )
        return text

    def _build_art_direction(self, golpe_obj: dict, creative_data: dict, config: dict) -> str:
        base = golpe_obj.get("direcao_arte_emocional", "")
        golpe_id = config.get("golpe_id", "")
        msg = creative_data.get("texto_card_notificacao", "").lower()
        genero = creative_data.get("genero_personagem_visual", "").lower()

        ambiente = (
            "Clean well-kept Brazilian home, tidy painted walls, pleasant natural daylight, "
            "relatable working-class comfort — not luxury mansion, not worn-out poverty, not peeling paint."
        )

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

        return {
            "publico": publico_final,
            "publico_id": publico_id,
            "publico_slug": publico_slug,
            "golpe": golpe_final,
            "golpe_id": golpe_id,
            "midia": midia_final,
            "canal": canal_final,
            "objetivo": objetivo_final
        }

    def execute_automated_pipeline(self):
        # Dispara o menu interativo e captura as escolhas do usuário
        config = self.show_interactive_menu()
        
        print("\n======================================================================")
        print("🚀 [MKT GUARDIAN AI - ENGINE ORQUESTRAÇÃO v3.8] Iniciando Esteira...")
        print(f"📁 Diretório de trabalho: {self.BASE_DIR}")
        print(f"🧠 Modelo de copy: {self.model_name}")
        print("======================================================================")
        
        # Busca os ganchos virais, a frase real do golpista e a direção de arte do guardian_base.json
        golpe_obj = next(
            (g for g in self.context_data.get("TIPOS_DE_GOLPE", []) if g.get("id") == config.get("golpe_id")),
            {}
        )
        framework = self.context_data.get("COPYWRITING_FRAMEWORK", {})
        ganchos_ref = golpe_obj.get("ganchos", [golpe_obj.get("gancho_modelo", "")])
        frase_golpista = golpe_obj.get("frase_golpista", "")

        produto = self.context_data.get("PRODUTO_E_POSICIONAMENTO", {})
        foco_whatsapp = produto.get(
            "foco_exclusivo",
            "Guardian AI protege EXCLUSIVAMENTE o WhatsApp — pessoal e WhatsApp Business."
        )

        contexto_injetado = (
            f"DIRETRIZES DE CAMPANHA SELECIONADAS:\n"
            f"- Público-Alvo: {config['publico']}\n"
            f"- Ameaça/Golpe Abordado: {config['golpe']}\n"
            f"- Frase real que o golpista enviaria no WhatsApp (base para o card): {frase_golpista}\n"
            f"- Ganchos de referência (inspire-se, não copie literalmente): {' | '.join(ganchos_ref)}\n"
            f"- Canal de Distribuição: {config['canal']}\n"
            f"- Tipo de Mídia: {config['midia']}\n"
            f"- Objetivo de Conversão: {config['objetivo']}\n\n"
            f"FOCO DO PRODUTO (OBRIGATÓRIO):\n"
            f"- {foco_whatsapp}\n"
            f"- Toda narrativa deve mencionar WhatsApp explicitamente.\n"
            f"- Nunca fale de segurança genérica, cibersegurança abstrata ou outros apps.\n"
            f"- O golpe acontece DENTRO do WhatsApp (mensagem, link, código, clonagem).\n\n"
            f"REGRAS DE TOM DE VOZ DA MARCA:\n"
            f"- Posicionamento: {produto.get('posicionamento_comercial')}\n"
            f"- Restrições Linguísticas: {'; '.join(produto.get('tom_de_voz_obrigatorio', {}).get('regras_linguisticas', []))}\n\n"
            f"CONTEXTO ESTRATÉGICO DE NEGÓCIO (documentos oficiais):\n"
            f"{self.md_context[:12000] if self.md_context else 'Documentos MD não encontrados em contexto_negocio/'}"
        )

        print("\n🧠 [Agente Redator Sênior] Escrevendo copies de alta conversão (resposta direta)...")

        roteiro = framework.get("roteiro_narracao_modelo", {})
        roteiro_txt = "\n".join(f"   - {k}: {v}" for k, v in roteiro.items())

        system_instruction = (
            "Você é o Maior Copywriter de Resposta Direta do Brasil, especialista em anúncios de alta "
            "conversão para o app Guardian AI — proteção EXCLUSIVA do WhatsApp (pessoal e Business). "
            "Seu objetivo é SENSIBILIZAR a dor do público e levá-lo a baixar o app IMEDIATAMENTE. "
            "Nunca use tom calmo ou institucional. Nunca fale de segurança genérica — sempre WhatsApp.\n\n"
            f"FRAMEWORK OBRIGATÓRIO: {framework.get('estrutura_obrigatoria', 'PAS — Problema, Agitação, Solução, Urgência')}\n"
            + ("PRINCÍPIOS:\n" + "\n".join(f"   - {p}" for p in framework.get("principios", [])) + "\n\n" if framework.get("principios") else "")
            + (f"ESTRUTURA DO ROTEIRO DE NARRAÇÃO (siga os tempos):\n{roteiro_txt}\n\n" if roteiro_txt else "")
            + "REGRAS OBRIGATÓRIAS DE OUTPUT (JSON estrito):\n"
            "1. gancho_atencao_inicial: MANCHETE visceral em MAIÚSCULAS, máx 10 palavras. "
            "Deve citar WhatsApp, golpe ou PIX. Nada genérico sobre 'celular' ou 'internet'.\n"
            "2. desenvolvimento_copy: Roteiro de narração de 20-27s seguindo Problema→Agitação→Solução→Urgência. "
            "Descreva o golpe acontecendo NO WHATSAPP. Na SOLUÇÃO, explique claramente o que o Guardian AI faz "
            "(monitora, detecta, bloqueia golpes no WhatsApp). Termine convidando a baixar GRÁTIS em guardian-ai.app "
            "(escrito assim na copy; a narração fala o endereço em português automaticamente).\n"
            "Mantenha 'Guardian AI' em inglês ao citar o nome do aplicativo — isso soa natural na voz.\n"
            "3. chamada_para_acao_cta: Comando curto em MAIÚSCULAS. Ex: 'BAIXE GRÁTIS — PROTEJA SEU WHATSAPP'.\n"
            "4. texto_card_notificacao: APENAS a mensagem REAL que o golpista enviaria no WhatsApp. "
            "O genero da vitima na mensagem DEVE combinar com genero_personagem_visual "
            "(se escrever 'linda' = menina/filha em TODA a copy incluindo headline; se 'lindo' = menino/filho).\n"
            "Guardian AI é masculino (ele/o app detecta, bloqueia) — NUNCA use 'ela' para o app.\n"
            "5. frase_destaque_golpista: A frase-chave mais chocante do golpista para destacar "
            "no card (ex: 'NÃO CONTA PRA SUA MÃE'). Será exibida entre aspas com exclamação.\n"
            "6. genero_personagem_visual: Quem aparece na cena — ex: 'menina adolescente', "
            "'menino adolescente', 'mulher madura', 'homem', 'idoso'.\n"
            "7. texto_card_solucao: Card de SOLUÇÃO (1-2 frases). Guardian AI detectou e bloqueou no WhatsApp.\n"
            "8. publico_alvo_icp: Descrição resumida do público para segmentação.\n"
            "PROIBIDO: falar de outros apps, redes sociais genéricas, escudos digitais, hackers genéricos.\n"
            "Retorne os dados estritamente em formato JSON."
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
                    "publico_alvo_icp": {"type": "STRING"}
                },
                "required": [
                    "gancho_atencao_inicial", "desenvolvimento_copy", "chamada_para_acao_cta",
                    "texto_card_notificacao", "frase_destaque_golpista", "genero_personagem_visual",
                    "texto_card_solucao", "publico_alvo_icp"
                ]
            }
        )

        creative_data = {}
        for tentativa in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contexto_injetado,
                    config=config_creative
                )
                creative_data = json.loads(response.text)
                break
            except Exception as e:
                if "429" in str(e):
                    time.sleep(15)
                else:
                    print(f"❌ Erro no Agente Criativo: {e}")
                    return

        if not creative_data:
            print("❌ Falha crítica: Impossível gerar roteiro.")
            return

        # INJEÇÃO TÉCNICA DE COMPATIBILIDADE: Mapeia as escolhas do menu para a Fábrica de Mídia
        creative_data = self._harmonize_gender_copy(creative_data)
        creative_data["tipo_midia_selecionada"] = config["midia"]
        creative_data["canal_veiculacao_selecionado"] = config["canal"]
        creative_data["direcao_arte_emocional"] = self._build_art_direction(golpe_obj, creative_data, config)
        creative_data["regras_visuais"] = self.context_data.get("DIRETRIZES_VISUAIS", {})
        creative_data["golpe_nome"] = golpe_obj.get("nome", config["golpe"])
        creative_data["link_conversao"] = produto.get("url_oficial", "https://guardian-ai.app")
        creative_data["texto_botao_conversao"] = self._build_cta_button(
            config, creative_data.get("genero_campanha", "neutro")
        )
        creative_data["publico_id"] = config.get("publico_id", "massa")
        creative_data["publico_slug"] = config.get("publico_slug", creative_data["publico_id"])

        print("\n📝 CAMPANHA ESTRUTURADA PELOS AGENTES:")
        print(f"🔥 HEADLINE GERADA: {creative_data['gancho_atencao_inicial']}")
        print(f"📖 ROTEIRO DE ÁUDIO: {creative_data['desenvolvimento_copy']}")
        print(f"👤 Gênero campanha: {creative_data.get('genero_campanha', 'neutro')}")
        print(f"🔘 CTA: {creative_data['texto_botao_conversao']}\n")

        # Envia os dados higienizados para a fábrica de mídia
        assets_resultado = self.media_factory.generate_campaign_assets(creative_data)
        
        # Envia as configurações para o gestor de tráfego injetar no Meta/TikTok Ads
        config_trafego = self.traffic_manager.structure_advertising_campaign(creative_data, assets_resultado)

        print("\n======================================================================")
        print("🏁 [PIPELINE DA CAMPANHA CONCLUÍDO COM SUCESSO]")
        print("======================================================================")
        print(f"📛 Identificador: {assets_resultado.get('basename', 'N/A')}")
        print(f"🖼️ Arte Final Publicitária: {assets_resultado['static_image_file']}")
        print(f"🎬 Vídeo Comercial Final: {assets_resultado.get('commercial_video_file', 'N/A')}")
        print(f"🎙️ Áudio para {config['canal']}: {assets_resultado['audio_file']}")
        print(f"🔗 Link de conversão: {creative_data.get('link_conversao', 'https://guardian-ai.app')}")
        print(f"🎯 Canal de Tráfego Configurado: {config['canal']}")
        print(f"📈 Objetivo Comercial Alvo: {config['objetivo']}")
        print("======================================================================\n")

if __name__ == "__main__":
    orchestrator = CampaignOrchestrator()
    orchestrator.execute_automated_pipeline()
