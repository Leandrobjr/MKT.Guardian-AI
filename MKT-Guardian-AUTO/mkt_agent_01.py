import os
import time
import requests
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

class MediaFactory:
    def __init__(self):
        load_dotenv()
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY não encontrada. Crie o arquivo .env na raiz do projeto "
                "com base no .env.example e informe a chave de um projeto com billing ativo."
            )
        self.client = genai.Client(api_key=api_key)
        
        # Amarração estrita do modelo de texto atualizado da família 3.1
        self.model_name = "gemini-3.1-flash-lite"
        
        self.elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
        self.runway_key = os.environ.get("RUNWAY_API_KEY")
        self.voice_id = "21m00Tcm4TlvDq8ikWAM"
        
        # Garante a existência da tipografia profissional Montserrat localmente
        self.font_path = "Montserrat-Bold.ttf"
        self._download_professional_font()

    def _download_professional_font(self):
        """Baixa a fonte Montserrat do Google Fonts se ela não existir localmente."""
        if not os.path.exists(self.font_path):
            print("📥 [Pillow System] Baixando fonte Montserrat-Bold para design profissional...")
            url = "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Bold.ttf"
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    with open(self.font_path, "wb") as f:
                        f.write(response.content)
                    print("✅ Fonte Montserrat carregada com sucesso.")
            except Exception as e:
                print(f"⚠️ Falha ao baixar fonte. Usando fallback padrão: {e}")

    def generate_campaign_assets(self, creative_data: dict) -> dict:
        print("\n🏭 [Fábrica de Mídia v2.7] Gerando Assets com Engine Multimodal 3.1...")
        os.makedirs("output_campanha", exist_ok=True)
        
        texto_audio = f"{creative_data['gancho_atencao_inicial']}. {creative_data['desenvolvimento_copy']}"
        texto_cta = creative_data['chamada_para_acao_cta']
        
        audio_path = self._generate_audio(texto_audio)
        
        print("🎨 [Designer AI Sênior] Estruturando prompt de arte fotorrealista...")
        image_prompt = self._create_image_prompt(texto_audio, texto_cta)
        base_image_path = "output_campanha/anuncio_base.jpg"
        
        # Executa o motor multimodal de imagem resiliente contra o erro 429
        self._generate_gemini_image(image_prompt, base_image_path)
        
        print("📐 [Pillow Grid Engine] Executando alinhamento e tipografia premium...")
        final_design_path = "output_campanha/anuncio_final_design.jpg"
        self._apply_pillow_overlay(base_image_path, final_design_path, texto_cta)
        
        video_path = "output_campanha/anuncio_video_mock.mp4"
        
        return {
            "audio_file": audio_path,
            "static_image_file": final_design_path,
            "commercial_video_file": video_path,
            "designer_prompt": image_prompt
        }

    def _generate_audio(self, text: str) -> str:
        if not self.elevenlabs_key:
            return "output_campanha/anuncio_audio_mock.mp3"
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
        instruction = (
            "You are an Elite Creative Art Director. Translate the ad theme into an advanced image generation prompt. "
            "CRITICAL RULES:\n"
            "- Write the prompt strictly in ENGLISH.\n"
            "- Use cinematic style, realistic details, high contrast, commercial advertising photograph look, dramatic chiaroscuro lighting, sharp focus, 8k resolution, photorealistic textures.\n"
            "- Avoid any text, letters, logos, or words inside the image itself.\n"
            "- Return ONLY the clean prompt text. Do not write intros or explanations."
        )
        
        for tentativa in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[f"{instruction}\n\nAd Context: {copy_text} | Focus: {cta_text}"]
                )
                return response.text.strip()
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait = 15 * (tentativa + 1)
                    print(f"⚠️ [Prompt] Rate limit (429). Tentativa {tentativa + 1}/3. Aguardando {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"❌ [Prompt] Erro não recuperável: {e}")
                    break
        return "A close-up cinematic photograph of a smartphone showing a digital security protection shield interface, high contrast, photo realistic, 8k."

    def _generate_gemini_image(self, prompt: str, output_path: str):
        print(f"🤖 [Gemini Image Engine] Solicitando imagem via gemini-3.1-flash-image...")
        
        for tentativa in range(4):
            try:
                response = self.client.models.generate_content(
                    model="gemini-3.1-flash-image",
                    contents=[
                        f"Generate a high-quality promotional image. "
                        f"No text, letters or typography inside the image. "
                        f"Description: {prompt}"
                    ]
                )
                
                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        img = part.as_image()
                        img.save(output_path)
                        print(f"✅ Imagem salva em: {output_path}")
                        return

                raise ValueError(
                    "Nenhum dado de imagem retornado pela API. "
                    "Verifique se o projeto tem billing ativo e acesso ao modelo gemini-3.1-flash-image."
                )

            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
                is_permission  = "403" in err_str or "PERMISSION_DENIED" in err_str or "billing" in err_str.lower()

                if is_permission:
                    print(
                        f"🚫 [Permissão negada] A chave API não tem acesso ao modelo de imagem.\n"
                        f"   Causa provável: projeto sem billing ativo ou sem acesso ao gemini-3.1-flash-image.\n"
                        f"   Detalhe: {e}"
                    )
                    break

                if is_rate_limit:
                    wait = 30 * (tentativa + 1)
                    print(f"⚠️ [Rate Limit 429] Tentativa {tentativa + 1}/4. Aguardando {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"❌ [Imagem] Erro não recuperável na tentativa {tentativa + 1}: {e}")
                    break

        print("⚠️ Falha na geração de imagem. Usando placeholder.")
        Image.new('RGB', (1080, 1080), color=(15, 23, 42)).save(output_path)

    def _apply_pillow_overlay(self, input_path: str, output_path: str, text: str):
        try:
            img = Image.open(input_path).convert("RGBA")
            txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)
            w, h = img.size
            
            font_size = int(h * 0.04)
            if os.path.exists(self.font_path):
                font = ImageFont.truetype(self.font_path, font_size)
            else:
                font = ImageFont.load_default()
            
            # Algoritmo de Quebra Automática de Linha (Word Wrap)
            palavras = text.split(' ')
            linhas = []
            linha_atual = ""
            largura_maxima = int(w * 0.9)
            
            for palavra in palavras:
                test_linha = f"{linha_atual} {palavra}".strip()
                bbox = draw.textbbox((0, 0), test_linha, font=font)
                test_w = bbox[2] - bbox[0]
                
                if test_w <= largura_maxima:
                    linha_atual = test_linha
                else:
                    linhas.append(linha_atual)
                    linha_atual = palavra
            if i := linha_atual:
                linhas.append(i)
            
            linha_espaco = int(font_size * 1.4)
            barra_altura = (len(linhas) * linha_espaco) + int(h * 0.05)
            
            # Fundo retangular escuro para destaque comercial do texto da oferta
            draw.rectangle([(0, h - barra_altura), (w, h)], fill=(15, 23, 42, 220))
            
            y_offset = h - barra_altura + int(h * 0.025)
            for linha in linhas:
                bbox_linha = draw.textbbox((0, 0), linha, font=font)
                w_linha = bbox_linha[2] - bbox_linha[0]
                x_pos = (w - w_linha) // 2
                draw.text((x_pos, y_offset), linha, fill=(255, 204, 0, 255), font=font)
                y_offset += linha_espaco
            
            final_img = Image.alpha_composite(img, txt_layer).convert("RGB")
            final_img.save(output_path, "JPEG", quality=98)
            print(f"🎯 Design finalizado com fonte Montserrat comercial em: {output_path}")
            
        except Exception as e:
            print(f"❌ Erro na composição visual do Pillow: {e}")
            if os.path.exists(input_path): os.replace(input_path, output_path)
