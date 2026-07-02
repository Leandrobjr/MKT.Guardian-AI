import os
import re
import time
import random
import shutil
import subprocess
from datetime import datetime
import requests
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types
from dotenv import load_dotenv

from visual_variety import VisualVarietyEngine
from channel_presets import resolve_channel_preset, format_preset_summary
from build_info import MEDIA_FACTORY_VERSION, print_build_banner
from video_motion import build_natural_frame_sequence, motion_prompt_suffix, still_video_zoom_filter
from video_compositor import compile_kling_pipeline, compose_still_with_overlay
from tts_narration import build_narration_script, card_solucao_text, resolve_overlay_cta, NARRATION_CLOSING
from kling_client import (
    KLING_BASE_URL,
    explain_balance_error,
    fetch_resource_packages,
    format_balance_report,
    kling_headers,
    parse_kling_response,
)


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

        self.kling_base_url = KLING_BASE_URL

        self.output_dir = os.path.join(self.BASE_DIR, "output_campanha")
        self.work_dir = os.path.join(self.output_dir, "_work")
        self.frames_brutos_dir = os.path.join(self.work_dir, "frames_brutos")
        self.frames_finais_dir = os.path.join(self.work_dir, "frames_finais")
        self.frames_loop_dir = os.path.join(self.work_dir, "frames_loop")
        self.base_audio_dir = os.path.join(self.BASE_DIR, "trilhas_sonoras")
        self.dir_suspense = os.path.join(self.base_audio_dir, "musicas_suspense")
        self.dir_corporativo = os.path.join(self.base_audio_dir, "musicas_corporativo")
        self.url_conversao = os.getenv("GUARDIAN_URL_CONVERSAO", "https://guardian-ai.app")
        self.card_body_font_size = 22
        self.visual_variety = VisualVarietyEngine(self.BASE_DIR)
        self.canvas_width = 1080
        self.canvas_height = 1920
        self.preset_midia: dict = {}

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
            if self._text_width(draw, word, font) > max_width:
                if current:
                    lines.append(" ".join(current))
                    current = []
                chunk = ""
                for ch in word:
                    trial = chunk + ch
                    if self._text_width(draw, trial, font) <= max_width:
                        chunk = trial
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = ch
                if chunk:
                    if current:
                        lines.append(" ".join(current))
                        current = []
                    current = [chunk]
                continue
            trial = " ".join(current + [word]) if current else word
            if self._text_width(draw, trial, font) <= max_width:
                current.append(word)
            else:
                if current:
                    lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
        return lines[:max_lines]

    def _parse_highlight_spans(self, text: str, highlight_phrases: list[str]) -> list[tuple[str, bool]]:
        if not highlight_phrases or not text:
            return [(text, False)]
        work = text
        spans: list[tuple[str, bool]] = []
        while work:
            best = None
            for hp in highlight_phrases:
                variants = [
                    hp,
                    hp.strip('"').strip("'"),
                    hp.strip('"').strip("'").rstrip("!"),
                ]
                for variant in variants:
                    if not variant:
                        continue
                    idx = work.lower().find(variant.lower())
                    if idx != -1 and (best is None or idx < best[0]):
                        best = (idx, idx + len(variant), True)
            if best is None:
                spans.append((work, False))
                break
            idx, end, is_hi = best
            if idx > 0:
                spans.append((work[:idx], False))
            spans.append((work[idx:end], is_hi))
            work = work[end:]
        return spans

    def _flow_words_to_lines(
        self,
        draw: ImageDraw.ImageDraw,
        spans: list[tuple[str, bool]],
        font,
        max_width: int,
        max_lines: int,
    ) -> list[list[tuple[str, bool]]]:
        lines: list[list[tuple[str, bool]]] = [[]]
        line_widths = [0]

        def append_word(word: str, is_hi: bool) -> bool:
            prefix = " " if lines[-1] else ""
            trial = prefix + word
            w = self._text_width(draw, trial, font)
            if line_widths[-1] + w > max_width and lines[-1]:
                if len(lines) >= max_lines:
                    return False
                lines.append([])
                line_widths.append(0)
                prefix = ""
                trial = word
                w = self._text_width(draw, trial, font)
            lines[-1].append((word, is_hi))
            line_widths[-1] += w
            return True

        for seg, is_hi in spans:
            words = seg.split()
            if not words and seg:
                words = [seg]
            for word in words:
                if not append_word(word, is_hi):
                    return lines[:max_lines]
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
        x0, y0, x1, y1 = box
        max_w = x1 - x0 - 40
        fsize = getattr(font, "size", 22)
        line_h = max(fsize + 4, int(30 * self.canvas_height / 1920))
        max_lines = max(1, (y1 - y0 - 8) // line_h)

        spans = self._parse_highlight_spans(text, highlight_phrases)
        word_lines = self._flow_words_to_lines(draw, spans, font, max_w, max_lines)

        y = y0 + 2
        for word_line in word_lines:
            if y + line_h > y1:
                break
            x = x0 + 20
            for i, (word, is_hi) in enumerate(word_line):
                chunk = (" " if i > 0 else "") + word
                color = highlight_color if is_hi else default_color
                draw.text((x, y), chunk, font=font, fill=color)
                x += self._text_width(draw, chunk, font)
            y += line_h

    def _split_line_by_highlights(self, line: str, highlight_phrases: list[str]) -> list[tuple[str, bool]]:
        if not highlight_phrases or not line:
            return [(line, False)]
        work = line
        segments: list[tuple[str, bool]] = []
        while work:
            best = None
            for hp in highlight_phrases:
                hp_core = hp.upper().strip('"').strip("'").rstrip("!")
                idx = work.upper().find(hp_core)
                if idx != -1 and (best is None or idx < best[0]):
                    best = (idx, idx + len(hp_core))
            if best is None:
                segments.append((work, False))
                break
            idx, end = best
            if idx > 0:
                segments.append((work[:idx], False))
            segments.append((work[idx:end], True))
            work = work[end:]
        return segments

    def _scale_box(self, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        """Escala coordenadas de layout desenhadas para 1080x1920."""
        ref_w, ref_h = 1080, 1920
        x0, y0, x1, y1 = box
        sx = self.canvas_width / ref_w
        sy = self.canvas_height / ref_h
        return (
            int(x0 * sx), int(y0 * sy),
            int(x1 * sx), int(y1 * sy),
        )

    def _scaled_font_size(self, base_size: int, min_size: int = 14) -> int:
        """Escala tamanho de fonte proporcionalmente ao canvas (referência 1920px de altura)."""
        return max(min_size, int(base_size * self.canvas_height / 1920))

    def _card_layout(self) -> tuple:
        """Retorna (alerta_box, solucao_box, cta_box) ajustadas ao canvas atual.
        Em canvas 1:1 (imagem estática) os cards ficam nos últimos 28% da imagem."""
        is_square = self.canvas_height <= self.canvas_width * 1.15
        if is_square:
            # 1:1 — inicia em 72% (y=1382/1920) deixando 72% superior livre para a foto
            boxes = (
                self._scale_box((36, 1382, 1044, 1520)),
                self._scale_box((36, 1532, 1044, 1655)),
                self._scale_box((36, 1663, 1044, 1760)),
            )
        else:
            # 9:16 — posição original
            boxes = (
                self._scale_box((36, 1050, 1044, 1240)),
                self._scale_box((36, 1260, 1044, 1440)),
                self._scale_box((36, 1470, 1044, 1600)),
            )
        print(
            f"[Layout] canvas={self.canvas_width}x{self.canvas_height} "
            f"is_square={is_square} "
            f"alerta_y={boxes[0][1]}-{boxes[0][3]} "
            f"solucao_y={boxes[1][1]}-{boxes[1][3]} "
            f"cta_y={boxes[2][1]}-{boxes[2][3]}"
        )
        return boxes

    def _draw_headline_branded(
        self, draw: ImageDraw.ImageDraw, headline: str, highlight_phrases: list[str]
    ):
        font_size = self._scaled_font_size(42, min_size=28)
        font = self._load_font(font_size, bold=True)
        max_w = self.canvas_width - 100
        lines = self._wrap_text(draw, headline.upper(), font, max_w, max_lines=3)
        y = int(56 * self.canvas_height / 1920)
        line_h = max(font_size + 8, int(50 * self.canvas_height / 1920))
        center_x = self.canvas_width // 2
        for line in lines:
            segments = self._split_line_by_highlights(line, highlight_phrases)
            total_w = sum(self._text_width(draw, seg, font) for seg, _ in segments)
            x = center_x - total_w // 2
            for seg, is_hi in segments:
                color = self.BRAND_GREEN if is_hi else self.BRAND_TEXT
                self._draw_text_with_shadow(draw, (x, y), seg, font, color)
                x += self._text_width(draw, seg, font)
            y += line_h

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
        font_title_size = self._scaled_font_size(20, min_size=13)
        font_body_size = self._scaled_font_size(self.card_body_font_size, min_size=13)
        font_title = self._load_font(font_title_size, bold=True)
        font_body = self._load_font(font_body_size, bold=True)
        title_y_offset = max(10, int(14 * self.canvas_height / 1920))
        body_y_offset = max(30, int(46 * self.canvas_height / 1920))
        line_h = max(font_body_size + 4, int(30 * self.canvas_height / 1920))
        draw.text((x0 + 20, y0 + title_y_offset), title, font=font_title, fill=title_color)
        body_box = (x0, y0 + body_y_offset, x1, y1 - 8)
        max_body_lines = max(2, (body_box[3] - body_box[1]) // line_h)
        if highlight_phrases:
            self._draw_rich_text_block(
                draw, body_box, body, font_body, body_color,
                highlight_phrases, highlight_color or self.BRAND_HIGHLIGHT,
            )
        else:
            lines = self._wrap_text(draw, body, font_body, (x1 - x0) - 40, max_lines=max_body_lines)
            y = y0 + body_y_offset + 2
            for line in lines:
                if y + line_h > body_box[3]:
                    break
                draw.text((x0 + 20, y), line, font=font_body, fill=body_color)
                y += line_h

    def _draw_cta_button(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], main_text: str, url: str):
        draw.rounded_rectangle(box, radius=36, fill=self.BRAND_GREEN, outline=self.BRAND_GREEN_DARK, width=3)
        font_main_size = self._scaled_font_size(24, min_size=16)
        font_url_size = self._scaled_font_size(18, min_size=12)
        font_main = self._load_font(font_main_size, bold=True)
        font_url = self._load_font(font_url_size, bold=True)
        cta_line_h = font_main_size + 6
        lines = self._wrap_text(draw, main_text.upper(), font_main, box[2] - box[0] - 40, max_lines=2)
        y = box[1] + max(12, int(18 * self.canvas_height / 1920))
        for line in lines:
            x = (box[0] + box[2]) // 2 - self._text_width(draw, line, font_main) // 2
            draw.text((x, y), line, font=font_main, fill=self.BRAND_CTA_TEXT)
            y += cta_line_h
        url_clean = url.replace("https://", "").replace("http://", "")
        url_y = box[3] - font_url_size - max(8, int(12 * self.canvas_height / 1920))
        xu = (box[0] + box[2]) // 2 - self._text_width(draw, url_clean, font_url) // 2
        draw.text((xu, url_y), url_clean, font=font_url, fill=self.BRAND_CTA_TEXT)

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
        img = img.resize((self.canvas_width, self.canvas_height), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(img)
        highlights = frases_destaque or []

        self._draw_headline_branded(draw, headline, highlights)
        alerta_box, solucao_box, cta_box = self._card_layout()

        self._draw_brand_card(
            draw, alerta_box,
            "MENSAGEM SUSPEITA NO WHATSAPP",
            alerta,
            self.WHATSAPP_GREEN, self.BRAND_TEXT,
            highlight_phrases=highlights, highlight_color=self.BRAND_HIGHLIGHT,
        )
        self._draw_brand_card(
            draw, solucao_box,
            "GUARDIAN AI — PROTECAO WHATSAPP",
            solucao,
            self.BRAND_GREEN, self.BRAND_TEXT,
        )
        self._draw_cta_button(draw, cta_box, cta, url)

        img.save(out_path, "JPEG", quality=95)

    def _compose_overlay_png(
        self,
        out_path: str,
        headline: str,
        alerta: str,
        solucao: str,
        cta: str,
        url: str,
        frases_destaque: list[str] | None = None,
    ):
        """Camada PNG transparente (cards/headline) — aplicada uma vez sobre o vídeo Kling."""
        img = Image.new("RGBA", (self.canvas_width, self.canvas_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        highlights = frases_destaque or []

        self._draw_headline_branded(draw, headline, highlights)
        alerta_box, solucao_box, cta_box = self._card_layout()

        self._draw_brand_card(
            draw, alerta_box,
            "MENSAGEM SUSPEITA NO WHATSAPP",
            alerta,
            self.WHATSAPP_GREEN, self.BRAND_TEXT,
            highlight_phrases=highlights, highlight_color=self.BRAND_HIGHLIGHT,
        )
        self._draw_brand_card(
            draw, solucao_box,
            "GUARDIAN AI — PROTECAO WHATSAPP",
            solucao,
            self.BRAND_GREEN, self.BRAND_TEXT,
        )
        self._draw_cta_button(draw, cta_box, cta, url)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        img.save(out_path, "PNG")

    def _compile_kling_native(
        self,
        kling_raw: str,
        overlay_png: str,
        audio_path: str,
        output_path: str,
        boom_path: str,
    ) -> bool:
        duration = self._get_audio_duration(audio_path)
        slowdown = float(self.preset_midia.get("video_slowdown", 1.35))
        return compile_kling_pipeline(
            kling_raw, overlay_png, audio_path, output_path, boom_path,
            self.canvas_width, self.canvas_height, duration, slowdown=slowdown,
        )

    def _warn_narration_duration(self, audio_path: str) -> None:
        preset = self.preset_midia or {}
        target = preset.get("target_narration_seconds")
        if not target:
            return
        dur = self._get_audio_duration(audio_path)
        if dur > float(target) + 3:
            print(
                f"⚠️ Narração {dur:.0f}s — acima do alvo {target}s para "
                f"{preset.get('label', 'canal')}. Prefira copy mais curta na Etapa 4."
            )

    def _compile_legacy_frames(self, audio_path: str, output_path: str) -> bool:
        """Fallback: pipeline antigo JPEG + ping-pong se FFmpeg nativo falhar."""
        frames = sorted(f for f in os.listdir(self.frames_finais_dir) if f.endswith(".jpg"))
        if not frames:
            return False
        self._compile_processed_video(audio_path, output_path)
        return os.path.isfile(output_path)

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
        preset = creative_data.get("preset_midia") or {}
        ratio_hint = preset.get("visual_ratio_hint")
        if ratio_hint:
            partes.append(ratio_hint)
        else:
            partes.append(
                "Vertical 9:16 composition, all subjects fully visible without crop, "
                "clean image with no text overlays (text added later in post-production)."
            )
        vid = creative_data.get("visual_variation_id")
        if vid:
            partes.append(
                f"MANDATORY UNIQUENESS: Campaign visual {vid}. "
                "Distinct individual face, outfit and room — never repeat generic stock look."
            )
        if "Vídeo" in creative_data.get("tipo_midia_selecionada", ""):
            partes.append(motion_prompt_suffix())
        return " ".join(partes)

    def _slug_filename(self, text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", text.lower().strip())
        return slug.strip("_") or "geral"

    def _resolve_midia_slug(self, creative_data: dict) -> str:
        formato = creative_data.get("tipo_midia_selecionada", "")
        if "Vídeo" in formato or "video" in formato.lower():
            return "video"
        return "imagem"

    def _allocate_campaign_seq(self, publico: str, midia: str, date_str: str) -> int:
        pattern = re.compile(
            rf"^(\d+)_{re.escape(publico)}_{re.escape(midia)}_{re.escape(date_str)}(?:_|\.|$)"
        )
        max_seq = 0
        if os.path.isdir(self.output_dir):
            for fname in os.listdir(self.output_dir):
                if fname.startswith("_"):
                    continue
                match = pattern.match(fname)
                if match:
                    max_seq = max(max_seq, int(match.group(1)))
        return max_seq + 1

    def _resolve_output_names(self, creative_data: dict) -> dict:
        publico = self._slug_filename(
            creative_data.get("publico_slug") or creative_data.get("publico_id") or "geral"
        )
        midia = self._resolve_midia_slug(creative_data)
        date_str = datetime.now().strftime("%Y-%m-%d")
        seq = self._allocate_campaign_seq(publico, midia, date_str)
        basename = f"{seq}_{publico}_{midia}_{date_str}"
        os.makedirs(self.work_dir, exist_ok=True)
        return {
            "basename": basename,
            "seq": seq,
            "publico": publico,
            "midia": midia,
            "date": date_str,
            "video": os.path.join(self.output_dir, f"{basename}.mp4"),
            "final_image": os.path.join(self.output_dir, f"{basename}.jpg"),
            "base_image": os.path.join(self.output_dir, f"{basename}_base.jpg"),
            "audio": os.path.join(self.output_dir, f"{basename}.mp3"),
            "voice_raw": os.path.join(self.work_dir, f"{basename}_voz.mp3"),
            "kling_raw": os.path.join(self.work_dir, f"{basename}_kling_raw.mp4"),
            "overlay_png": os.path.join(self.work_dir, f"{basename}_overlay.png"),
            "boomerang": os.path.join(self.work_dir, f"{basename}_boomerang.mp4"),
        }

    def _audio_ok(self, path: str, min_bytes: int = 5000) -> bool:
        return os.path.isfile(path) and os.path.getsize(path) >= min_bytes

    def _overlay_from_creative(self, creative_data: dict) -> dict:
        frases: list[str] = []
        if creative_data.get("frase_destaque_golpista"):
            frases.append(creative_data["frase_destaque_golpista"])
        frases.extend(creative_data.get("frases_destaque_extra", []))
        return {
            "headline": creative_data.get("gancho_atencao_inicial", ""),
            "alerta": creative_data.get("texto_card_notificacao", ""),
            "solucao": card_solucao_text(),
            "cta": resolve_overlay_cta(creative_data),
            "url": creative_data.get("link_conversao", self.url_conversao),
            "frases_destaque": frases,
        }

    def reapply_overlay_only(self, creative_data: dict, prior_assets: dict) -> dict:
        """Recompõe cards/overlay mantendo áudio e mídia base — para correções de layout."""
        print(f"\n🔄 [Fábrica v{MEDIA_FACTORY_VERSION}] Recompondo overlay (layout — sem regerar copy/áudio/Kling)...")

        self.card_body_font_size = int(creative_data.get("overlay_card_font_size", 20))
        self.preset_midia = creative_data.get("preset_midia") or resolve_channel_preset(
            creative_data.get("canal_veiculacao_selecionado", ""),
            creative_data.get("tipo_midia_selecionada", ""),
        )
        self.canvas_width = int(self.preset_midia.get("width", 1080))
        self.canvas_height = int(self.preset_midia.get("height", 1920))
        ov = self._overlay_from_creative(creative_data)

        audio_path = prior_assets.get("audio_file", "")
        video_path = prior_assets.get("commercial_video_file", "")
        final_image = prior_assets.get("static_image_file", "")
        kling_raw = prior_assets.get("kling_raw_file", "")
        base_image = prior_assets.get("base_image_file", "")

        if isinstance(final_image, str) and final_image in ("N/A", "Não solicitada", "Não solicitado"):
            final_image = ""
        if isinstance(base_image, str) and base_image in ("N/A", "Não solicitada", "Não solicitado"):
            base_image = ""

        os.makedirs(self.frames_finais_dir, exist_ok=True)

        recomposed = False
        overlay_png = os.path.join(self.work_dir, f"{prior_assets.get('basename', 'camp')}_overlay.png")
        self._compose_overlay_png(
            overlay_png, ov["headline"], ov["alerta"], ov["solucao"], ov["cta"], ov["url"], ov["frases_destaque"],
        )

        if kling_raw and os.path.isfile(kling_raw):
            print(f"🎞️ Recompondo via FFmpeg nativo: {os.path.basename(kling_raw)}")
            boom_path = os.path.join(self.work_dir, f"{prior_assets.get('basename', 'camp')}_boomerang.mp4")
            if self._audio_ok(audio_path) and video_path:
                recomposed = self._compile_kling_native(kling_raw, overlay_png, audio_path, video_path, boom_path)
            if not recomposed:
                print("⚠️ FFmpeg nativo falhou — tentando fallback JPEG...")
                self._extract_frames(kling_raw)
                recomposed = self._compose_all_frames(
                    ov["headline"], ov["alerta"], ov["solucao"], ov["cta"], ov["url"], ov["frases_destaque"],
                )
                if recomposed and self._audio_ok(audio_path) and video_path:
                    self._compile_legacy_frames(audio_path, video_path)
        elif base_image and os.path.isfile(base_image):
            print(f"🖼️ Reutilizando imagem base: {os.path.basename(base_image)}")
            if self._audio_ok(audio_path) and video_path and os.path.isfile(base_image):
                duration = self._get_audio_duration(audio_path)
                zoom = still_video_zoom_filter(self.canvas_width, self.canvas_height, int(duration * 25), 25)
                recomposed = compose_still_with_overlay(
                    base_image, overlay_png, audio_path, video_path,
                    duration, self.canvas_width, self.canvas_height, zoom,
                )
            out_img = final_image or base_image.replace("_base.", ".")
            self._apply_pillow_layout(
                base_image, out_img,
                ov["headline"], ov["alerta"], ov["solucao"], ov["cta"], ov["url"], ov["frases_destaque"],
            )
            recomposed = recomposed or os.path.isfile(out_img)
            final_image = out_img
        else:
            bruts = [f for f in os.listdir(self.frames_brutos_dir) if f.endswith(".jpg")]
            if bruts:
                print(f"🎞️ Reutilizando {len(bruts)} frames em cache...")
                recomposed = self._compose_all_frames(
                    ov["headline"], ov["alerta"], ov["solucao"], ov["cta"], ov["url"], ov["frases_destaque"],
                )
                if recomposed and self._audio_ok(audio_path) and video_path:
                    self._compile_processed_video(audio_path, video_path, keep_frames=True)

        if not recomposed:
            print("⚠️ Não foi possível recompor — será necessário regerar mídia completa.")
            return prior_assets

        print("✅ Overlay recomposto com quebra de texto nos cards.")
        return {
            **prior_assets,
            "static_image_file": final_image or prior_assets.get("static_image_file"),
            "commercial_video_file": video_path if os.path.isfile(str(video_path)) else prior_assets.get("commercial_video_file"),
            "recomposed": True,
        }

    def _build_narration_for_tts(self, creative_data: dict) -> str:
        script = build_narration_script(
            creative_data.get("gancho_atencao_inicial", ""),
            creative_data.get("desenvolvimento_copy", ""),
            self._trim_narration_for_preset,
            self.preset_midia or {},
        )
        print(f"🔊 Fechamento narração: {NARRATION_CLOSING}")
        return script

    def _regenerate_audio_and_remux(self, creative_data: dict, prior_assets: dict) -> str:
        """Gera nova narração e retorna path do áudio mixado."""
        basename = prior_assets.get("basename", "campanha")
        canal = creative_data.get("canal_veiculacao_selecionado", "Meta Ads (Instagram/Facebook)")
        voice_raw = os.path.join(self.work_dir, f"{basename}_voz.mp3")
        audio_out = prior_assets.get("audio_file") or os.path.join(self.output_dir, f"{basename}.mp3")

        texto_tts = self._build_narration_for_tts(creative_data)
        voz = self._generate_audio(texto_tts, voice_raw, self.preset_midia)
        if not self._audio_ok(voz):
            return ""
        voz = self._fit_narration_to_preset(voz, voice_raw)
        mixed = self._mix_background_track(voz, canal, audio_out, self.preset_midia)
        self._warn_narration_duration(mixed)
        return mixed if self._audio_ok(mixed) else ""

    def reapply_audio_only(self, creative_data: dict, prior_assets: dict) -> dict:
        """Regera só narração/áudio e remuxa vídeo — sem regerar copy Gemini/Kling."""
        print(f"\n🔊 [Fábrica v{MEDIA_FACTORY_VERSION}] Regerando narração (pronúncia/áudio)...")

        self.preset_midia = creative_data.get("preset_midia") or resolve_channel_preset(
            creative_data.get("canal_veiculacao_selecionado", ""),
            creative_data.get("tipo_midia_selecionada", ""),
        )
        self.canvas_width = int(self.preset_midia.get("width", 1080))
        self.canvas_height = int(self.preset_midia.get("height", 1920))

        audio_path = self._regenerate_audio_and_remux(creative_data, prior_assets)
        if not audio_path:
            print("⚠️ Falha ao regerar áudio.")
            return prior_assets

        video_path = prior_assets.get("commercial_video_file", "")
        kling_raw = prior_assets.get("kling_raw_file", "")
        base_image = prior_assets.get("base_image_file", "")
        basename = prior_assets.get("basename", "campanha")
        overlay_png = os.path.join(self.work_dir, f"{basename}_overlay.png")
        boom_path = os.path.join(self.work_dir, f"{basename}_boomerang.mp4")

        remuxed = False
        if kling_raw and os.path.isfile(kling_raw) and os.path.isfile(overlay_png):
            remuxed = self._compile_kling_native(kling_raw, overlay_png, audio_path, video_path, boom_path)
        elif base_image and os.path.isfile(base_image) and os.path.isfile(overlay_png):
            duration = self._get_audio_duration(audio_path)
            zoom = still_video_zoom_filter(self.canvas_width, self.canvas_height, int(duration * 25), 25)
            remuxed = compose_still_with_overlay(
                base_image, overlay_png, audio_path, video_path,
                duration, self.canvas_width, self.canvas_height, zoom,
            )
        elif video_path and os.path.isfile(str(video_path)):
            print("⚠️ Remux parcial — áudio atualizado; vídeo pode precisar regerar mídia completa.")

        print("✅ Narração regerada com soletração correta do site.")
        return {
            **prior_assets,
            "audio_file": audio_path,
            "commercial_video_file": video_path if remuxed or os.path.isfile(str(video_path)) else prior_assets.get("commercial_video_file"),
            "audio_regenerated": True,
        }

    def generate_campaign_assets(self, creative_data: dict) -> dict:
        self.card_body_font_size = int(creative_data.get("overlay_card_font_size", 22))
        self.preset_midia = creative_data.get("preset_midia") or resolve_channel_preset(
            creative_data.get("canal_veiculacao_selecionado", ""),
            creative_data.get("tipo_midia_selecionada", ""),
        )
        self.canvas_width = int(self.preset_midia.get("width", 1080))
        self.canvas_height = int(self.preset_midia.get("height", 1920))

        print(f"\n🏭 [Fábrica de Mídia v{MEDIA_FACTORY_VERSION}] Compositor FFmpeg nativo + Pillow...")
        print(f"📁 Diretório de saída: {self.output_dir}")
        print(f"🎨 Modelo de imagem: {self.model_imagem}")
        print(f"📐 Preset ativo: {format_preset_summary(self.preset_midia)}")

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.work_dir, exist_ok=True)
        os.makedirs(self.frames_brutos_dir, exist_ok=True)
        os.makedirs(self.frames_finais_dir, exist_ok=True)

        names = self._resolve_output_names(creative_data)
        print(
            f"📛 Arquivos: {names['basename']} "
            f"(#{names['seq']} | {names['publico']} | {names['midia']} | {names['date']})"
        )

        formato_midia = creative_data.get("tipo_midia_selecionada", "Vídeo Vertical Reels (1080x1920)")
        canal_veiculacao = creative_data.get("canal_veiculacao_selecionado", "Meta Ads (Instagram/Facebook)")

        texto_audio_tts = self._build_narration_for_tts(creative_data)
        voz_pura_path = self._generate_audio(texto_audio_tts, names["voice_raw"], self.preset_midia)
        if not self._audio_ok(voz_pura_path):
            print("❌ CRÍTICO: Narração não gerada — verifique ELEVENLABS_API_KEY e créditos.")
        voz_pura_path = self._fit_narration_to_preset(voz_pura_path, names["voice_raw"])
        audio_final_path = self._mix_background_track(
            voz_pura_path, canal_veiculacao, names["audio"], self.preset_midia,
        )
        self._warn_narration_duration(audio_final_path)

        alerta_texto = creative_data.get("texto_card_notificacao", "")
        solucao_texto = card_solucao_text()
        creative_data["texto_card_solucao"] = solucao_texto
        cta_texto = resolve_overlay_cta(creative_data)
        url_conversao = creative_data.get("link_conversao", self.url_conversao)
        headline = creative_data.get("gancho_atencao_inicial", "")
        frases_destaque: list[str] = []
        if creative_data.get("frase_destaque_golpista"):
            frases_destaque.append(creative_data["frase_destaque_golpista"])
        frases_destaque.extend(creative_data.get("frases_destaque_extra", []))

        print(f"📝 Card golpe: {alerta_texto[:80]}...")
        print(f"🛡️ Card solução: {solucao_texto[:80]}...")
        print(f"🔗 Link: {url_conversao}")

        base_image_path = names["base_image"]
        final_design_path = names["final_image"]
        video_output_path = names["video"]

        publicidade_prompt = self._build_visual_prompt(creative_data)
        overlay_png = names["overlay_png"]
        self._compose_overlay_png(
            overlay_png,
            headline, alerta_texto, solucao_texto, cta_texto, url_conversao, frases_destaque,
        )

        if "Vídeo" in formato_midia:
            print("🎬 Solicitando clipe Kling AI...")
            video_bruto_path = (
                self._generate_kling_video(publicidade_prompt, names["kling_raw"])
                if (self.kling_key or os.getenv("KLING_ACCESS_KEY"))
                else ""
            )

            if video_bruto_path and os.path.exists(video_bruto_path):
                native_ok = False
                if self._audio_ok(audio_final_path):
                    native_ok = self._compile_kling_native(
                        video_bruto_path, overlay_png, audio_final_path,
                        video_output_path, names["boomerang"],
                    )
                if native_ok:
                    print("✅ Vídeo Kling + overlay (movimento nativo preservado).")
                    self._apply_pillow_layout(
                        self._extract_poster_frame(video_bruto_path, names["base_image"]),
                        final_design_path,
                        headline, alerta_texto, solucao_texto, cta_texto, url_conversao, frases_destaque,
                    )
                else:
                    print("⚠️ Pipeline FFmpeg nativo falhou — fallback JPEG ping-pong...")
                    self._extract_frames(video_bruto_path)
                    overlay_ok = self._compose_all_frames(
                        headline, alerta_texto, solucao_texto, cta_texto, url_conversao, frases_destaque,
                    )
                    if overlay_ok and self._audio_ok(audio_final_path):
                        self._compile_legacy_frames(audio_final_path, video_output_path)
                    else:
                        print("❌ Vídeo NÃO gerado — overlay ou áudio inválido.")
            else:
                print("⚠️ Fallback: Kling indisponível — gerando vídeo com imagem estática + overlay Guardian...")
                self._generate_gemini_image(
                    publicidade_prompt, base_image_path,
                    creative_data=creative_data, basename=names["basename"],
                )
                if self._audio_ok(audio_final_path):
                    duration = self._get_audio_duration(audio_final_path)
                    zoom = still_video_zoom_filter(self.canvas_width, self.canvas_height, int(duration * 25), 25)
                    still_ok = compose_still_with_overlay(
                        base_image_path, overlay_png, audio_final_path, video_output_path,
                        duration, self.canvas_width, self.canvas_height, zoom,
                    )
                    if not still_ok:
                        self._apply_pillow_layout(
                            base_image_path, final_design_path,
                            headline, alerta_texto, solucao_texto, cta_texto, url_conversao, frases_destaque,
                        )
                        self._compile_still_video(final_design_path, audio_final_path, video_output_path)
                self._apply_pillow_layout(
                    base_image_path, final_design_path,
                    headline, alerta_texto, solucao_texto, cta_texto, url_conversao, frases_destaque,
                )

            return {
                "basename": names["basename"],
                "audio_file": audio_final_path,
                "commercial_video_file": video_output_path if os.path.exists(video_output_path) else "FALHOU",
                "static_image_file": (
                    final_design_path if os.path.exists(final_design_path) else "Não solicitada"
                ),
                "kling_raw_file": video_bruto_path if video_bruto_path and os.path.exists(video_bruto_path) else "",
                "base_image_file": base_image_path if os.path.exists(base_image_path) else "",
            }

        print("🖼️ Fluxo de imagem estática...")
        self._generate_gemini_image(
            publicidade_prompt, base_image_path,
            creative_data=creative_data, basename=names["basename"],
        )
        self._apply_pillow_layout(
            base_image_path, final_design_path,
            headline, alerta_texto, solucao_texto, cta_texto, url_conversao, frases_destaque,
        )

        # Combina imagem base (sem overlay baked) + overlay_png + áudio em MP4 para veiculação
        # ATENÇÃO: usa base_image_path para evitar texto duplicado (overlay_png já tem os cards)
        video_output_path = names["video"]
        video_ok = False
        if self._audio_ok(audio_final_path) and os.path.exists(base_image_path):
            duration = self._get_audio_duration(audio_final_path)
            zoom = still_video_zoom_filter(
                self.canvas_width, self.canvas_height, int(duration * 25), 25
            )
            video_ok = compose_still_with_overlay(
                base_image_path, overlay_png, audio_final_path,
                video_output_path, duration,
                self.canvas_width, self.canvas_height, zoom,
            )
            if video_ok:
                print("✅ MP4 estático gerado (imagem + áudio).")
            else:
                print("⚠️ FFmpeg falhou ao gerar MP4 estático.")

        return {
            "basename": names["basename"],
            "audio_file": audio_final_path,
            "static_image_file": final_design_path,
            "commercial_video_file": video_output_path if video_ok else "Não solicitado",
            "kling_raw_file": "",
            "base_image_file": base_image_path if os.path.exists(base_image_path) else "",
        }

    def _generate_kling_video(self, prompt: str, raw_output_path: str) -> str:
        if not self.kling_key and not os.getenv("KLING_ACCESS_KEY"):
            print("❌ Kling: KLING_API_KEY ausente no .env")
            return ""

        balance = fetch_resource_packages(days=30)
        if balance.get("ok"):
            remaining = balance.get("total_remaining", 0)
            if remaining <= 0 and not balance.get("pending_packs"):
                print(format_balance_report(balance))
                print("❌ Kling: saldo API zerado — usando fallback Gemini.")
                return ""
            if remaining > 0:
                print(f"💳 Kling API: ~{remaining:.1f} unidades disponíveis (pacotes online)")
        else:
            print(f"⚠️ Não foi possível consultar saldo Kling: {balance.get('message') or balance.get('error')}")

        headers = kling_headers()
        preset = self.preset_midia or {}
        kling_prompt = f"{prompt} {motion_prompt_suffix()}"
        payload = {
            "prompt": kling_prompt,
            "settings": {
                "duration": preset.get("kling_duration", 5),
                "resolution": preset.get("kling_resolution", "720p"),
                "aspect_ratio": preset.get("aspect_ratio", "9:16"),
            },
        }
        inicio = time.time()
        try:
            res = requests.post(
                f"{self.kling_base_url}/text-to-video/kling-3.0-turbo",
                headers=headers, json=payload, timeout=60,
            )
            if res.status_code != 200:
                parsed = parse_kling_response(res)
                print(f"❌ Kling HTTP {parsed['http_status']} | code={parsed.get('code')} | {parsed.get('message')}")
                if parsed.get("hint"):
                    print(f"   → {parsed['hint']}")
                extra = explain_balance_error(str(parsed.get("message", "")))
                if extra:
                    print(f"   → {extra}")
                return ""
            body = res.json()
            task_id = body.get("data", {}).get("id")
            if not task_id:
                print(f"❌ Kling sem task_id. Resposta: {str(body)[:300]}")
                return ""
            print("⏳ Renderizando na Kling AI (fila da nuvem — tempo varia)...")
            for tentativa in range(48):
                time.sleep(5)
                elapsed = int(time.time() - inicio)
                if tentativa % 2 == 0:
                    print(f"   ... {elapsed}s aguardando render Kling")
                status_res = requests.get(
                    f"{self.kling_base_url}/tasks?task_ids={task_id}",
                    headers=headers, timeout=30,
                )
                if status_res.status_code != 200:
                    parsed = parse_kling_response(status_res)
                    print(f"⚠️ Kling status HTTP {parsed['http_status']}: {parsed.get('message')}")
                    continue
                tasks = status_res.json().get("data", [])
                if not tasks:
                    continue
                task = tasks[0]
                status = task.get("status", "")
                if status == "succeeded":
                    video_url = task.get("outputs", [{}])[0].get("url")
                    if video_url:
                        os.makedirs(os.path.dirname(raw_output_path), exist_ok=True)
                        with open(raw_output_path, "wb") as f:
                            f.write(requests.get(video_url, timeout=120).content)
                        print(f"✅ Kling concluiu em {int(time.time() - inicio)}s")
                        return raw_output_path
                    print("❌ Kling succeeded mas sem URL de vídeo.")
                    return ""
                if status in ("failed", "cancelled"):
                    err_msg = task.get("message") or task.get("error") or str(task)
                    print(f"❌ Kling {status}: {err_msg}")
                    extra = explain_balance_error(str(err_msg))
                    if extra:
                        print(f"   → {extra}")
                    print("   → Rode: python3 kling_diagnostico.py  (para ver saldo real da API)")
                    return ""
            print(f"❌ Kling timeout após {int(time.time() - inicio)}s (fila cheia — usando fallback estático).")
        except Exception as e:
            print(f"❌ Erro Kling: {e}")
        return ""

    def _extract_poster_frame(self, video_path: str, output_path: str) -> str:
        """Extrai um frame do clipe Kling para thumbnail JPG (local, sem API)."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = [
            "ffmpeg", "-y", "-ss", "00:00:00.5", "-i", video_path,
            "-frames:v", "1", "-q:v", "2", output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.isfile(output_path):
            return output_path
        return video_path

    def _extract_frames(self, video_path: str):
        for f in os.listdir(self.frames_brutos_dir):
            if f.endswith(".jpg"):
                os.remove(os.path.join(self.frames_brutos_dir, f))
        cmd = [
            "ffmpeg", "-y", "-an", "-i", video_path,
            "-vf", "fps=12",
            "-q:v", "2", os.path.join(self.frames_brutos_dir, "frame_%04d.jpg"),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        count = len([f for f in os.listdir(self.frames_brutos_dir) if f.endswith(".jpg")])
        print(f"🎞️ {count} frames extraídos @12fps (movimento suavizado, áudio Kling descartado).")
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
        seed = hash(tuple(frames)) & 0xFFFFFFFF
        sequence = build_natural_frame_sequence(len(frames), needed, seed=seed)
        for i, frame_idx in enumerate(sequence):
            src_name = frames[frame_idx]
            shutil.copy2(
                os.path.join(self.frames_finais_dir, src_name),
                os.path.join(self.frames_loop_dir, f"frame_{i + 1:04d}.jpg"),
            )
        cycles = max(1, needed // max(len(frames) * 2, 1))
        print(f"🔄 Sequência ping-pong: {len(frames)} frames → {needed} (@{fps}fps, ~{cycles} ciclos suaves)")
        return needed

    def _compile_processed_video(self, audio_path: str, output_path: str, keep_frames: bool = False):
        frames = sorted(f for f in os.listdir(self.frames_finais_dir) if f.endswith(".jpg"))
        if not frames:
            print("❌ Sem frames finais.")
            return
        duration = self._get_audio_duration(audio_path)
        total = self._prepare_looped_frames(frames, duration)
        print(f"🎬 Compilando {total} frames ({duration:.1f}s) + narração [ping-pong]...")
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
        if not keep_frames:
            self._cleanup_frame_cache()

    def _cleanup_frame_cache(self):
        for pasta in (self.frames_brutos_dir, self.frames_finais_dir, self.frames_loop_dir):
            if not os.path.isdir(pasta):
                continue
            for arquivo in os.listdir(pasta):
                if arquivo.endswith(".jpg"):
                    os.remove(os.path.join(pasta, arquivo))

    def _extract_domain(self, url: str) -> str:
        domain = url.strip().lower()
        domain = re.sub(r"^https?://", "", domain)
        domain = re.sub(r"^www\.", "", domain)
        return domain.split("/")[0].split("?")[0]

    def _domain_to_spoken_pt(self, url_or_domain: str) -> str:
        domain = self._extract_domain(url_or_domain)
        falado = domain.replace("-", " traço ")
        if "." in falado:
            nome, tld = falado.rsplit(".", 1)
            falado = f"{nome} ponto {tld}"
        return falado

    def _prepare_narration_text_for_tts(self, text: str) -> str:
        """
        Converte endereços web para pronúncia em português na narração.
        Mantém 'Guardian AI' (marca do app) sem alteração — só URLs/domínios.
        """
        dominio = self._extract_domain(self.url_conversao)
        if not dominio:
            return text
        falado = self._domain_to_spoken_pt(dominio)
        dominio_re = re.escape(dominio).replace(r"\-", "[\\-.]")
        padroes = [
            rf"https?://(?:www\.)?{dominio_re}",
            rf"(?:www\.)?{dominio_re}",
        ]
        resultado = text
        for padrao in padroes:
            resultado = re.sub(padrao, falado, resultado, flags=re.IGNORECASE)
        return resultado

    def _trim_narration_for_preset(self, text: str, preset: dict | None) -> str:
        """Corta roteiro longo antes do TTS — evita vídeos de 27s+ no TikTok."""
        preset = preset or {}
        max_chars = preset.get("copy_max_chars")
        if not max_chars or len(text) <= int(max_chars):
            return text
        limite = int(max_chars)
        cortado = text[:limite].rsplit(" ", 1)[0].rstrip(".,; ")
        if not cortado.endswith("."):
            cortado += "."
        print(f"✂️ Roteiro encurtado: {len(text)} → {len(cortado)} chars (limite {limite} TikTok/Shorts)")
        return cortado

    def _fit_narration_to_preset(self, audio_path: str, base_path: str) -> str:
        """Acelera narração via FFmpeg (local) quando excede o alvo do canal — sem API extra."""
        preset = self.preset_midia or {}
        if not preset.get("auto_fit_narration") or not self._audio_ok(audio_path):
            return audio_path
        target = float(preset.get("target_narration_seconds") or 0)
        if target <= 0:
            return audio_path

        dur = self._get_audio_duration(audio_path)
        if dur <= target + 0.5:
            return audio_path

        factor = min(dur / target, float(preset.get("max_audio_speedup", 1.4)))
        if factor < 1.03:
            return audio_path

        out_path = base_path.replace("_voz.mp3", "_voz_fit.mp3")
        if out_path == base_path:
            out_path = audio_path.replace(".mp3", "_fit.mp3")

        atempo_filters: list[str] = []
        remaining = factor
        while remaining > 1.005:
            step = min(remaining, 1.35)
            atempo_filters.append(f"atempo={step:.4f}")
            remaining /= step
        filter_str = ",".join(atempo_filters)

        cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-filter:a", filter_str,
            "-c:a", "libmp3lame", "-b:a", "192k", out_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and self._audio_ok(out_path):
            new_dur = self._get_audio_duration(out_path)
            print(
                f"⚡ Narração acelerada {dur:.1f}s → {new_dur:.1f}s "
                f"(atempo total ~{factor:.2f}x | alvo TikTok {target:.0f}s)"
            )
            return out_path
        print(f"⚠️ Ajuste de velocidade falhou — usando narração original: {result.stderr[-120:]}")
        return audio_path

    def _generate_audio(self, text: str, output_path: str | None = None, preset: dict | None = None) -> str:
        path = output_path or os.path.join(self.work_dir, "voz_pura.mp3")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not self.elevenlabs_key:
            print("❌ Chave ElevenLabs ausente no .env. Use ELEVENLABS_API_KEY (ou ELEVEN_LABS_API_KEY).")
            return path
        preset = preset or self.preset_midia or {}
        speed = float(preset.get("eleven_speed", 1.0))
        stability = float(preset.get("eleven_stability", 0.4))
        style = float(preset.get("eleven_style", 0.45))
        print(f"🎙️ Gerando narração ({len(text)} chars, velocidade {speed}x)...")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": self.elevenlabs_key}
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": 0.9,
                "style": style,
                "speed": speed,
            },
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

    def _mix_background_track(
        self,
        voz_path: str,
        canal: str,
        output_path: str | None = None,
        preset: dict | None = None,
    ) -> str:
        mixed_path = output_path or os.path.join(self.output_dir, "anuncio_audio_final.mp3")
        os.makedirs(os.path.dirname(mixed_path), exist_ok=True)
        if not self._audio_ok(voz_path):
            print("❌ Sem narração válida — mixagem abortada.")
            return voz_path

        preset = preset or self.preset_midia or {}
        trilha_tipo = preset.get("trilha_tipo", "corporativo" if "Meta" in canal else "suspense")
        pasta_alvo = self.dir_corporativo if trilha_tipo == "corporativo" else self.dir_suspense
        trilhas = []
        if os.path.isdir(pasta_alvo):
            trilhas = [f for f in os.listdir(pasta_alvo) if f.lower().endswith(".mp3")]
        if not trilhas:
            print(f"⚠️ Sem trilha em {os.path.basename(pasta_alvo)}/ — usando só narração.")
            return voz_path

        trilha_path = os.path.join(pasta_alvo, random.choice(trilhas))
        voice_vol = preset.get("voice_volume", "1.5")
        track_db = preset.get("track_volume_db", "-6dB")
        track_weight = preset.get("track_weight", "0.45")
        print(
            f"🎵 Mix ({trilha_tipo}): narração + {os.path.basename(trilha_path)} "
            f"[voz {voice_vol}x | trilha {track_db}]..."
        )
        cmd = [
            "ffmpeg", "-y", "-i", voz_path, "-stream_loop", "-1", "-i", trilha_path,
            "-filter_complex",
            f"[0:a]volume={voice_vol},highpass=f=80[voz];"
            f"[1:a]volume={track_db}[trilha];"
            f"[voz][trilha]amix=inputs=2:duration=first:dropout_transition=2:weights=1 {track_weight}[a]",
            "-map", "[a]", "-c:a", "libmp3lame", "-b:a", "192k", mixed_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and self._audio_ok(mixed_path):
            print(f"✅ Áudio mixado: {mixed_path}")
            return mixed_path
        print(f"⚠️ Mix falhou, usando narração pura: {result.stderr[-200:]}")
        return voz_path

    def _generate_gemini_image(
        self,
        prompt: str,
        output_path: str,
        creative_data: dict | None = None,
        basename: str = "",
    ):
        if os.path.isfile(output_path):
            os.remove(output_path)

        full_prompt = prompt
        retry_suffixes = [
            "",
            " Alternative composition: different person (age, gender, hair, clothes), different camera angle.",
            " Second attempt: new unique face, new background layout, new color palette — avoid kitchen cliché.",
        ]

        print(f"🎨 Gerando imagem ({self.model_imagem})...")
        for attempt, suffix in enumerate(retry_suffixes[:2]):
            attempt_prompt = full_prompt + suffix
            if attempt > 0:
                print(f"🔁 Tentativa {attempt + 1} com prompt alternativo (diversidade visual)...")
            try:
                response = self.client.models.generate_content(
                    model=self.model_imagem,
                    contents=attempt_prompt,
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
                )
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        with open(output_path, "wb") as f:
                            f.write(part.inline_data.data)
                        print(f"✅ Imagem: {output_path}")
                        self.visual_variety.register_generated(attempt_prompt, basename)
                        return
            except Exception as e:
                print(f"❌ Imagem falhou (tentativa {attempt + 1}): {e}")

        print("❌ Não foi possível gerar imagem após tentativas.")

    def _compile_still_video(self, image_path: str, audio_path: str, output_video_path: str):
        duration = self._get_audio_duration(audio_path)
        fps = 25
        total_frames = max(int(duration * fps), fps * 3)
        w, h = self.canvas_width, self.canvas_height
        zoom_filter = still_video_zoom_filter(w, h, total_frames, fps)
        print(f"🎬 Vídeo still com movimento orgânico ({w}x{h}, {duration:.1f}s)...")
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", image_path, "-i", audio_path,
            "-map", "0:v:0", "-map", "1:a:0",
            "-vf", zoom_filter,
            "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-t", f"{duration:.2f}",
            output_video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Vídeo estático: {output_video_path}")
        else:
            print(f"❌ Vídeo estático falhou: {result.stderr[-300:]}")
