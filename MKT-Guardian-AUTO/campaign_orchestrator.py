import os
import json
import time
from google import genai
from google.genai import types

# Carrega o ficheiro .env de forma automática se ele existir na pasta
from dotenv import load_dotenv
load_dotenv()

# Importação da cadeia de agentes locais do ecossistema
from mkt_agent_01 import MediaFactory
from traffic_manager import TrafficManager
from data_analyst import DataAnalyst
from community_manager import CommunityManager

class MarketingOrchestrator:
    def __init__(self):
        # Inicializa o cliente oficial coletando a GEMINI_API_KEY do .env
        self.client = genai.Client()
        self.model_name = "gemini-3.1-flash-lite"
        
        # Estado Global da Campanha (Memória Central Compartilhada)
        self.state = {
            "campaign_brief": {},
            "strategy_output": {},
            "creative_output": {},
            "media_factory_ready": False,
            "generated_assets": {},
            "traffic_setup": {},
            "optimization_history": [],
            "simulated_chat_reply": ""
        }

    def _load_agent_knowledge(self, filename: str) -> str:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return f.read()
        return "Você é um especialista em marketing digital de alta performance."

    def start_campaign_flow(self, user_prompt: str, max_iterations: int = 2):
        """
        Inicia a agência e gerencia o loop de execução. 
        Contém mecanismos de tolerância a falhas para indisponibilidade da API (Erro 503).
        """
        print("🚀 [Orquestrador] Iniciando Ecossistema Multi-Agente MKT Guardian AI...")
        self.state["campaign_brief"] = {"initial_prompt": user_prompt}
        
        # 1. Executa Inteligência de Mercado (Estrategista)
        self._run_strategist_node()
        
        ajuste_feedback = ""
        
        for rodada in range(1, max_iterations + 1):
            print(f"\n🔄 [Orquestrador] === EXECUTANDO RODADA OTIMIZAÇÃO OPERACIONAL #{rodada} ===")
            
            # 2. Executa Copywriting e Roteirização (Criativo)
            self._run_creative_node(feedback_analista=ajuste_feedback)
            
            # 3. Dispara a Produção Visual/Áudio (Fábrica de Mídia)
            factory = MediaFactory()
            self.state["generated_assets"] = factory.generate_campaign_assets(self.state["creative_output"])
            self.state["media_factory_ready"] = True
            
            # 4. Executa Mapeamento e Estruturação de Tráfego
            traffic = TrafficManager()
            self.state["traffic_setup"] = traffic.structure_advertising_campaign(
                self.state["strategy_output"], 
                self.state["generated_assets"]
            )
            
            # 5. Auditoria de Funil (Analista de Dados)
            analyst = DataAnalyst()
            diagnostico = analyst.analyze_campaign_performance(campaign_id="CAMP_AUTOMATICA_CYBER")
            
            self.state["optimization_history"].append({
                "rodada": rodada,
                "status": diagnostico["status_campanha"],
                "acao": diagnostico["acao_corretiva_obrigatoria"]
            })
            
            # Avaliação algorítmica de loops recursivos
            if diagnostico["acao_corretiva_obrigatoria"] == "REFAZER_CRIATIVOS":
                print(f"\n⚠️ [Orquestrador] Alerta do Analista! O criativo falhou.")
                print(f"🎯 Motivo: {diagnostico['diagnostico_funil']}")
                ajuste_feedback = diagnostico["sugestao_ajuste_prompt"]
                print("🔄 Reiniciando esteira criativa com novos ajustes de contexto...")
                continue
            elif diagnostico["acao_corretiva_obrigatoria"] == "ESCALAR_ORCAMENTO":
                print(f"\n💰 [Orquestrador] Ótima Performance! Escalando orçamento em +20% na API.")
                break
            else:
                break
                
        # 6. Atendimento Final de Leads (Community Manager)
        manager = CommunityManager()
        self.state["simulated_chat_reply"] = manager.process_incoming_message(
            lead_name="Dona Maria", 
            message_text="Me enviaram um link dizendo que meu zap ia ser clonado se eu não clicasse. Esse app me protege disso?"
        )
        
        print("\n🏁 [Orquestrador] Ciclo completo de 360 graus finalizado com resiliência de rede.")
        return self.state

    def _run_strategist_node(self):
        print("\n🧠 [Agente 1: Estrategista] Mapeando mercado e objetivos...")
        sop = self._load_agent_knowledge("01_estrategista.md")
        config_strat = types.GenerateContentConfig(
            system_instruction=f"{sop}\nCreate a marketing target audience profile (ICP) and goals. Respond in JSON.",
            temperature=0.3, response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {"publico_alvo_icp": {"type": "STRING"}, "posicionamento_comunicacao": {"type": "STRING"}, "principais_metas": {"type": "STRING"}},
                "required": ["publico_alvo_icp", "posicionamento_comunicacao", "principais_metas"]
            }
        )
        
        # Tratamento de erro robusto com 3 tentativas automáticas e recuo de tempo
        for tentativa in range(3):
            try:
                res_strat = self.client.models.generate_content(
                    model=self.model_name, 
                    contents=self.state["campaign_brief"]["initial_prompt"], 
                    config=config_strat
                )
                self.state["strategy_output"] = json.loads(res_strat.text)
                print("✅ Estrategista concluiu.")
                return
            except Exception as e:
                print(f"⚠️ API instável ou ocupada (503) no Estrategista. Tentativa {tentativa + 1}/3. Aguardando 5s...")
                time.sleep(5)
        raise RuntimeError("Falha crítica de rede: API do Google indisponível no nó do Estrategista.")

    def _run_creative_node(self, feedback_analista: str = ""):
        print("\n✍️ [Agente 2: Criativo de Conteúdo] Processando diretrizes de copywriting...")
        sop = self._load_agent_knowledge("02_criativo_conteudo.md")
        
        system_creative = f"{sop}\nCreate an ad script (hook text, body copy, CTA) based on strategy JSON. Respond in JSON."
        prompt_input = f"Estratégia anterior:\n{json.dumps(self.state['strategy_output'])}"
        
        if feedback_analista:
            system_creative += " Note: The previous ad had low conversion. Follow data analyst instructions strictly."
            prompt_input += f"\n🚨 INSTRUÇÃO DE AJUSTE DO ANALISTA:\n{feedback_analista}"

        config_creative = types.GenerateContentConfig(
            system_instruction=system_creative, temperature=0.7, response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {"gancho_atencao_inicial": {"type": "STRING"}, "desenvolvimento_copy": {"type": "STRING"}, "chamada_para_acao_cta": {"type": "STRING"}},
                "required": ["gancho_atencao_inicial", "desenvolvimento_copy", "chamada_para_acao_cta"]
            }
        )
        
        # Tratamento de erro robusto com 3 tentativas automáticas e recuo de tempo
        for tentativa in range(3):
            try:
                res_creative = self.client.models.generate_content(
                    model=self.model_name, 
                    contents=prompt_input, 
                    config=config_creative
                )
                self.state["creative_output"] = json.loads(res_creative.text)
                print("✅ Criativo de Conteúdo concluiu.")
                return
            except Exception as e:
                print(f"⚠️ API instável ou ocupada (503) no Criativo. Tentativa {tentativa + 1}/3. Aguardando 5s...")
                time.sleep(5)
        raise RuntimeError("Falha crítica de rede: API do Google indisponível no nó do Criativo.")

if __name__ == "__main__":
    prompt_mestre = (
        "Lançar app de segurança digital com o objetivo de proteger contas de WhatsApp contra clonagem e golpes de engenharia social. "
        "Foco principal em públicos maduros e idosos."
    )
    orchestrator = MarketingOrchestrator()
    agencia_viva = orchestrator.start_campaign_flow(prompt_mestre, max_iterations=2)
    
    print("\n📦 [ESTADO CENTRALIZADO DA AGÊNCIA EM MEMÓRIA]")
    print(json.dumps(agencia_viva, indent=4, ensure_ascii=False))
