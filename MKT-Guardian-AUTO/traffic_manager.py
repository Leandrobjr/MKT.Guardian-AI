import os
import json
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

class TrafficManager:
    def __init__(self):
        load_dotenv()
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY não encontrada. Crie o arquivo .env com base no .env.example."
            )
        self.client = genai.Client(api_key=api_key)
        
        # Amarrando explicitamente o modelo atual da família 3.1
        self.model_name = "gemini-3.1-flash-lite"
        
        self.meta_access_token = os.environ.get("META_ACCESS_TOKEN")
        self.meta_ad_account_id = os.environ.get("META_AD_ACCOUNT_ID")

    def structure_advertising_campaign(self, strategy_data: dict, media_assets: dict) -> dict:
        print("\n🎯 [Gestor de Tráfego] Iniciando o mapeamento técnico da campanha...")
        
        system_instruction = "Translate the target audience specification into precise technical Meta Ads targeting configuration (age range, gender, interests) in JSON format."
        prompt_input = f"Público Alvo: {strategy_data.get('publico_alvo_icp')}"
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "idade_minima": {"type": "INTEGER"},
                    "idade_maxima": {"type": "INTEGER"},
                    "genero": {"type": "STRING"},
                    "interesses_meta_keywords": {"type": "ARRAY", "items": {"type": "STRING"}}
                },
                "required": ["idade_minima", "idade_maxima", "genero", "interesses_meta_keywords"]
            }
        )
        
        for tentativa in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt_input],
                    config=config
                )
                targeting = json.loads(response.text)
                print("✅ Segmentação mapeada com sucesso.")
                
                return {
                    "campaign_setup": {"name": "CAMPANHA_AUTOMATICA_MKT", "objective": "OUTCOMES", "status": "PAUSED"},
                    "ad_set_setup": {"name": "CONJUNTO_BRAZIL_TARGET", "targeting_criteria": targeting, "daily_budget_brl": 50.0},
                    "ad_creative_setup": {"headline": media_assets.get("designer_prompt")[:25] if media_assets.get("designer_prompt") else "Proteção Digital", "body_copy": "Ative o escudo invisível do seu app."}
                }
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait = 20 * (tentativa + 1)
                    print(f"⚠️ [Tráfego Rate Limit] Tentativa {tentativa + 1}/3. Aguardando {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"❌ [Tráfego] Erro não recuperável: {e}")
                    break
                    
        print("❌ Falha de rede resiliente no nó de tráfego. Retornando mapeamento padrão de salvaguarda.")
        return {
            "campaign_setup": {"name": "CAMPANHA_AUTOMATICA_MKT_FALLBACK", "objective": "OUTCOMES", "status": "PAUSED"},
            "ad_set_setup": {"targeting_criteria": {"idade_minima": 25, "idade_maxima": 65, "genero": "ALL", "interesses_meta_keywords": ["Cybersecurity", "Mobile Apps"]}}
        }
