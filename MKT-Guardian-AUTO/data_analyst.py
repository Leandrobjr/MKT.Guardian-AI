import os
import json
from google import genai
from google.genai import types

class DataAnalyst:
    def __init__(self):
        self.client = genai.Client()
        self.model_name = "gemini-3.1-flash-lite"
        self.META_CAC_MAXIMO = 25.00

    def analyze_campaign_performance(self, campaign_id: str, real_api_data: dict = None) -> dict:
        print(f"\n📊 [Analista de Dados v2] Executando auditoria algorítmica na campanha {campaign_id}...")
        metrics = real_api_data if real_api_data else {
            "valor_gasto": 500.00, "impressoes": 40000, "cliques": 320, "ctr_porcentagem": 0.8, "conversoes_downloads": 10, "cac_atual": 50.00
        }
        
        contexto_regras = (
            f"Meta de CAC máximo: R$ {self.META_CAC_MAXIMO}. Se CAC > 25 e CTR < 1.5% -> Ação: 'REFAZER_CRIATIVOS'. "
            f"Se CAC > 25 e CTR >= 1.5% -> Ação: 'REFAZER_SEGMENTACAO'. Se CAC <= 25 -> Ação: 'ESCALAR_ORCAMENTO'. Responda em JSON."
        )

        config = types.GenerateContentConfig(
            system_instruction=contexto_regras, temperature=0.1, response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "diagnostico_funil": {"type": "STRING"},
                    "status_campanha": {"type": "STRING"},
                    "acao_corretiva_obrigatoria": {"type": "STRING"},
                    "sugestao_ajuste_prompt": {"type": "STRING"}
                },
                "required": ["diagnostico_funil", "status_campanha", "acao_corretiva_obrigatoria", "sugestao_ajuste_prompt"]
            }
        )
        try:
            response = self.client.models.generate_content(model=self.model_name, contents=json.dumps(metrics), config=config)
            analysis = json.loads(response.text)
            print(f"✅ Análise concluída. Comando: {analysis['acao_corretiva_obrigatoria']}")
            return analysis
        except Exception as e:
            print(f"❌ Erro análise: {e}")
            return {"status_campanha": "ATENCAO", "acao_corretiva_obrigatoria": "MANTER", "diagnostico_funil": "", "sugestao_ajuste_prompt": ""}
