#!/usr/bin/env python3
# AVISO: Este e um script LEGADO (v3.0) na raiz do repositorio.
# Usa gemini-2.5 e NAO e o pipeline de producao atual.
# Execute SEMPRE a partir de MKT-Guardian-AUTO/:
#   cd MKT-Guardian-AUTO && python campaign_orchestrator.py
# MKT Guardian AI - Fábrica de Mídia v3.0 (Correção Total)
import os, json, requests
from dotenv import load_dotenv
from google import genai
from google.genai import types
from elevenlabs import ElevenLabs
from moviepy.editor import ImageClip, AudioFileClip
from PIL import Image, ImageDraw, ImageFont

# Configuração
DIR_BASE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(DIR_BASE, '.env')
if not os.path.exists(ENV_PATH):
    print("ERRO: .env não encontrado!"); exit(1)

load_dotenv(ENV_PATH)
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
ELEVEN_KEY = os.getenv("ELEVEN_LABS_API_KEY")
VOICE_ID = os.getenv("ELEVEN_LABS_VOICE_ID", "Josh")
MAX_VIDEOS = int(os.getenv("MAX_VIDEOS_DIARIOS", "20"))
PASTA_SAIDA = os.getenv("PASTA_SAIDA", "output_videos")

if not GEMINI_KEY or not ELEVEN_KEY:
    print("ERRO: Chaves faltando no .env"); exit(1)

client_gemini = genai.Client(api_key=GEMINI_KEY)
client_eleven = ElevenLabs(api_key=ELEVEN_KEY)

DIR_OUT = os.path.join(DIR_BASE, PASTA_SAIDA)
for s in ["", "imagens", "audios", "videos"]:
    os.makedirs(os.path.join(DIR_OUT, s), exist_ok=True)

def get_roteiro(tema):
    print(f"   🧠 Roteiro: {tema}...")
    try:
        # Prompt rigoroso para evitar repetição de instruções
        prompt = f"""Atue como um roteirista de vídeos virais.
        Tema: {tema}
        Retorne APENAS um JSON válido com:
        1. "script": Uma frase impactante de 15 segundos pronta para narração. Não inclua instruções como 'narre aqui'. Apenas a fala.
        2. "img_prompt": Um prompt em INGLÊS descrevendo uma cena realista, cinematográfica, 8k, altamente detalhada sobre o tema. Sem palavras abstratas, descreva objetos e luz."""
        
        resp = client_gemini.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        txt = resp.text.replace("```json", "").replace("```", "").strip()
        return json.loads(txt)
    except Exception as e:
        print(f"   ⚠️ Erro Roteiro: {e}")
        return {"script": f"Cuidado com {tema}. Proteja seu patrimônio agora.", "img_prompt": "cybersecurity shield glowing realistic 8k"}

def get_imagem(prompt, vid_id):
    print(f"   🎨 Gerando Imagem Realista (Gemini 2.5 Flash Image)...")
    path_final = os.path.join(DIR_OUT, "imagens", f"{vid_id}.png")
    
    # Reforço no prompt para realismo
    prompt_reforcado = f"{prompt}, photorealistic, cinematic lighting, 8k, highly detailed, sharp focus, no text, no cartoon"
    
    try:
        resp = client_gemini.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt_reforcado],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"])
        )
        for part in resp.parts:
            # CORREÇÃO AQUI: Verificação completa do atributo
            if hasattr(part, 'inline_data') and part.inline_data is not None:
                img = part.as_image()
                img.save(path_final)
                print("   ✅ Imagem realista gerada!")
                return path_final
        print("   ⚠️ Nenhuma imagem na resposta.")
    except Exception as e:
        print(f"   ⚠️ Falha IA ({e}), criando fallback...")

    # Fallback
    img = Image.new('RGB', (1080, 1920), color=(10, 15, 30))
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    d.text((50, 200), f"Falha na IA. Tema: {tema}", fill=(255,255,255), font=font)
    img.save(path_final)
    return path_final

def get_audio(texto, vid_id):
    print(f"   🎙️ Narração Neural (Velocidade Normal)...")
    path_mp3 = os.path.join(DIR_OUT, "audios", f"{vid_id}.mp3")
    try:
        # Ajuste de estabilidade para naturalidade
        stream = client_eleven.text_to_speech.convert(
            text=texto, 
            voice_id=VOICE_ID, 
            model_id="eleven_multilingual_v2",
            voice_settings={"stability": 0.5, "similarity_boost": 0.75}
        )
        with open(path_mp3, "wb") as f:
            for chunk in stream:
                f.write(chunk)
        return path_mp3
    except Exception as e:
        print(f"   ❌ Erro Áudio: {e}")
        return None

def montar_video(audio_path, img_path, vid_id):
    print(f"   🎬 Renderizando...")
    final_path = os.path.join(DIR_OUT, "videos", f"{vid_id}.mp4")
    try:
        audio = AudioFileClip(audio_path)
        clip = ImageClip(img_path).set_duration(audio.duration)
        clip = clip.set_audio(audio)
        clip = clip.set_fps(24)
        
        clip.write_videofile(final_path, codec='libx264', audio_codec='aac', preset='ultrafast', logger=None)
        print(f"   ✅ SUCESSO: {vid_id}.mp4")
        return True
    except Exception as e:
        print(f"   ❌ Erro Render: {e}")
        return False

def main():
    temas = [
        "Golpe do PIX Fantasma",
        "Segurança Digital para Empresas",
        "Como investir seguro em 2025",
        "Proteja seus dados bancários",
        "Senhas fortes salvam vidas"
    ]
    
    print("\n🏭 FÁBRICA MKT GUARDIAN v3.0\n")
    count = 0
    for i, tema in enumerate(temas):
        if count >= MAX_VIDEOS: break
        vid_id = f"video_{i+1}"
        print(f"[{i+1}] {tema}")
        
        dados = get_roteiro(tema)
        img_path = get_imagem(dados.get("img_prompt", ""), vid_id)
        aud_path = get_audio(dados.get("script", ""), vid_id)
        
        if img_path and aud_path:
            if montar_video(aud_path, img_path, vid_id): count += 1
        print("-" * 40)
    
    print(f"\n🎉 Finalizado! {count} vídeos em: {os.path.join(DIR_OUT, 'videos')}")

if __name__ == "__main__":
    main()
