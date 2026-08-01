"""
Meta Publisher — Guardian AI
Postagem no Instagram via Meta Graph API v21.0 (Reels e imagens).
"""

import os
import time

import requests

from env_loader import load_project_env

load_project_env()

GRAPH_BASE = "https://graph.facebook.com/v21.0"
RUPLOAD_BASE = "https://rupload.facebook.com/ig-api-upload/v21.0"


class MetaPublisher:
    def __init__(self):
        self.token = os.getenv("META_ACCESS_TOKEN")
        self.ig_user = os.getenv("META_IG_USER_ID")
        self.imgbb_key = os.getenv("IMGBB_API_KEY")

        if not self.token or not self.ig_user:
            raise EnvironmentError(
                "META_ACCESS_TOKEN e META_IG_USER_ID precisam estar no .env"
            )

    def verificar_token(self) -> dict | None:
        """Retorna None se OK; senão dict com ok=False e mensagem legível."""
        app_id = os.getenv("META_APP_ID", "")
        app_secret = os.getenv("META_APP_SECRET", "")
        app_token = f"{app_id}|{app_secret}" if app_id and app_secret else self.token
        try:
            r = requests.get(
                f"{GRAPH_BASE}/debug_token",
                params={"input_token": self.token, "access_token": app_token},
                timeout=15,
            )
            data = r.json().get("data") or {}
            if not data.get("is_valid"):
                return {
                    "ok": False,
                    "erro": (
                        "META_ACCESS_TOKEN expirado ou inválido. "
                        "No Linux: python3 meta_token_check.py"
                    ),
                }
            exp = data.get("expires_at") or 0
            if exp and exp < time.time():
                return {
                    "ok": False,
                    "erro": (
                        "META_ACCESS_TOKEN expirado. "
                        "Renove (long-lived 60 dias) e atualize o .env no Linux."
                    ),
                }
            scopes = set(data.get("scopes") or [])
            needed = {"instagram_basic", "instagram_content_publish"}
            if not needed.issubset(scopes):
                falta = ", ".join(sorted(needed - scopes))
                return {
                    "ok": False,
                    "erro": f"Token sem permissões Instagram: {falta}",
                }
        except Exception:
            pass
        return None

    @staticmethod
    def _meta_error(response: requests.Response) -> str:
        try:
            body = response.json()
            err = body.get("error", {})
            msg = err.get("message", response.text)
            code = err.get("code")
            sub = err.get("error_subcode")
            user = err.get("error_user_msg")
            detail = f"{response.status_code} — {msg}"
            if code is not None:
                detail += f" (code={code}"
                if sub is not None:
                    detail += f", subcode={sub}"
                detail += ")"
            if user:
                detail += f" — {user}"
            return detail
        except Exception:
            return f"{response.status_code} — {response.text[:300]}"

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

    def _upload_video_resumable(self, caminho_video: str, caption: str) -> str | None:
        """Upload local via protocolo resumável (Instagram Graph API)."""
        tamanho = os.path.getsize(caminho_video)
        print(f"📤 [Meta] Upload vídeo ({tamanho // 1024} KB)...")

        try:
            r = requests.post(
                f"{GRAPH_BASE}/{self.ig_user}/media",
                data={
                    "upload_type": "resumable",
                    "media_type": "REELS",
                    "caption": caption[:2200],
                    "share_to_feed": "true",
                    "access_token": self.token,
                },
                timeout=30,
            )
            if not r.ok:
                print(f"❌ [Meta] Falha init container: {self._meta_error(r)}")
                return None
            container_id = r.json().get("id")
            if not container_id:
                print(f"❌ [Meta] Resposta sem container id: {r.text[:300]}")
                return None
            print(f"📦 [Meta] Container criado: {container_id}")
        except Exception as e:
            print(f"❌ [Meta] Falha init upload: {e}")
            return None

        upload_url = f"{RUPLOAD_BASE}/{container_id}"
        try:
            with open(caminho_video, "rb") as f:
                up = requests.post(
                    upload_url,
                    headers={
                        "Authorization": f"OAuth {self.token}",
                        "offset": "0",
                        "file_size": str(tamanho),
                    },
                    data=f,
                    timeout=300,
                )
            if not up.ok:
                print(f"❌ [Meta] Falha transferência: {self._meta_error(up)}")
                return None
            print("✅ [Meta] Vídeo transferido para servidores Meta.")
        except Exception as e:
            print(f"❌ [Meta] Falha transferência: {e}")
            return None

        return container_id

    def _aguardar_container(self, container_id: str) -> dict | None:
        for tentativa in range(18):
            if tentativa:
                time.sleep(10)
            try:
                status_r = requests.get(
                    f"{GRAPH_BASE}/{container_id}",
                    params={
                        "fields": "status_code,status",
                        "access_token": self.token,
                    },
                    timeout=15,
                )
                if not status_r.ok:
                    continue
                payload = status_r.json()
                status_code = payload.get("status_code", "")
                if status_code == "FINISHED":
                    return None
                if status_code in ("ERROR", "EXPIRED"):
                    return {"ok": False, "erro": payload}
                if tentativa == 0:
                    print("⏳ [Meta] Processando vídeo...")
            except Exception:
                pass
        return {"ok": False, "erro": "Timeout aguardando processamento do vídeo."}

    def postar_reel(self, caminho_video: str, caption: str) -> dict:
        token_err = self.verificar_token()
        if token_err:
            print(f"❌ [Meta] {token_err['erro']}")
            return token_err

        container_id = self._upload_video_resumable(caminho_video, caption)
        if not container_id:
            return {"ok": False, "erro": "Falha no upload do vídeo."}

        erro = self._aguardar_container(container_id)
        if erro:
            return erro

        try:
            r = requests.post(
                f"{GRAPH_BASE}/{self.ig_user}/media_publish",
                data={"creation_id": container_id, "access_token": self.token},
                timeout=30,
            )
            if not r.ok:
                return {"ok": False, "erro": self._meta_error(r)}
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
            if not r.ok:
                return {"ok": False, "erro": self._meta_error(r)}
            container_id = r.json().get("id")
            r2 = requests.post(
                f"{GRAPH_BASE}/{self.ig_user}/media_publish",
                data={"creation_id": container_id, "access_token": self.token},
                timeout=30,
            )
            if not r2.ok:
                return {"ok": False, "erro": self._meta_error(r2)}
            post_id = r2.json().get("id")
            print(f"✅ [Meta] Imagem publicada! ID: {post_id}")
            return {"ok": True, "post_id": post_id}
        except Exception as e:
            return {"ok": False, "erro": str(e)}

    def postar_asset(self, asset_path: str, caption: str) -> dict:
        if asset_path.lower().endswith(".mp4"):
            return self.postar_reel(asset_path, caption)
        return self.postar_imagem(asset_path, caption)
