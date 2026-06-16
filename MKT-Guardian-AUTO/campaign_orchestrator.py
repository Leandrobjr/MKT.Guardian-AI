import os
import json
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Importação dos submódulos do ecossistema Guardian AI
from mkt_agent_01 import MediaFactory
from traffic_manager import TrafficManager

class CampaignOrchestrator:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-3.1-flash-lite"
        
        self.context_path = "contexto_negocio/guardian_base.json"
        self.context_data = self._load_business_context()
        
        self.media_factory = MediaFactory()
        self.traffic_manager = TrafficManager()

    def _load_business_context(self) -> dict:
        if not os.path.exists(self.context_path):
            return {}
        try:
            with open(self.context_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Erro ao ler JSON de contexto: {e}")
            return {}

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
        p_escolhido = input("Digite o número da opção desejada: ").strip()
        publico_final = opcoes_publico.get(p_escolhido, "Idosos e aposentados vulneráveis.")

        # 2. SELEÇÃO DO TIPO DE GOLPE
        print("\n⚠️ ETAPA 2: Selecione o TIPO DE GOLPE a ser abordado:")
        print("[1] Falso Parente / Novo Número (Engenharia Social)")
        print("[2] Golpe do PIX / Fraude Financeira")
        print("[3] Falsa Central Bancária / Falso Atendente")
        print("[4] Grooming / Aliciamento Digital de Menores")
        print("[5] Links de Phishing / Páginas Clonadas")
        opcoes_golpe = {
            "1": "Golpe do Falso Parente / Novo Número no WhatsApp pedindo dinheiro urgente.",
            "2": "Golpe do PIX e transferências bancárias sob indução mecânica ou pânico.",
            "3": "Golpe da Falsa Central Bancária simulando atendimento institucional de segurança.",
            "4": "Grooming / Aliciamento digital de menores e exposição de crianças em redes e jogos online.",
            "5": "Links maliciosos de Phishing e páginas clonadas projetadas para roubo de senhas."
        }
        g_escolhido = input("Digite o número da opção desejada: ").strip()
        golpe_final = opcoes_golpe.get(g_escolhido, "Fraudes gerais no WhatsApp.")

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
            "golpe": golpe_final,
            "midia": midia_final,
            "canal": canal_final,
            "objetivo": objetivo_final
        }

    def execute_automated_pipeline(self):
        # Dispara o menu interativo e captura as escolhas do usuário
        config = self.show_interactive_menu()
        
        print("\n======================================================================")
        print("🚀 [MKT GUARDIAN AI - ENGINE ORQUESTRAÇÃO v3.7] Iniciando Esteira...")
        print("======================================================================")
        
        # Consolida as respostas estruturadas para blindar os prompts dos agentes
        contexto_injetado = (
            f"DIRETRIZES DE CAMPANHA SELECIONADAS:\n"
            f"- Público-Alvo: {config['publico']}\n"
            f"- Ameaça/Golpe Abordado: {config['golpe']}\n"
            f"- Canal de Distribuição: {config['canal']}\n"
            f"- Tipo de Mídia: {config['midia']}\n"
            f"- Objetivo de Conversão: {config['objetivo']}\n\n"
            f"REGRAS DE TOM DE VOZ DA MARCA:\n"
            f"- Posicionamento: {self.context_data.get('PRODUTO_E_POSICIONAMENTO', {}).get('posicionamento_comercial')}\n"
            f"- Restrições Linguísticas: {'; '.join(self.context_data.get('PRODUTO_E_POSICIONAMENTO', {}).get('tom_de_voz_obrigatorio', {}).get('regras_linguisticas', []))}"
        )

        print("\n🧠 [Agente Redator Sênior] Escrevendo copies comerciais com base no briefing...")
        
        system_instruction = (
            "Você é o Redator Publicitário Master focado em criar criativos de alta conversão para o app Guardian AI.\n"
            "REGRAS OBRIGATÓRIAS DE OUTPUT:\n"
            "1. gancho_atencao_inicial: Deve ser uma MANCHETE curta, forte, em LETRAS MAIÚSCULAS, focada exatamente no golpe escolhido para chocar e reter o público selecionado. Máximo 10 palavras.\n"
            "2. chamada_para_acao_cta: Retorne um texto simples de comando de clique em caixa alta.\n"
            "3. desenvolvimento_copy: Roteiro argumentativo completo e empático adaptado às dores do público.\n"
            "Retorne os dados estritamente em formato JSON."
        )

        config_creative = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.35,
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "gancho_atencao_inicial": {"type": "STRING"},
                    "desenvolvimento_copy": {"type": "STRING"},
                    "chamada_para_acao_cta": {"type": "STRING"},
                    "publico_alvo_icp": {"type": "STRING"}
                },
                "required": ["gancho_atencao_inicial", "desenvolvimento_copy", "chamada_para_acao_cta", "publico_alvo_icp"]
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

        print("\n📝 CAMPANHA ESTRUTURADA PELOS AGENTES:")
        print(f"🔥 HEADLINE GERADA: {creative_data['gancho_atencao_inicial']}")
        print(f"📖 ROTEIRO DE ÁUDIO: {creative_data['desenvolvimento_copy']}\n")
        
        # INJEÇÃO TÉCNICA DE COMPATIBILIDADE: Mapeia as escolhas do menu para a Fábrica de Mídia
        creative_data["tipo_midia_selecionada"] = config["midia"]
        creative_data["canal_veiculacao_selecionado"] = config["canal"]
        
        # Envia os dados higienizados para a fábrica de mídia baseada em HTML/CSS e FFmpeg
        assets_resultado = self.media_factory.generate_campaign_assets(creative_data)
        
        # Envia as configurações para o gestor de tráfego injetar no Meta/TikTok Ads
        config_trafego = self.traffic_manager.structure_advertising_campaign(creative_data, assets_resultado)

        print("\n======================================================================")
        print("🏁 [PIPELINE DA CAMPANHA CONCLUÍDO COM SUCESSO]")
        print("======================================================================")
        print(f"🖼️ Arte Final Publicitária: {assets_resultado['static_image_file']}")
        print(f"🎙️ Áudio Mixado para {config['canal']}: {assets_resultado['audio_file']}")
        print(f"🎯 Canal de Tráfego Configurado: {config['canal']}")
        print(f"📈 Objetivo Comercial Alvo: {config['objetivo']}")
        print("======================================================================\n")

if __name__ == "__main__":
    orchestrator = CampaignOrchestrator()
    orchestrator.execute_automated_pipeline()
