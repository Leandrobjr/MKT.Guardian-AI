import os
import time
import requests
import asyncio
import base64
from google import genai
from google.genai import types
from playwright.async_api import async_playwright
from dotenv import load_dotenv

class MediaFactory:
    def __init__(self):
        load_dotenv()
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_name = "gemini-3.1-flash-lite"
        
        self.elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
        self.voice_id = "21m00Tcm4TlvDq8ikWAM"

    def generate_campaign_assets(self, creative_data: dict) -> dict:
        print("\n🏭 [Fábrica de Mídia v9.5] Gerando Design de Alta Conversão com Modelos Reais...")
        os.makedirs("output_campanha", exist_ok=True)
        
        texto_audio = f"{creative_data['gancho_atencao_inicial']}. {creative_data['desenvolvimento_copy']}"
        audio_path = self._generate_audio(texto_audio)
        
        print("🎨 [Direção de Arte] Construindo prompt de imagem com diretrizes demográficas brasileiras...")
        image_prompt = self._create_image_prompt(texto_audio, creative_data['chamada_para_acao_cta'])
        base_image_path = os.path.abspath("output_campanha/anuncio_base.jpg")
        
        self._generate_gemini_image(image_prompt, base_image_path)
        
        print("📐 [HTML Headless Render] Renderizando tipografia publicitária na imagem via Playwright...")
        final_design_path = os.path.abspath("output_campanha/anuncio_final_design.jpg")
        
        # Dispara o renderizador assíncrono do Playwright
        asyncio.run(self._apply_html_css_layout(
            base_image_path, 
            final_design_path, 
            creative_data['gancho_atencao_inicial'], 
            creative_data['chamada_para_acao_cta']
        ))
        
        return {
            "audio_file": audio_path,
            "static_image_file": final_design_path,
            "commercial_video_file": "output_campanha/anuncio_video_mock.mp4",
            "designer_prompt": image_prompt
        }

    def _generate_audio(self, text: str) -> str:
        if not self.elevenlabs_key: return "output_campanha/anuncio_audio_mock.mp3"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": self.elevenlabs_key}
        data = {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                path = "output_campanha/anuncio_audio.mp3"
                with open(path, "wb") as f: f.write(response.content)
                return path
        except: pass
        return "output_campanha/anuncio_audio_mock.mp3"

    def _create_image_prompt(self, copy_text: str, cta_text: str) -> str:
        # DIRETRIZES DE ALTA PERFORMANCE PARA SELEÇÃO DE MODELOS PUBLICITÁRIOS BRASILEIROS
        instruction = (
            "You are a Premium Advertising Art Director. Convert this marketing concept into a photorealistic campaign asset.\n"
            "CRITICAL DEMOGRAPHIC DIRECTIVES:\n"
            "- Subject Profile: Must be an attractive, well-presented Brazilian person (male or female) with warm, friendly, and trustworthy facial features.\n"
            "- Ethnicity & Look: Authentic Brazilian diversity, natural healthy look, well-groomed, professional advertising model quality.\n"
            "- Age & Context Adaptation:\n"
            "  * If context mentions ELDERLY/PARENTS/SENIORS: Present attractive mature adults or seniors (55-70 years old), elegant, with graying hair, smiling with complete relief.\n"
            "  * If context mentions FAMILY: Present a beautiful multi-generational Brazilian family (grandparents, young parents, and well-dressed children/teenagers) interacting warmly and safely.\n"
            "  * If context mentions TEENAGERS/YOUTH: Present charismatic, modern, well-dressed Brazilian teenagers or young adults (16-25 years old) using smartphones in a vibrant, safe setting.\n"
            "  * If context mentions PROFESSIONAL/BUSINESS: Present a sharp, confident Brazilian professional (30-45 years old, male or female) in a modern workspace, looking successful, organized, and secure.\n"
            "- Environment: High-end, clean, and modern Brazilian household, cozy living room, or premium office, flooded with soft, high-quality cinematic light.\n"
            "- Style & Lens: Commercial lifestyle photography, shot on 85mm f/1.4 lens, cinematic color grading, rich natural textures, professional lighting setup, clean soft background blur.\n"
            "- STRICT NEGATIVE CONSTRAINT: NO ugly or cartoonish features, NO low-quality amateur look, NO plastic skin textures, NO fake/scary expressions, NO corporate stock clichés, NO digital matrix background, NO neon shields or glowing graphics. Just a premium, beautiful real-life photograph."
        )
        for tentativa in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name, 
                    contents=f"{instruction}\n\nCampaign Target Context: {copy_text} | Focus: {cta_text}"
                )
                return response.text.strip()
            except Exception as e:
                if "429" in str(e): time.sleep(15)
                else: break
        return "A premium commercial lifestyle photograph of a well-dressed, attractive mature Brazilian couple in their 50s sitting in a modern, sunlit living room, looking at a smartphone screen with smiles of complete relief. High-end lighting, detailed skin textures, shot on 85mm camera lens."

    def _generate_gemini_image(self, prompt: str, output_path: str):
        print(f"🤖 [Gemini Multimodal] Renderizando fotografia publicitária real...")
        for tentativa in range(3):
            try:
                response = self.client.models.generate_content(
                    model="gemini-3.1-flash-image",
                    contents=f"A professional, raw, authentic real-life documentary photograph, detailed textures, natural look. {prompt}"
                )
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        with open(output_path, "wb") as f: f.write(part.inline_data.data)
                        return
            except Exception as e:
                if "429" in str(e): time.sleep(26)
                else: break

    async def _apply_html_css_layout(self, input_image_path: str, output_path: str, headline: str, cta: str):
        """
        MOTOR DE DESIGN PREMIUM (v9.5):
        - Transforma a imagem gerada em string Base64 para forçar o carregamento nativo no Playwright.
        - Renderiza a manchete gigante com tipografia limpa flutuando diretamente sobre o topo.
        - Posiciona o botão tridimensional real na base.
        """
        headline_upper = headline.upper().strip()
        cta_upper = cta.upper().strip()

        with open(input_image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@900&display=swap" rel="stylesheet">
        </head>
        <body class="m-0 p-0 overflow-hidden select-none bg-slate-900" style="font-family: 'Montserrat', sans-serif; width: 1080px; height: 1080px;">
            <div class="relative w-full h-full bg-cover bg-center flex flex-col justify-between p-12" style="background-image: url('data:image/jpeg;base64,{encoded_string}');">
                
                <div class="w-full text-center mt-4">
                    <h1 class="text-[56px] leading-[1.1] font-[900] text-white tracking-tight uppercase" style="text-shadow: -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 3px 3px 0 #000, 0px 8px 16px rgba(0,0,0,0.95);">
                        {headline_upper}
                    </h1>
                </div>

                <div class="w-full flex justify-center mb-6">
                    <div class="bg-amber-500 text-slate-950 text-[32px] font-[900] tracking-wide uppercase px-14 py-6 rounded-2xl border-b-[6px] border-amber-700 inline-block text-center max-w-[92%]" style="box-shadow: 0 12px 28px rgba(0,0,0,0.6), 0 4px 10px rgba(245,158,11,0.35);">
                        {cta_upper}
                    </div>
                </div>

            </div>
        </body>
        </html>
        """

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1080, "height": 1080})
            await page.set_content(html_content)
            
            await asyncio.sleep(0.8)
            
            await page.screenshot(path=output_path, type="jpeg", quality=98)
            await browser.close()
            print(f"✅ [HTML/CSS Engine] Snapshot final montado com modelos premium: {output_path}")
