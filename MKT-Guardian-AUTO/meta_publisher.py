"""
Meta Publisher — Guardian AI
Postagem no Instagram via Meta Graph API v21.0 (Reels e imagens).
"""

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_BASE = "https://graph.facebook.com/v21.0"


class MetaPublisher:
    def __init__(self):
        self.token = os.getenv("META_ACCESS_TOKEN")
        self.ig_user = os.getenv("META_IG_USER_ID")
        self.imgbb_key = os.getenv("IMGBB_API_KEY")

        if not self.token or not self.ig_user:
            raise EnvironmentError(
                "META_ACCESS_TOKEN e META_IG_USER_ID precisam estar no .env"
            )

    def _upload_para_imgbb(self, caminho_imagem: str) -> str | None:
        if not self.imgbb_key:
            print("❌ [ImgBB] IMGBB_API_KEY não configurada.")
            return None
        try:
            with open(caminho_imagem, "rb") as f:
                r = requests.post(
                    "https://api.imgbb.com/1/upload",
                    params={"key": self.imgbb_key},
                    files={"image": f},
                    timeout=60,
                )
            r.raise_for_status()
            url = r.json()["data"]["url"]
            print(f"✅ [ImgBB] Imagem hospedada: {url}")
            return url
        except Exception as e:
            print(f"❌ [ImgBB] Falha: {e}")
            return None

    def _upload_video_meta(self, caminho_video: str) -> str | None:
        tamanho = os.path.getsize(caminho_video)
        print(f"📤 [Meta] Upload vídeo ({tamanho // 1024} KB)...")

        init_url = f"{GRAPH_BASE}/{self.ig_user}/video_reels"
        try:
            r = requests.post(
                init_url,
                data={"upload_phase": "start", "access_token": self.token},
                timeout=30,
            )
            r.raise_for_status()
            resp = r.json()
            video_id = resp.get("video_id")
            upload_url = resp.get("upload_url")
            if not video_id or not upload_url:
                return None
        except Exception as e:
            print(f"❌ [Meta] Falha init upload: {e}")
            return None

        try:
            with open(caminho_video, "rb") as f:
                requests.post(
                    upload_url,
                    headers={
                        "Authorization": f"OAuth {self.token}",
                        "offset": "0",
                        "file_size": str(tamanho),
                    },
                    data=f,
                    timeout=300,
                ).raise_for_status()
        except Exception as e:
            print(f"❌ [Meta] Falha transferência: {e}")
            return None

        return video_id

    def postar_reel(self, caminho_video: str, caption: str) -> dict:
        video_id = self._upload_video_meta(caminho_video)
        if not video_id:
            return {"ok": False, "erro": "Falha no upload do vídeo."}

        try:
            r = requests.post(
                f"{GRAPH_BASE}/{self.ig_user}/media",
                data={
                    "media_type": "REELS",
                    "video_id": video_id,
                    "caption": caption[:2200],
                    "share_to_feed": "true",
                    "access_token": self.token,
                },
                timeout=60,
            )
            r.raise_for_status()
            container_id = r.json().get("id")
        except Exception as e:
            return {"ok": False, "erro": f"Falha ao criar container: {e}"}

        for _ in range(12):
            time.sleep(10)
            try:
                status_r = requests.get(
                    f"{GRAPH_BASE}/{container_id}",
                    params={"fields": "status_code", "access_token": self.token},
                    timeout=15,
                )
                status_code = status_r.json().get("status_code", "")
                if status_code == "FINISHED":
                    break
                if status_code in ("ERROR", "EXPIRED"):
                    return {"ok": False, "erro": status_r.json()}
            except Exception:
                pass

        try:
            r = requests.post(
                f"{GRAPH_BASE}/{self.ig_user}/media_publish",
                data={"creation_id": container_id, "access_token": self.token},
                timeout=30,
            )
            r.raise_for_status()
            post_id = r.json().get("id")
            print(f"✅ [Meta] Reel publicado! ID: {post_id}")
            return {"ok": True, "post_id": post_id}
        except Exception as e:
            return {"ok": False, "erro": str(e)}

    def postar_imagem(self, caminho_imagem: str, caption: str) -> dict:
        image_url = self._upload_para_imgbb(caminho_imagem)
        if not image_url:
            return {"ok": False, "erro": "Falha ImgBB."}

        try:
            r = requests.post(
                f"{GRAPH_BASE}/{self.ig_user}/media",
                data={
                    "image_url": image_url,
                    "caption": caption[:2200],
                    "access_token": self.token,
                },
                timeout=30,
            )
            r.raise_for_status()
            container_id = r.json().get("id")
            r2 = requests.post(
                f"{GRAPH_BASE}/{self.ig_user}/media_publish",
                data={"creation_id": container_id, "access_token": self.token},
                timeout=30,
            )
            r2.raise_for_status()
            post_id = r2.json().get("id")
            print(f"✅ [Meta] Imagem publicada! ID: {post_id}")
            return {"ok": True, "post_id": post_id}
        except Exception as e:
            return {"ok": False, "erro": str(e)}

    def postar_asset(self, asset_path: str, caption: str) -> dict:
        if asset_path.lower().endswith(".mp4"):
            return self.postar_reel(asset_path, caption)
        return self.postar_imagem(asset_path, caption)
