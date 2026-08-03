"""Exportação local de pacotes para upload manual no TikTok."""

from __future__ import annotations

import json
import os
import shutil
import webbrowser
from pathlib import Path


TIKTOK_UPLOAD_URL = "https://www.tiktok.com/upload"


def export_tiktok_package(
    base_dir: str,
    assets: dict,
    creative_data: dict,
    open_browser: bool = True,
) -> dict:
    """Cria pacote local e abre a página de upload no navegador do Ubuntu."""
    video = str(assets.get("commercial_video_file") or "")
    image = str(assets.get("static_image_file") or "")
    if not video or not os.path.isfile(video):
        return {"ok": False, "erro": "Vídeo MP4 não encontrado para exportação manual."}

    basename = assets.get("basename") or Path(video).stem
    package_dir = Path(base_dir) / "output_campanha" / "tiktok" / str(basename)
    package_dir.mkdir(parents=True, exist_ok=True)

    video_target = package_dir / "video.mp4"
    shutil.copy2(video, video_target)

    thumbnail_target = ""
    if image and os.path.isfile(image):
        thumbnail = package_dir / "thumbnail.jpg"
        shutil.copy2(image, thumbnail)
        thumbnail_target = str(thumbnail)

    caption = _build_caption(creative_data)
    caption_target = package_dir / "legenda.txt"
    caption_target.write_text(caption + "\n", encoding="utf-8")

    metadata = {
        "basename": basename,
        "canal": "TikTok / YouTube Shorts",
        "video": str(video_target),
        "thumbnail": thumbnail_target,
        "legenda": str(caption_target),
        "upload_url": TIKTOK_UPLOAD_URL,
        "publicacao_automatica": False,
    }
    metadata_target = package_dir / "dados_campanha.json"
    metadata_target.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    checklist = package_dir / "CHECKLIST.txt"
    checklist.write_text(
        "UPLOAD MANUAL NO TIKTOK\n\n"
        "1. Abra https://www.tiktok.com/upload neste computador Ubuntu.\n"
        "2. Clique em Upload e selecione o arquivo video.mp4 desta pasta.\n"
        "3. Abra legenda.txt, copie o conteúdo e cole na descrição.\n"
        "4. Revise vídeo, capa, descrição e hashtags.\n"
        "5. Publique manualmente no TikTok.\n\n"
        "O Guardian AI não publica automaticamente e não confirma a publicação.\n",
        encoding="utf-8",
    )

    browser_opened = False
    if open_browser:
        try:
            browser_opened = webbrowser.open(TIKTOK_UPLOAD_URL)
        except Exception:
            browser_opened = False

    return {
        "ok": True,
        "package_dir": str(package_dir),
        "video": str(video_target),
        "thumbnail": thumbnail_target,
        "caption": str(caption_target),
        "checklist": str(checklist),
        "browser_opened": browser_opened,
    }


def _build_caption(creative_data: dict) -> str:
    headline = (creative_data.get("gancho_atencao_inicial") or "").strip()
    copy = (creative_data.get("desenvolvimento_copy") or "").strip()
    cta = (creative_data.get("chamada_para_acao_cta") or "").strip()
    url = (creative_data.get("link_conversao") or "").strip()
    hashtags = "#guardianai #segurancadigital #golpewhatsapp #whatsapp #pix"
    parts = [part for part in (headline, copy[:800], cta, url, hashtags) if part]
    return "\n\n".join(parts)
