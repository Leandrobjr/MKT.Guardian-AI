import os
import time
import random
import requests
import asyncio
import base64
import subprocess
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
        
        # Definição dos caminhos absolutos do seu estoque de áudios
        self.base_audio_dir = os.path.abspath("trilhas_sonoras")
        self.dir_suspense = os.path.join(self.base_audio_dir, "musicas_suspense")
        self.dir_corporativo = os.path.join(self.base_audio_dir, "musicas_corporativo")
        self.dir_efeitos = os.path.join(self.base_audio_dir, "efeitos_sonoros")

    def generate_campaign_assets(self, creative_data: dict) -> dict:
        print("\n🏭 [Fábrica de Mídia v11.0] Iniciando Geração Multimodal Avançada...")
        os.makedirs("output_campanha", exist_ok=True)
        
        # Captura as escolhas dinâmicas do menu interativo
        formato_midia = creative_data.get("tipo_midia_selecionada", "Imagem Estática Square (1080x1080)")
        canal_veiculacao = creative_data.get("canal_veiculacao_selecionado", "Meta Ads (Instagram/Facebook)")
        
        texto_audio = f"{creative_data['gancho_atencao_inicial']}. {creative_data['desenvolvimento_copy']}"
        
        # Gerar a locução de voz pura via ElevenLabs
        voz_pura_path = self._generate_audio(texto_audio)
        
        # Selecionar e misturar a trilha de fundo ideal com base no canal
        audio_final_path = self._mix_background_track(voz_pura_path, canal_veiculacao)
        
        print("🎨 [Direção de Arte] Construindo prompt de imagem com diretrizes demográficas brasileiras...")
        image_prompt = self._create_image_prompt(texto_audio, creative_data['chamada_para_acao_cta'])
        base_image_path = os.path.abspath("output_campanha/anuncio_base.jpg")
        
        self._generate_gemini_image(image_prompt, base_image_path)
        
        final_design_path = os.path.abspath("output_campanha/anuncio_final_design.jpg")
        video_output_path = os.path.abspath("output_campanha/anuncio_video_final.mp4")
        
        nova_cta_usuario = "PROTEJA SEU WHATSAPP AGORA!!! CLIQUE AQUI!"

        # Renderização condicional baseada na escolha de mídia
        if "Vídeo" in formato_midia:
            print("📐 [HTML & FFmpeg Engine] Renderizando e compilando Vídeo Comercial Animado...")
            asyncio.run(self._apply_html_css_layout(base_image_path, final_design_path, creative_data['gancho_atencao_inicial'], nova_cta_usuario, animar=True))
            self._compile_video_with_ffmpeg(final_design_path, audio_final_path, video_output_path)
        else:
            print("📐 [HTML Headless Render] Renderizando Arte Estática Premium para Redes Sociais...")
            asyncio.run(self._apply_html_css_layout(base_image_path, final_design_path, creative_data['gancho_atencao_inicial'], nova_cta_usuario, animar=False))

        return {
            "audio_file": audio_final_path,
            "static_image_file": final_design_path,
            "commercial_video_file": video_output_path if "Vídeo" in formato_midia else "Não solicitado",
            "designer_prompt": image_prompt
        }

    def _generate_audio(self, text: str) -> str:
        path = "output_campanha/voz_pura.mp3"
        if not self.elevenlabs_key:
            print("⚠️ Sem chave ElevenLabs. Gerando arquivo de salvaguarda...")
            with open(path, "wb") as f: f.write(b"\x00" * 1000)
            return path
            
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": self.elevenlabs_key}
        data = {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                with open(path, "wb") as f: f.write(response.content)
                return path
        except: pass
        return path

    def _mix_background_track(self, voz_path: str, canal: str) -> str:
        """Sorteia uma trilha do estoque e faz a mixagem inteligente usando FFmpeg."""
        mixed_path = "output_campanha/anuncio_audio_final.mp3"
        
        # Decide qual pasta olhar baseado no canal de veiculação
        pasta_alvo = self.dir_suspense if "TikTok" in canal else self.dir_corporativo
        
        # Tenta listar os arquivos mp3 dentro da pasta escolhida
        trilhas = []
        if os.path.exists(pasta_alvo):
            trilhas = [f for f in os.listdir(pasta_alvo) if f.lower().endswith('.mp3')]
            
        if not trilhas:
            print(f"ℹ️ Nenhuma trilha encontrada em '{os.basename(pasta_alvo)}'. Usando apenas a voz limpa.")
            return voz_path

        # Sorteia um arquivo de áudio aleatório do seu estoque de 10 a 20 músicas
        trilha_sorteada = random.choice(trilhas)
        trilha_path = os.path.join(pasta_alvo, trilha_sorteada)
        print(f"🎵 [Mixer Automatizado] Trilha sorteada para {canal}: {trilha_sorteada}")

        # Executa a mixagem de áudio nativa via FFmpeg aplicando redução de volume na trilha (-22dB)
        # Isso garante que a trilha de fundo não cubra a voz principal da ElevenLabs
        cmd = [
            "ffmpeg", "-y",
            "-i", voz_path,
            "-stream_loop", "-1", "-i", trilha_path,
            "-filter_complex", "[1:a]volume=-22dB[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "[a]",
            "-c:a", "libmp3lame", "-b:a", "192k",
            mixed_path
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return mixed_path
        except Exception as e:
            print(f"⚠️ Falha na mixagem do FFmpeg: {e}. Usando voz pura.")
            return voz_path

    def _create_image_prompt(self, copy_text: str, cta_text: str) -> str:
        instruction = (
            "You are a Premium Advertising Art Director. Convert this marketing concept into a photorealistic campaign asset.\n"
            "CRITICAL DEMOGRAPHIC DIRECTIVES:\n"
            "- Subject Profile: Must be an attractive, well-presented Brazilian person (male or female) with warm, friendly, and trustworthy facial features.\n"
            "- Ethnicity & Look: Authentic Brazilian diversity, natural healthy look, well-groomed, professional advertising model quality.\n"
            "- Environment: High-end, clean, and modern Brazilian household, cozy living room, flooded with soft, high-quality cinematic light.\n"
            "- Style & Lens: Commercial lifestyle photography, shot on 85mm f/1.4 lens, cinematic color grading, rich natural textures, soft background blur.\n"
            "- STRICT NEGATIVE CONSTRAINT: NO digital matrix background, NO neon shields or glowing graphics. Just a premium, beautiful real-life photograph."
        )
        try:
            response = self.client.models.generate_content(model=self.model_name, contents=f"{instruction}\n\nContext: {copy_text}")
            return response.text.strip()
        except:
            return "A premium commercial lifestyle photograph of an attractive Brazilian person looking at a smartphone screen with a smile of complete relief. High-end lighting, detailed skin textures, shot on 85mm camera lens."

    def _generate_gemini_image(self, prompt: str, output_path: str):
        print(f"🤖 [Gemini Multimodal] Renderizando fotografia publicitária real...")
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
            print(f"⚠️ Erro ao gerar imagem: {e}")

    async def _apply_html_css_layout(self, input_image_path: str, output_path: str, headline: str, cta: str, animar: bool):
        headline_upper = headline.upper().strip()
        cta_upper = cta.upper().strip()

        with open(input_image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

        # Animação sutil de zoom contínuo para reter a atenção em formatos de vídeo
        animation_css = """
        @keyframes pulseScale {
            0% { transform: scale(1); }
            50% { transform: scale(1.04); }
            100% { transform: scale(1); }
        }
        .animate-criativo { animation: pulseScale 4s ease-in-out infinite; }
        """ if animar else ""

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@900&display=swap" rel="stylesheet">
            <style>{animation_css}</style>
        </head>
        <body class="m-0 p-0 overflow-hidden select-none bg-slate-900" style="font-family: 'Montserrat', sans-serif; width: 1080px; height: 1080px;">
            <div class="relative w-full h-full bg-cover bg-center flex flex-col justify-between p-12 {'animate-criativo' if animar else ''}" style="background-image: url('data:image/jpeg;base64,{encoded_string}');">
                
                <div class="w-full text-center mt-4">
                    <h1 class="text-[56px] leading-[1.1] font-[900] text-white tracking-tight uppercase" style="text-shadow: -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 3px 3px 0 #000, 0px 8px 16px rgba(0,0,0,0.95);">
                        {headline_upper}
                    </h1>
                </div>

                <div class="w-full flex justify-center mb-6">
                    <div class="bg-amber-500 text-slate-950 text-[30px] font-[900] tracking-wide uppercase px-12 py-6 rounded-2xl border-b-[6px] border-amber-700 inline-block text-center max-w-[95%]" style="box-shadow: 0 12px 28px rgba(0,0,0,0.6), 0 4px 10px rgba(245,158,11,0.35);">
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

    def _compile_video_with_ffmpeg(self, image_path: str, audio_path: str, output_video_path: str):
        """Compila o vídeo final sincronizando perfeitamente a imagem animada com a trilha mixada."""
        print("🎬 [FFmpeg Multiplexer] Montando contêiner MP4 de alto desempenho...")
        if os.path.exists(output_video_path):
            os.remove(output_video_path)
            
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            output_video_path
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            print(f"✅ [FFmpeg] Vídeo final integrado com sucesso.")
        except Exception as e:
            print(f"❌ Erro na compilação do MP4 via FFmpeg: {e}")
