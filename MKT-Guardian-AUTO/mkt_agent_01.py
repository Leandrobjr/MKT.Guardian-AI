import os
import time
import random
import html
import requests
import asyncio
import base64
import subprocess
from google import genai
from google.genai import types
from playwright.async_api import async_playwright
from dotenv import load_dotenv

class MediaFactory:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    def __init__(self):
        load_dotenv(os.path.join(self.BASE_DIR, ".env"))
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        self.kling_key = os.getenv("KLING_API_KEY")

        self.client = genai.Client(api_key=self.gemini_key)
        self.model_imagem = os.getenv("GEMINI_MODEL_IMAGEM", "gemini-3.1-flash-image")
        self.voice_id = "21m00Tcm4TlvDq8ikWAM"

        self.kling_base_url = "https://api-singapore.klingai.com"

        self.output_dir = os.path.join(self.BASE_DIR, "output_campanha")
        self.frames_brutos_dir = os.path.join(self.output_dir, "frames_brutos")
        self.frames_finais_dir = os.path.join(self.output_dir, "frames_finais")
        self.base_audio_dir = os.path.join(self.BASE_DIR, "trilhas_sonoras")
        self.dir_suspense = os.path.join(self.base_audio_dir, "musicas_suspense")
        self.dir_corporativo = os.path.join(self.base_audio_dir, "musicas_corporativo")
        self.url_conversao = os.getenv("GUARDIAN_URL_CONVERSAO", "https://guardian-ai.app")

    def _render_overlay_html(
        self,
        encoded_frame: str,
        headline: str,
        alerta: str,
        solucao: str,
        cta: str,
        url: str,
    ) -> str:
        """HTML/CSS inline — sem CDN externo (Tailwind quebrava overlays no Linux headless)."""
        h = html.escape(headline.upper().strip())
        a = html.escape(alerta.strip())
        s = html.escape(solucao.strip())
        c = html.escape(cta.upper().strip())
        u = html.escape(url.strip())
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ width:1080px; height:1920px; font-family:Arial,Helvetica,sans-serif; overflow:hidden; }}
  .bg {{
    width:100%; height:100%;
    background:url('data:image/jpeg;base64,{encoded_frame}') center/cover no-repeat;
    display:flex; flex-direction:column; justify-content:space-between;
    padding:40px 36px 56px;
  }}
  .headline {{
    text-align:center; margin-top:32px; color:#fff; font-size:46px; font-weight:900;
    text-shadow:2px 2px 0 #000,-2px -2px 0 #000,0 4px 14px rgba(0,0,0,0.95);
    line-height:1.12; letter-spacing:-0.5px;
  }}
  .bottom {{ display:flex; flex-direction:column; gap:18px; }}
  .card-scam {{
    background:rgba(255,255,255,0.98); border-radius:18px; padding:22px 24px;
    border-left:8px solid #25D366; box-shadow:0 8px 32px rgba(0,0,0,0.45);
  }}
  .card-scam-label {{ color:#128C7E; font-weight:900; font-size:15px; margin-bottom:10px; }}
  .card-scam p {{ color:#111; font-size:21px; font-weight:700; line-height:1.38; }}
  .card-solucao {{
    background:linear-gradient(135deg,#1e40af 0%,#059669 100%);
    border-radius:18px; padding:22px 24px;
    box-shadow:0 8px 32px rgba(0,0,0,0.5);
  }}
  .card-solucao .brand {{ font-size:14px; font-weight:900; color:#a7f3d0; margin-bottom:8px; }}
  .card-solucao p {{ color:#fff; font-size:22px; font-weight:800; line-height:1.35; }}
  .cta {{
    background:#dc2626; color:#fff; text-align:center; padding:24px 20px;
    border-radius:18px; font-size:26px; font-weight:900;
    border-bottom:6px solid #991b1b; box-shadow:0 6px 20px rgba(0,0,0,0.4);
  }}
  .url {{
    text-align:center; color:#fff; font-size:22px; font-weight:800;
    text-shadow:1px 1px 4px #000; letter-spacing:0.5px;
  }}
</style></head><body>
<div class="bg">
  <div class="headline">{h}</div>
  <div class="bottom">
    <div class="card-scam">
      <div class="card-scam-label">⚠️ MENSAGEM SUSPEITA NO WHATSAPP</div>
      <p>{a}</p>
    </div>
    <div class="card-solucao">
      <div class="brand">🛡️ GUARDIAN AI — PROTEÇÃO WHATSAPP</div>
      <p>{s}</p>
    </div>
    <div class="cta">{c}</div>
    <div class="url">👉 {u}</div>
  </div>
</div>
</body></html>"""

    def _build_visual_prompt(self, creative_data: dict) -> str:
        """Monta prompt visual com cena do golpe + regras obrigatórias WhatsApp/humanização."""
        cena = creative_data.get("direcao_arte_emocional") or (
            "Documentary photorealistic photo of an ordinary Brazilian person in everyday clothes "
            "at home, holding a smartphone showing the WhatsApp chat screen with green message bubbles."
        )
        visuais = creative_data.get("regras_visuais") or {}
        obrigatorias = visuais.get("regras_obrigatorias", [])
        proibicoes = visuais.get("proibicoes", [])
        estilo = visuais.get(
            "estilo_fotografico",
            "Photorealistic documentary advertising, natural daylight, Brazilian everyday environment."
        )

        partes = [cena.strip(), estilo.strip()]
        if obrigatorias:
            partes.append("MANDATORY: " + " ".join(obrigatorias))
        if proibicoes:
            partes.append("FORBIDDEN: " + " ".join(proibicoes))
        partes.append(
            "Vertical 9:16 composition, all subjects fully visible without crop, "
            "clean image with no text overlays (text added later in post-production)."
        )
        return " ".join(partes)

    def generate_campaign_assets(self, creative_data: dict) -> dict:
        print("\n🏭 [Fábrica de Mídia v15.0] Motor de Composição por Frames Ativo...")
        print(f"📁 Diretório de saída: {self.output_dir}")
        print(f"🎨 Modelo de imagem (Nano Banana): {self.model_imagem}")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.frames_brutos_dir, exist_ok=True)
        os.makedirs(self.frames_finais_dir, exist_ok=True)
        
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
        solucao_texto = creative_data.get(
            "texto_card_solucao",
            "Guardian AI monitora seu WhatsApp 24h, detecta golpes e bloqueia antes do prejuízo."
        )
        url_conversao = creative_data.get("link_conversao", self.url_conversao)
        
        base_image_path = os.path.join(self.output_dir, "anuncio_base.jpg")
        final_design_path = os.path.join(self.output_dir, "anuncio_final_design.jpg")
        video_output_path = os.path.join(self.output_dir, "anuncio_video_final.mp4")

        publicidade_prompt = self._build_visual_prompt(creative_data)
        print(f"🎯 Prompt visual: {publicidade_prompt[:180]}...")

        # FLUXO DE VÍDEO REAL CORRIGIDO
        if "Vídeo" in formato_midia:
            print("🎬 [Fluxo de Vídeo Ativo] Solicitando clipe dinâmico para a Kling AI...")
            video_bruto_path = ""
            if self.kling_key:
                video_bruto_path = self._generate_kling_video(publicidade_prompt)
                
            if video_bruto_path and os.path.exists(video_bruto_path):
                print("🎞️ [Frame Processing Engine] Extraindo frames sequenciais do vídeo da IA...")
                self._extract_frames(video_bruto_path)
                
                print("📐 [HTML Headless Compositor] Queimando cards WhatsApp + solução + CTA frame por frame...")
                asyncio.run(self._compose_all_frames(
                    creative_data["gancho_atencao_inicial"],
                    alerta_texto, solucao_texto, cta_texto, url_conversao
                ))
                
                print("🎬 [FFmpeg Multiplexer] Compilando vídeo comercial em movimento com áudio de suspense...")
                self._compile_processed_video(audio_final_path, video_output_path)
            else:
                print("⚠️ Fallback: Usando renderizador estático por indisponibilidade do servidor Kling...")
                self._generate_gemini_image(publicidade_prompt, base_image_path)
                asyncio.run(self._apply_html_css_layout(
                    base_image_path, final_design_path,
                    creative_data["gancho_atencao_inicial"],
                    alerta_texto, solucao_texto, cta_texto, url_conversao
                ))
                self._compile_still_video(final_design_path, audio_final_path, video_output_path)
                
            return {"audio_file": audio_final_path, "commercial_video_file": video_output_path, "static_image_file": "Não solicitada"}
            
        else:
            print("🖼️ [Fluxo de Imagem Ativo] Gerando anúncio estático premium...")
            self._generate_gemini_image(publicidade_prompt, base_image_path)
            asyncio.run(self._apply_html_css_layout(
                base_image_path, final_design_path,
                creative_data["gancho_atencao_inicial"],
                alerta_texto, solucao_texto, cta_texto, url_conversao
            ))
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
                        raw_path = os.path.join(self.output_dir, "kling_raw.mp4")
                        with open(raw_path, "wb") as f:
                            f.write(requests.get(video_url).content)
                        return raw_path
                elif task.get("status") in ["failed", "cancelled"]: break
        except: pass
        return ""

    def _extract_frames(self, video_path: str):
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path, 
            "-q:v", "2", os.path.join(self.frames_brutos_dir, "frame_%04d.jpg")
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    async def _compose_all_frames(self, headline: str, alerta: str, solucao: str, cta: str, url: str):
        frames = sorted([f for f in os.listdir(self.frames_brutos_dir) if f.endswith(".jpg")])
        if not frames:
            print("❌ Nenhum frame extraído — overlay não aplicado.")
            return
        print(f"📐 Compondo {len(frames)} frames com cards de alerta + solução...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1080, "height": 1920})
            for frame in frames:
                frame_path = os.path.join(self.frames_brutos_dir, frame)
                with open(frame_path, "rb") as f:
                    encoded_frame = base64.b64encode(f.read()).decode("utf-8")
                await page.set_content(
                    self._render_overlay_html(encoded_frame, headline, alerta, solucao, cta, url),
                    wait_until="load",
                )
                await asyncio.sleep(0.5)
                out_path = os.path.join(self.frames_finais_dir, frame)
                await page.screenshot(path=out_path, type="jpeg", quality=95)
            await browser.close()
        print(f"✅ {len(frames)} frames compostos em {self.frames_finais_dir}")

    def _get_audio_duration(self, audio_path: str) -> float:
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", audio_path,
                ],
                capture_output=True, text=True, check=True,
            )
            return max(float(result.stdout.strip()), 8.0)
        except Exception:
            return 27.0

    def _compile_processed_video(self, audio_path: str, output_path: str):
        frames = sorted([f for f in os.listdir(self.frames_finais_dir) if f.endswith(".jpg")])
        if not frames:
            print("❌ Sem frames finais — vídeo não compilado.")
            return
        duration = self._get_audio_duration(audio_path)
        print(f"🎬 Compilando vídeo ({duration:.1f}s de narração, {len(frames)} frames em loop)...")
        subprocess.run([
            "ffmpeg", "-y",
            "-framerate", "25", "-stream_loop", "-1",
            "-i", os.path.join(self.frames_finais_dir, "frame_%04d.jpg"),
            "-i", audio_path,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-t", f"{duration:.2f}",
            output_path,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"✅ Vídeo final: {output_path}")
        for pasta in (self.frames_brutos_dir, self.frames_finais_dir):
            for arquivo in os.listdir(pasta):
                if arquivo.endswith(".jpg"):
                    os.remove(os.path.join(pasta, arquivo))

    def _generate_audio(self, text: str) -> str:
        path = os.path.join(self.output_dir, "voz_pura.mp3")
        if not self.elevenlabs_key:
            print("❌ ELEVENLABS_API_KEY ausente — narração não gerada.")
            return path
        print(f"🎙️ Gerando narração ({len(text)} caracteres)...")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": self.elevenlabs_key}
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.85, "style": 0.35},
        }
        try:
            response = requests.post(url, json=data, headers=headers, timeout=120)
            if response.status_code == 200 and len(response.content) > 1000:
                with open(path, "wb") as f:
                    f.write(response.content)
                print(f"✅ Narração salva: {path} ({len(response.content) // 1024} KB)")
            else:
                print(f"❌ ElevenLabs falhou: HTTP {response.status_code} — {response.text[:200]}")
        except Exception as e:
            print(f"❌ Erro ElevenLabs: {e}")
        return path

    def _mix_background_track(self, voz_path: str, canal: str) -> str:
        mixed_path = os.path.join(self.output_dir, "anuncio_audio_final.mp3")
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
        print(f"🎨 Gerando imagem com {self.model_imagem}...")
        try:
            response = self.client.models.generate_content(
                model=self.model_imagem,
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    with open(output_path, "wb") as f:
                        f.write(part.inline_data.data)
                    print(f"✅ Imagem salva em: {output_path}")
                    return
        except Exception as e:
            print(f"❌ Falha na geração de imagem ({self.model_imagem}): {e}")

    async def _apply_html_css_layout(
        self, input_image_path: str, output_path: str,
        headline: str, alerta: str, solucao: str, cta: str, url: str,
    ):
        with open(input_image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1080, "height": 1920})
            await page.set_content(
                self._render_overlay_html(encoded_string, headline, alerta, solucao, cta, url),
                wait_until="load",
            )
            await asyncio.sleep(0.5)
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
