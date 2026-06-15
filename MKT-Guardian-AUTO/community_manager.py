import os
from google import genai

class CommunityManager:
    def __init__(self):
        self.client = genai.Client()
        self.model_name = "gemini-3.1-flash-lite"

    def process_incoming_message(self, lead_name: str, message_text: str) -> str:
        print(f"\n💬 [Community Manager] Novo lead '{lead_name}' enviou uma mensagem.")
        prompt = f"Você é um gestor de comunidade profissional. Responda com empatia e foco comercial ao lead {lead_name} que disse: '{message_text}'"
        try:
            response = self.client.models.generate_content(model=self.model_name, contents=prompt)
            return response.text.strip()
        except Exception as e:
            print(f"❌ Erro chat: {e}")
            return "Olá! Como posso ajudar com a segurança do seu WhatsApp hoje?"
