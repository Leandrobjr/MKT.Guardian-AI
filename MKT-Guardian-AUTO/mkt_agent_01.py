import os
import time
import random
import shutil
import subprocess
import requests
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types
from dotenv import load_dotenv


class MediaFactory:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # Identidade visual guardian-ai.app
    BRAND_NAVY = (11, 20, 36)
    BRAND_CARD = (15, 23, 42)
    BRAND_CARD_BORDER = (30, 58, 95)
    BRAND_GREEN = (52, 211, 153)
    BRAND_GREEN_DARK = (16, 185, 129)
    BRAND_TEXT = (255, 255, 255)
    BRAND_TEXT_MUTED = (148, 163, 184)
    BRAND_HIGHLIGHT = (251, 191, 36)
    BRAND_CTA_TEXT = (11, 20, 36)
    WHATSAPP_GREEN = (37, 211, 102)
    FONT_CANDIDATES = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    def __init__(self):
        load_dotenv(os.path.join(self.BASE_DIR, ".env"))
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        # Aceita os dois nomes de variavel (novo e legado) para compatibilidade com .env existente
        self.elevenlabs_key = (
            os.getenv("ELEVENLABS_API_KEY")
            or os.getenv("ELEVEN_LABS_API_KEY")
            or os.getenv("ELEVENLABS_KEY")
        )
        self.kling_key = os.getenv("KLING_API_KEY")

        self.client = genai.Client(api_key=self.gemini_key)
        self.model_imagem = os.getenv("GEMINI_MODEL_IMAGEM", "gemini-3.1-flash-image")
        self.voice_id = (
            os.getenv("ELEVENLABS_VOICE_ID")
            or os.getenv("ELEVEN_LABS_VOICE_ID")
            or "21m00Tcm4TlvDq8ikWAM"
        )

        self.kling_base_url = "https://api-singapore.klingai.com"

        self.output_dir = os.path.join(self.BASE_DIR, "output_campanha")
        self.frames_brutos_dir = os.path.join(self.output_dir, "frames_brutos")
        self.frames_finais_dir = os.path.join(self.output_dir, "frames_finais")
        self.frames_loop_dir = os.path.join(self.output_dir, "frames_loop")
        self.base_audio_dir = os.path.join(self.BASE_DIR, "trilhas_sonoras")
        self.dir_suspense = os.path.join(self.base_audio_dir, "musicas_suspense")
        self.dir_corporativo = os.path.join(self.base_audio_dir, "musicas_corporativo")
        self.url_conversao = os.getenv("GUARDIAN_URL_CONVERSAO", "https://guardian-ai.app")

    def _load_font(self, size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = self.FONT_CANDIDATES if bold else self.FONT_CANDIDATES[1:]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    continue
        return ImageFont.load_default()

    def _text_width(self, draw: ImageDraw.ImageDraw, text: str, font) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def _wrap_text(self, draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int = 4) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            trial = " ".join(current + [word])
            if self._text_width(draw, trial, font) <= max_width:
                current.append(word)
            else:
                if current:
                    lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
        return lines[:max_lines]

    def _draw_text_with_shadow(
        self, draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill=(255, 255, 255)
    ):
        x, y = xy
        for dx, dy in ((-2, -2), (2, -2), (-2, 2), (2, 2), (0, 3)):
            draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
        draw.text((x, y), text, font=font, fill=fill)

    def _format_highlight_phrase(self, phrase: str) -> str:
        p = phrase.strip().strip('"').strip("'")
        if not p.endswith("!"):
            p += "!"
        return f'"{p.upper()}"'

    def _draw_rich_text_block(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        text: str,
        font,
        default_color: tuple,
        highlight_phrases: list[str],
        highlight_color: tuple,
    ):
        x0, y0, x1, _y1 = box
        max_w = x1 - x0 - 40
        lines = self._wrap_text(draw, text, font, max_w, max_lines=5)
        y = y0
        for line in lines:
            x = x0 + 20
            lower_line = line.lower()
            segments: list[tuple[str, bool]] = []
            if highlight_phrases:
                work = line
                while work:
                    best = None
                    for hp in highlight_phrases:
                        hp_fmt = self._format_highlight_phrase(hp).strip('"').rstrip("!").lower()
                        idx = work.lower().find(hp_fmt)
                        if idx == -1:
                            for variant in (hp.lower(), hp_fmt):
                                idx = work.lower().find(variant)
                                if idx != -1:
                                    break
                        if idx != -1 and (best is None or idx < best[0]):
                            best = (idx, idx + len(hp_fmt), hp)
                    if best is None:
                        segments.append((work, False))
                        break
                    idx, end, hp = best
                    if idx > 0:
                        segments.append((work[:idx], False))
                    segments.append((self._format_highlight_phrase(hp), True))
                    work = work[end:]
            else:
                segments = [(line, False)]

            for seg, is_hi in segments:
                color = highlight_color if is_hi else default_color
                draw.text((x, y), seg, font=font, fill=color)
                x += self._text_width(draw, seg, font)
            y += 34

    def _draw_headline_branded(
        self, draw: ImageDraw.ImageDraw, headline: str, highlight_phrases: list[str]
    ):
        font = self._load_font(42, bold=True)
        lines = self._wrap_text(draw, headline.upper(), font, 980, max_lines=3)
        y = 56
        for line in lines:
            x = 540 - self._text_width(draw, line, font) // 2
            self._draw_text_with_shadow(draw, (x, y), line, font, self.BRAND_TEXT)
            for hp in highlight_phrases:
                hp_core = hp.upper().strip('"').strip("'").rstrip("!")
                if hp_core and hp_core in line:
                    idx = line.find(hp_core)
                    prefix = line[:idx]
                    highlighted = self._format_highlight_phrase(hp)
                    x_hi = x + self._text_width(draw, prefix, font)
                    draw.text((x_hi, y), highlighted, font=font, fill=self.BRAND_GREEN)
            y += 50

    def _draw_brand_card(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        title: str,
        body: str,
        title_color: tuple,
        body_color: tuple,
        highlight_phrases: list[str] | None = None,
        highlight_color: tuple | None = None,
    ):
        x0, y0, x1, y1 = box
        draw.rounded_rectangle(box, radius=20, fill=self.BRAND_CARD, outline=self.BRAND_CARD_BORDER, width=2)
        font_title = self._load_font(20, bold=True)
        font_body = self._load_font(26, bold=True)
        draw.text((x0 + 20, y0 + 14), title, font=font_title, fill=title_color)
        body_box = (x0, y0 + 46, x1, y1 - 10)
        if highlight_phrases:
            self._draw_rich_text_block(
                draw, body_box, body, font_body, body_color,
                highlight_phrases, highlight_color or self.BRAND_HIGHLIGHT,
            )
        else:
            lines = self._wrap_text(draw, body, font_body, (x1 - x0) - 40, max_lines=4)
            y = y0 + 48
            for line in lines:
                draw.text((x0 + 20, y), line, font=font_body, fill=body_color)
                y += 34

    def _draw_cta_button(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], main_text: str, url: str):
        draw.rounded_rectangle(box, radius=36, fill=self.BRAND_GREEN, outline=self.BRAND_GREEN_DARK, width=3)
        font_main = self._load_font(24, bold=True)
        font_url = self._load_font(18, bold=True)
        lines = self._wrap_text(draw, main_text.upper(), font_main, box[2] - box[0] - 40, max_lines=2)
        y = box[1] + 18
        for line in lines:
            x = (box[0] + box[2]) // 2 - self._text_width(draw, line, font_main) // 2
            draw.text((x, y), line, font=font_main, fill=self.BRAND_CTA_TEXT)
            y += 30
        url_clean = url.replace("https://", "").replace("http://", "")
        xu = (box[0] + box[2]) // 2 - self._text_width(draw, url_clean, font_url) // 2
        draw.text((xu, box[3] - 36), url_clean, font=font_url, fill=self.BRAND_CTA_TEXT)

    def _compose_frame_pillow(
        self,
        frame_path: str,
        out_path: str,
        headline: str,
        alerta: str,
        solucao: str,
        cta: str,
        url: str,
        frases_destaque: list[str] | None = None,
    ):
        img = Image.open(frame_path).convert("RGB")
        img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(img)
        highlights = frases_destaque or []

        self._draw_headline_branded(draw, headline, highlights)

        self._draw_brand_card(
            draw, (36, 1050, 1044, 1240),
            "MENSAGEM SUSPEITA NO WHATSAPP",
            alerta,
            self.WHATSAPP_GREEN, self.BRAND_TEXT,
            highlight_phrases=highlights, highlight_color=self.BRAND_HIGHLIGHT,
        )
        self._draw_brand_card(
            draw, (36, 1260, 1044, 1440),
            "GUARDIAN AI — PROTECAO WHATSAPP",
            solucao,
            self.BRAND_GREEN, self.BRAND_TEXT,
        )
        self._draw_cta_button(
            draw, (36, 1470, 1044, 1600),
            cta,
            url,
        )

        img.save(out_path, "JPEG", quality=95)

    def _compose_all_frames(
        self, headline: str, alerta: str, solucao: str, cta: str, url: str,
        frases_destaque: list[str] | None = None,
    ):
        frames = sorted(f for f in os.listdir(self.frames_brutos_dir) if f.endswith(".jpg"))
        if not frames:
            print("❌ Nenhum frame bruto — overlay não aplicado.")
            return False
        print(f"📐 [Pillow] Compondo {len(frames)} frames (identidade Guardian AI)...")
        for frame in frames:
            src = os.path.join(self.frames_brutos_dir, frame)
            dst = os.path.join(self.frames_finais_dir, frame)
            self._compose_frame_pillow(src, dst, headline, alerta, solucao, cta, url, frases_destaque)
        print(f"✅ Overlay aplicado em {len(frames)} frames.")
        return True

    def _apply_pillow_layout(
        self, input_image_path: str, output_path: str,
        headline: str, alerta: str, solucao: str, cta: str, url: str,
        frases_destaque: list[str] | None = None,
    ):
        self._compose_frame_pillow(
            input_image_path, output_path, headline, alerta, solucao, cta, url, frases_destaque,
        )

    def _build_visual_prompt(self, creative_data: dict) -> str:
        cena = creative_data.get("direcao_arte_emocional") or (
            "Documentary photorealistic photo of an ordinary Brazilian person in everyday clothes "
            "at home, holding a smartphone showing the WhatsApp chat screen with green message bubbles."
        )
        visuais = creative_data.get("regras_visuais") or {}
        obrigatorias = visuais.get("regras_obrigatorias", [])
        proibicoes = visuais.get("proibicoes", [])
        estilo = visuais.get(
            "estilo_fotografico",
            "Photorealistic documentary advertising, natural daylight, Brazilian everyday environment.",
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

    def _audio_ok(self, path: str, min_bytes: int = 5000) -> bool:
        return os.path.isfile(path) and os.path.getsize(path) >= min_bytes

    def generate_campaign_assets(self, creative_data: dict) -> dict:
        print("\n🏭 [Fábrica de Mídia v15.2] Compositor Pillow + FFmpeg...")
        print(f"📁 Diretório de saída: {self.output_dir}")
        print(f"🎨 Modelo de imagem: {self.model_imagem}")

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.frames_brutos_dir, exist_ok=True)
        os.makedirs(self.frames_finais_dir, exist_ok=True)

        formato_midia = creative_data.get("tipo_midia_selecionada", "Vídeo Vertical Reels (1080x1920)")
        canal_veiculacao = creative_data.get("canal_veiculacao_selecionado", "Meta Ads (Instagram/Facebook)")

        texto_audio = (
            f"{creative_data['gancho_atencao_inicial']}. "
            f"{creative_data['desenvolvimento_copy']}"
        )
        voz_pura_path = self._generate_audio(texto_audio)
        if not self._audio_ok(voz_pura_path):
            print("❌ CRÍTICO: Narração não gerada — verifique ELEVENLABS_API_KEY e créditos.")
        audio_final_path = self._mix_background_track(voz_pura_path, canal_veiculacao)

        alerta_texto = creative_data.get("texto_card_notificacao", "")
        solucao_texto = creative_data.get(
            "texto_card_solucao",
            "Guardian AI monitora seu WhatsApp 24h, detecta golpes e bloqueia antes do prejuízo.",
        )
        cta_texto = creative_data.get(
            "texto_botao_conversao",
            creative_data.get("chamada_para_acao_cta", "TESTE GRÁTIS — PROTEJA SEU WHATSAPP AGORA!"),
        )
        url_conversao = creative_data.get("link_conversao", self.url_conversao)
        headline = creative_data.get("gancho_atencao_inicial", "")
        frases_destaque: list[str] = []
        if creative_data.get("frase_destaque_golpista"):
            frases_destaque.append(creative_data["frase_destaque_golpista"])
        frases_destaque.extend(creative_data.get("frases_destaque_extra", []))

        print(f"📝 Card golpe: {alerta_texto[:80]}...")
        print(f"🛡️ Card solução: {solucao_texto[:80]}...")
        print(f"🔗 Link: {url_conversao}")

        base_image_path = os.path.join(self.output_dir, "anuncio_base.jpg")
        final_design_path = os.path.join(self.output_dir, "anuncio_final_design.jpg")
        video_output_path = os.path.join(self.output_dir, "anuncio_video_final.mp4")
        if os.path.exists(video_output_path):
            os.remove(video_output_path)

        publicidade_prompt = self._build_visual_prompt(creative_data)

        if "Vídeo" in formato_midia:
            print("🎬 Solicitando clipe Kling AI...")
            video_bruto_path = self._generate_kling_video(publicidade_prompt) if self.kling_key else ""

            if video_bruto_path and os.path.exists(video_bruto_path):
                self._extract_frames(video_bruto_path)
                overlay_ok = self._compose_all_frames(
                    headline, alerta_texto, solucao_texto, cta_texto, url_conversao, frases_destaque,
                )
                if overlay_ok and self._audio_ok(audio_final_path):
                    self._compile_processed_video(audio_final_path, video_output_path)
                else:
                    print("❌ Vídeo NÃO gerado — overlay ou áudio inválido.")
            else:
                print("⚠️ Fallback: imagem estática + vídeo...")
                self._generate_gemini_image(publicidade_prompt, base_image_path)
                self._apply_pillow_layout(
                    base_image_path, final_design_path,
                    headline, alerta_texto, solucao_texto, cta_texto, url_conversao, frases_destaque,
                )
                if self._audio_ok(audio_final_path):
                    self._compile_still_video(final_design_path, audio_final_path, video_output_path)

            return {
                "audio_file": audio_final_path,
                "commercial_video_file": video_output_path if os.path.exists(video_output_path) else "FALHOU",
                "static_image_file": "Não solicitada",
            }

        print("🖼️ Fluxo de imagem estática...")
        self._generate_gemini_image(publicidade_prompt, base_image_path)
        self._apply_pillow_layout(
            base_image_path, final_design_path,
            headline, alerta_texto, solucao_texto, cta_texto, url_conversao, frases_destaque,
        )
        return {
            "audio_file": audio_final_path,
            "static_image_file": final_design_path,
            "commercial_video_file": "Não solicitado",
        }

    def _generate_kling_video(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {self.kling_key}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "settings": {"duration": 5, "resolution": "720p", "aspect_ratio": "9:16"}}
        try:
            res = requests.post(f"{self.kling_base_url}/text-to-video/kling-3.0-turbo", headers=headers, json=payload, timeout=60)
            task_id = res.json().get("data", {}).get("id")
            if not task_id:
                print(f"❌ Kling sem task_id: {res.text[:200]}")
                return ""
            print("⏳ Renderizando na Kling AI (fila da nuvem — tempo varia)...")
            inicio = time.time()
            for tentativa in range(40):
                time.sleep(5)
                elapsed = int(time.time() - inicio)
                if tentativa % 2 == 0:
                    print(f"   ... {elapsed}s aguardando render Kling")
                status_res = requests.get(f"{self.kling_base_url}/tasks?task_ids={task_id}", headers=headers, timeout=30)
                task = status_res.json().get("data", [])[0]
                if task.get("status") == "succeeded":
                    video_url = task.get("outputs", [{}])[0].get("url")
                    if video_url:
                        raw_path = os.path.join(self.output_dir, "kling_raw.mp4")
                        with open(raw_path, "wb") as f:
                            f.write(requests.get(video_url, timeout=120).content)
                        print(f"✅ Kling concluiu em {int(time.time() - inicio)}s")
                        return raw_path
                elif task.get("status") in ("failed", "cancelled"):
                    break
        except Exception as e:
            print(f"❌ Erro Kling: {e}")
        return ""

    def _extract_frames(self, video_path: str):
        for f in os.listdir(self.frames_brutos_dir):
            if f.endswith(".jpg"):
                os.remove(os.path.join(self.frames_brutos_dir, f))
        cmd = [
            "ffmpeg", "-y", "-an", "-i", video_path,
            "-q:v", "2", os.path.join(self.frames_brutos_dir, "frame_%04d.jpg"),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        count = len([f for f in os.listdir(self.frames_brutos_dir) if f.endswith(".jpg")])
        print(f"🎞️ {count} frames extraídos (áudio Kling descartado).")
        if count == 0:
            print(f"❌ FFmpeg extract erro: {result.stderr[-300:]}")

    def _get_audio_duration(self, audio_path: str) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                capture_output=True, text=True, check=True,
            )
            return max(float(result.stdout.strip()), 10.0)
        except Exception:
            return 27.0

    def _prepare_looped_frames(self, frames: list[str], duration: float, fps: int = 25) -> int:
        shutil.rmtree(self.frames_loop_dir, ignore_errors=True)
        os.makedirs(self.frames_loop_dir)
        needed = int(duration * fps) + 2
        for i in range(needed):
            src_name = frames[i % len(frames)]
            shutil.copy2(
                os.path.join(self.frames_finais_dir, src_name),
                os.path.join(self.frames_loop_dir, f"frame_{i + 1:04d}.jpg"),
            )
        return needed

    def _compile_processed_video(self, audio_path: str, output_path: str):
        frames = sorted(f for f in os.listdir(self.frames_finais_dir) if f.endswith(".jpg"))
        if not frames:
            print("❌ Sem frames finais.")
            return
        duration = self._get_audio_duration(audio_path)
        total = self._prepare_looped_frames(frames, duration)
        print(f"🎬 Compilando {total} frames ({duration:.1f}s) + narração...")
        cmd = [
            "ffmpeg", "-y", "-framerate", "25",
            "-i", os.path.join(self.frames_loop_dir, "frame_%04d.jpg"),
            "-i", audio_path,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-t", f"{duration:.2f}",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ FFmpeg compile erro: {result.stderr[-400:]}")
            return
        print(f"✅ Vídeo final: {output_path} ({os.path.getsize(output_path) // 1024} KB)")
        self._cleanup_frame_cache()

    def _cleanup_frame_cache(self):
        for pasta in (self.frames_brutos_dir, self.frames_finais_dir, self.frames_loop_dir):
            if not os.path.isdir(pasta):
                continue
            for arquivo in os.listdir(pasta):
                if arquivo.endswith(".jpg"):
                    os.remove(os.path.join(pasta, arquivo))

    def _generate_audio(self, text: str) -> str:
        path = os.path.join(self.output_dir, "voz_pura.mp3")
        if not self.elevenlabs_key:
            print("❌ Chave ElevenLabs ausente no .env. Use ELEVENLABS_API_KEY (ou ELEVEN_LABS_API_KEY).")
            return path
        print(f"🎙️ Gerando narração ({len(text)} chars)...")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": self.elevenlabs_key}
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.9, "style": 0.45},
        }
        try:
            response = requests.post(url, json=data, headers=headers, timeout=120)
            if response.status_code == 200 and len(response.content) > 1000:
                with open(path, "wb") as f:
                    f.write(response.content)
                print(f"✅ Narração: {len(response.content) // 1024} KB, ~{self._get_audio_duration(path):.0f}s")
            else:
                print(f"❌ ElevenLabs HTTP {response.status_code}: {response.text[:300]}")
        except Exception as e:
            print(f"❌ ElevenLabs erro: {e}")
        return path

    def _mix_background_track(self, voz_path: str, canal: str) -> str:
        mixed_path = os.path.join(self.output_dir, "anuncio_audio_final.mp3")
        if not self._audio_ok(voz_path):
            print("❌ Sem narração válida — mixagem abortada.")
            return voz_path

        pasta_alvo = self.dir_corporativo if "Meta" in canal else self.dir_suspense
        trilhas = []
        if os.path.isdir(pasta_alvo):
            trilhas = [f for f in os.listdir(pasta_alvo) if f.lower().endswith(".mp3")]
        if not trilhas:
            print("⚠️ Sem trilha em trilhas_sonoras/ — usando só narração.")
            return voz_path

        trilha_path = os.path.join(pasta_alvo, random.choice(trilhas))
        print(f"🎵 Mixando narração + trilha ({os.path.basename(trilha_path)})...")
        cmd = [
            "ffmpeg", "-y", "-i", voz_path, "-stream_loop", "-1", "-i", trilha_path,
            "-filter_complex",
            "[0:a]volume=1.5,highpass=f=80[voz];"
            "[1:a]volume=-6dB[trilha];"
            "[voz][trilha]amix=inputs=2:duration=first:dropout_transition=2:weights=1 0.45[a]",
            "-map", "[a]", "-c:a", "libmp3lame", "-b:a", "192k", mixed_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and self._audio_ok(mixed_path):
            print(f"✅ Áudio mixado: {mixed_path}")
            return mixed_path
        print(f"⚠️ Mix falhou, usando narração pura: {result.stderr[-200:]}")
        return voz_path

    def _generate_gemini_image(self, prompt: str, output_path: str):
        print(f"🎨 Gerando imagem ({self.model_imagem})...")
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
                    print(f"✅ Imagem: {output_path}")
                    return
        except Exception as e:
            print(f"❌ Imagem falhou: {e}")

    def _compile_still_video(self, image_path: str, audio_path: str, output_video_path: str):
        duration = self._get_audio_duration(audio_path)
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", image_path, "-i", audio_path,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-t", f"{duration:.2f}",
            output_video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Vídeo estático: {output_video_path}")
        else:
            print(f"❌ Vídeo estático falhou: {result.stderr[-300:]}")
