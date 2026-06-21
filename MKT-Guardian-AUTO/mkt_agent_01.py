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
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        self.kling_key = os.getenv("KLING_API_KEY")
        
        self.client = genai.Client(api_key=self.gemini_key)
        self.model_name = "gemini-3.1-flash-lite"
        self.voice_id = "21m00Tcm4TlvDq8ikWAM"
        
        self.kling_base_url = "https://api-singapore.klingai.com"
        
        self.base_audio_dir = os.path.abspath("trilhas_sonoras")
        self.dir_suspense = os.path.join(self.base_audio_dir, "musicas_suspense")
        self.dir_corporativo = os.path.join(self.base_audio_dir, "musicas_corporativo")

    def generate_campaign_assets(self, creative_data: dict) -> dict:
        print("\n🏭 [Fábrica de Mídia v15.0] Motor de Composição por Frames Ativo...")
        os.makedirs("output_campanha", exist_ok=True)
        os.makedirs("output_campanha/frames_brutos", exist_ok=True)
        os.makedirs("output_campanha/frames_finais", exist_ok=True)
        
        formato_midia = creative_data.get("tipo_midia_selecionada", "Vídeo Vertical Reels (1080x1920)")
        canal_veiculacao = creative_data.get("canal_veiculacao_selecionado", "Meta Ads (Instagram/Facebook)")
        
        # Narração 100% dinâmica (gancho + roteiro de conversão gerado pelo orquestrador).
        # Sem injeção fixa de "MARIANA/grooming" — o conteúdo agora acompanha o golpe escolhido.
        texto_audio = (
            f"{creative_data['gancho_atencao_inicial']}. "
            f"{creative_data['desenvolvimento_copy']}"
        )
        voz_pura_path = self._generate_audio(texto_audio)
        audio_final_path = self._mix_background_track(voz_pura_path, canal_veiculacao)
        
        # Card de notificação: usa a mensagem real do golpista gerada pelo motor de copy.
        alerta_texto = creative_data.get(
            "texto_card_notificacao",
            creative_data.get("desenvolvimento_copy", "")
        )
        cta_texto = creative_data.get("chamada_para_acao_cta", "Baixe grátis agora")
        
        base_image_path = os.path.abspath("output_campanha/anuncio_base.jpg")
        final_design_path = os.path.abspath("output_campanha/anuncio_final_design.jpg")
        video_output_path = os.path.abspath("output_campanha/anuncio_video_final.mp4")

        # Direção de arte emocional dinâmica (tensão/medo, pessoas comuns) vinda do guardian_base.json.
        # Fallback mantém clima de ameaça, nunca o "tom calmo de casa de luxo".
        publicidade_prompt = creative_data.get("direcao_arte_emocional") or (
            "Cinematic fear-based advertising photograph, an ordinary worried Brazilian person reacting "
            "with alarm to a threatening message on a smartphone, dramatic tense lighting, deep shadows, "
            "photorealistic, all subjects fully visible and framed without any crop, clean textless environment, vertical 9:16."
        )

        # FLUXO DE VÍDEO REAL CORRIGIDO
        if "Vídeo" in formato_midia:
            print("🎬 [Fluxo de Vídeo Ativo] Solicitando clipe dinâmico para a Kling AI...")
            video_bruto_path = ""
            if self.kling_key:
                video_bruto_path = self._generate_kling_video(publicidade_prompt)
                
            if video_bruto_path and os.path.exists(video_bruto_path):
                print("🎞️ [Frame Processing Engine] Extraindo frames sequenciais do vídeo da IA...")
                self._extract_frames(video_bruto_path)
                
                print("📐 [HTML Headless Compositor] Queimando marcas e textos em português frame por frame...")
                asyncio.run(self._compose_all_frames(creative_data['gancho_atencao_inicial'], alerta_texto, cta_texto))
                
                print("🎬 [FFmpeg Multiplexer] Compilando vídeo comercial em movimento com áudio de suspense...")
                self._compile_processed_video(audio_final_path, video_output_path)
            else:
                print("⚠️ Fallback: Usando renderizador estático por indisponibilidade do servidor Kling...")
                self._generate_gemini_image(publicidade_prompt, base_image_path)
                asyncio.run(self._apply_html_css_layout(base_image_path, final_design_path, creative_data['gancho_atencao_inicial'], alerta_texto, cta_texto))
                self._compile_still_video(final_design_path, audio_final_path, video_output_path)
                
            return {"audio_file": audio_final_path, "commercial_video_file": video_output_path, "static_image_file": "Não solicitada"}
            
        else:
            print("🖼️ [Fluxo de Imagem Ativo] Gerando anúncio estático premium...")
            self._generate_gemini_image(publicidade_prompt, base_image_path)
            asyncio.run(self._apply_html_css_layout(base_image_path, final_design_path, creative_data['gancho_atencao_inicial'], alerta_texto, cta_texto))
            return {"audio_file": audio_final_path, "static_image_file": final_design_path, "commercial_video_file": "Não solicitado"}

    def _generate_kling_video(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {self.kling_key}", "Content-Type": "application/json"}
        payload = {
            "prompt": prompt,
            "settings": {"duration": 5, "resolution": "720p", "aspect_ratio": "9:16"}
        }
        try:
            res = requests.post(f"{self.kling_base_url}/text-to-video/kling-3.0-turbo", headers=headers, json=payload)
            task_id = res.json().get("data", {}).get("id")
            if not task_id: return ""
            
            print("⏳ Renderizando movimento na nuvem da Kling AI...")
            for _ in range(40):
                time.sleep(10)
                status_res = requests.get(f"{self.kling_base_url}/tasks?task_ids={task_id}", headers=headers)
                task = status_res.json().get("data", [])[0]
                if task.get("status") == "succeeded":
                    video_url = task.get("outputs", [{}])[0].get("url")
                    if video_url:
                        raw_path = "output_campanha/kling_raw.mp4"
                        with open(raw_path, "wb") as f:
                            f.write(requests.get(video_url).content)
                        return raw_path
                elif task.get("status") in ["failed", "cancelled"]: break
        except: pass
        return ""

    def _extract_frames(self, video_path: str):
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path, 
            "-q:v", "2", "output_campanha/frames_brutos/frame_%04d.jpg"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    async def _compose_all_frames(self, headline: str, alerta: str, cta: str):
        frames = sorted([f for f in os.listdir("output_campanha/frames_brutos") if f.endswith(".jpg")])
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1080, "height": 1920})
            
            for frame in frames:
                frame_path = os.path.abspath(f"output_campanha/frames_brutos/{frame}")
                with open(frame_path, "rb") as f:
                    encoded_frame = base64.b64encode(f.read()).decode('utf-8')
                
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <script src="https://cdn.tailwindcss.com"></script>
                    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;900&display=swap" rel="stylesheet">
                </head>
                <body class="m-0 p-0 overflow-hidden select-none" style="font-family: 'Montserrat', sans-serif; width: 1080px; height: 1920px;">
                    <div class="relative w-full h-full bg-cover bg-center flex flex-col justify-between p-12" style="background-image: url('data:image/jpeg;base64,{encoded_frame}');">
                        <div class="w-full text-center mt-12">
                            <h1 class="text-[52px] leading-[1.1] font-[900] text-white tracking-tight uppercase" style="text-shadow: -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 3px 3px 0 #000, 0px 8px 16px rgba(0,0,0,0.95);">{headline.upper()}</h1>
                        </div>
                        <div class="w-full px-6 mb-16 flex flex-col items-center gap-8">
                            <div class="w-full bg-slate-950/95 border-l-8 border-red-500 rounded-2xl p-6 shadow-2xl">
                                <div class="flex items-center gap-3 mb-3">
                                    <div class="bg-gradient-to-tr from-blue-600 to-emerald-500 px-2 py-1 rounded text-white font-[900] text-xs">Guardian-AI</div>
                                    <span class="text-emerald-400 font-[900] text-lg uppercase tracking-wider">Guardian-AI</span>
                                </div>
                                <p class="text-white text-[22px] font-[700] leading-[1.4]">{alerta}</p>
                            </div>
                            <div class="w-full text-center">
                                <div class="bg-red-600 text-white text-[26px] font-[900] tracking-wide uppercase px-6 py-5 rounded-2xl border-b-[6px] border-red-900 w-full shadow-2xl">{cta.upper()}</div>
                            </div>
                        </div>
                    </div>
                </body>
                </html>
                """
                await page.set_content(html_content)
                out_path = os.path.abspath(f"output_campanha/frames_finais/{frame}")
                await page.screenshot(path=out_path, type="jpeg", quality=95)
                
            await browser.close()

    def _compile_processed_video(self, audio_path: str, output_path: str):
        subprocess.run([
            "ffmpeg", "-y", "-framerate", "25", 
            "-i", "output_campanha/frames_finais/frame_%04d.jpg",
            "-i", audio_path,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-shortest",
            output_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Limpeza técnica de cache de frames do sistema
        subprocess.run("rm -rf output_campanha/frames_brutos/* output_campanha/frames_finais/*", shell=True)

    def _generate_audio(self, text: str) -> str:
        path = "output_campanha/voz_pura.mp3"
        if not self.elevenlabs_key: return path
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": self.elevenlabs_key}
        data = {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}}
        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                with open(path, "wb") as f: f.write(response.content)
        except: pass
        return path

    def _mix_background_track(self, voz_path: str, canal: str) -> str:
        mixed_path = "output_campanha/anuncio_audio_final.mp3"
        pasta_alvo = self.dir_suspense
        trilhas = []
        if os.path.exists(pasta_alvo):
            trilhas = [f for f in os.listdir(pasta_alvo) if f.lower().endswith('.mp3')]
        if not trilhas: return voz_path
        
        trilha_path = os.path.join(pasta_alvo, random.choice(trilhas))
        cmd = [
            "ffmpeg", "-y", "-i", voz_path, "-stream_loop", "-1", "-i", trilha_path,
            "-filter_complex", "[1:a]volume=-24dB[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "[a]", "-c:a", "libmp3lame", "-b:a", "192k", mixed_path
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return mixed_path
        except: return voz_path

    def _generate_gemini_image(self, prompt: str, output_path: str):
        try:
            response = self.client.models.generate_content(model="gemini-3.1-flash-image", contents=prompt)
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    with open(output_path, "wb") as f: f.write(part.inline_data.data)
                    return
        except: pass

    async def _apply_html_css_layout(self, input_image_path: str, output_path: str, headline: str, alerta: str, cta: str):
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
            <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;900&display=swap" rel="stylesheet">
        </head>
        <body class="m-0 p-0 overflow-hidden select-none bg-slate-900" style="font-family: 'Montserrat', sans-serif; width: 1080px; height: 1920px;">
            <div class="relative w-full h-full bg-cover bg-center flex flex-col justify-between p-12" style="background-image: url('data:image/jpeg;base64,{encoded_string}');">
                <div class="w-full text-center mt-12">
                    <h1 class="text-[52px] leading-[1.1] font-[900] text-white tracking-tight uppercase" style="text-shadow: -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 3px 3px 0 #000, 0px 8px 16px rgba(0,0,0,0.95);">{headline_upper}</h1>
                </div>
                <div class="w-full px-6 mb-16 flex flex-col items-center gap-8">
                    <div class="w-full bg-slate-950/95 border-l-8 border-red-500 rounded-2xl p-6 shadow-2xl">
                        <div class="flex items-center gap-3 mb-3">
                            <div class="bg-gradient-to-tr from-blue-600 to-emerald-500 px-2 py-1 rounded text-white font-[900] text-xs">Guardian-AI</div>
                            <span class="text-emerald-400 font-[900] text-lg uppercase tracking-wider">Guardian-AI</span>
                        </div>
                        <p class="text-white text-[22px] font-[700] leading-[1.4]">{alerta}</p>
                    </div>
                    <div class="w-full text-center">
                        <div class="bg-red-600 text-white text-[26px] font-[900] tracking-wide uppercase px-6 py-5 rounded-2xl border-b-[6px] border-red-900 w-full shadow-2xl">{cta_upper}</div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1080, "height": 1920})
            await page.set_content(html_content)
            await asyncio.sleep(0.8)
            await page.screenshot(path=output_path, type="jpeg", quality=98)
            await browser.close()

    def _compile_still_video(self, image_path: str, audio_path: str, output_video_path: str):
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", image_path, "-i", audio_path,
            "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest", output_video_path
        ]
        try: subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except: pass
