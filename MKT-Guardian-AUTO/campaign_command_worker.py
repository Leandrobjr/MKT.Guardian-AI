"""Executor Linux da fila de comandos Desktop ↔ Supabase.

Por padrão, o CLI executa apenas dry-run. Publicação real exige --execute.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Callable

from campaign_catalog import CampaignCatalog
from env_loader import load_project_env
from supabase_campaign_bridge import SupabaseBridgeError, SupabaseCampaignBridge

PUBLISHABLE_STATUSES = {"APROVADA", "PRONTA_PARA_PUBLICAR", "ERRO_PUBLICACAO"}
SUPPORTED_ACTIONS = {"PUBLISH", "RETRY"}


class CampaignCommandWorker:
    """Processa comandos aprovados sem expor credenciais ao Desktop."""

    def __init__(
        self,
        base_dir: str,
        *,
        bridge: Any | None = None,
        catalog: CampaignCatalog | None = None,
        publisher_factory: Callable[[], Any] | None = None,
    ):
        load_project_env()
        self.base_dir = os.path.realpath(base_dir)
        self.bridge = bridge or SupabaseCampaignBridge.from_env(self.base_dir)
        if self.bridge is None:
            raise SupabaseBridgeError(
                "Ative SUPABASE_CAMPAIGN_SYNC=true para executar o worker."
            )
        self.catalog = catalog or CampaignCatalog(self.base_dir)
        self.publisher_factory = publisher_factory or self._default_publisher

    @staticmethod
    def _default_publisher() -> Any:
        from meta_publisher import MetaPublisher

        return MetaPublisher()

    def run_once(self, *, limit: int = 10, dry_run: bool = True) -> list[dict[str, Any]]:
        commands = (
            self.bridge.list_pending_commands(limit)
            if dry_run
            else self.bridge.claim_pending_commands(limit)
        )
        return [self.process_command(command, dry_run=dry_run) for command in commands]

    def process_command(
        self, command: dict[str, Any], *, dry_run: bool = True
    ) -> dict[str, Any]:
        command_id = str(command.get("id") or "")
        campaign_id = str(command.get("campaign_id") or "")
        action = str(command.get("action") or "").upper()

        if action not in SUPPORTED_ACTIONS:
            return self._finish(
                command_id,
                False,
                dry_run,
                campaign_id=campaign_id,
                error=f"Ação não suportada pelo worker: {action or 'vazia'}.",
            )

        campaign = self.bridge.get_campaign(campaign_id)
        if not campaign:
            return self._finish(
                command_id,
                False,
                dry_run,
                campaign_id=campaign_id,
                error="Campanha não encontrada no Supabase.",
            )

        remote_status = str(campaign.get("status") or "")
        if remote_status == "PUBLICADA":
            return self._finish(
                command_id,
                False,
                dry_run,
                campaign_id=campaign_id,
                error="Publicação duplicada bloqueada: campanha já publicada.",
            )
        if remote_status not in PUBLISHABLE_STATUSES:
            return self._finish(
                command_id,
                False,
                dry_run,
                campaign_id=campaign_id,
                error=f"Status remoto não permite publicação: {remote_status}.",
            )

        qa = (campaign.get("metadata") or {}).get("qa") or {}
        if qa.get("multimodal_passed") is not True:
            return self._finish(
                command_id,
                False,
                dry_run,
                campaign_id=campaign_id,
                error="QA multimodal obrigatória não aprovada para publicação.",
            )

        channel = str(campaign.get("canal") or "").lower()
        if "tiktok" in channel:
            return self._finish(
                command_id,
                False,
                dry_run,
                campaign_id=campaign_id,
                error="TikTok continua manual; use o pacote de exportação.",
            )
        if "meta" not in channel and "instagram" not in channel:
            return self._finish(
                command_id,
                False,
                dry_run,
                campaign_id=campaign_id,
                error=f"Canal não suportado pelo worker: {campaign.get('canal', '')}.",
            )

        local_record = self.catalog.get(campaign_id)
        if not local_record or not self.catalog.can_publish(campaign_id):
            return self._finish(
                command_id,
                False,
                dry_run,
                campaign_id=campaign_id,
                error="Catálogo local não está aprovado para publicação.",
            )

        asset_path = str(local_record.get("asset_path") or "")
        try:
            asset_path = self.bridge.validate_local_asset(asset_path)
        except SupabaseBridgeError as exc:
            return self._finish(
                command_id,
                False,
                dry_run,
                campaign_id=campaign_id,
                error=str(exc),
            )

        caption = str(campaign.get("legenda") or local_record.get("legenda") or "")
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "command_id": command_id,
                "campaign_id": campaign_id,
                "asset": os.path.basename(asset_path),
                "action": action,
            }

        requested_by = str(command.get("requested_by") or "")
        try:
            self.bridge.update_campaign_publication(
                campaign_id,
                "PUBLICANDO",
                platform="Instagram",
                approved_by=requested_by,
            )
            self._update_local(
                local_record,
                "PUBLICANDO",
                asset_path=asset_path,
            )
            result = self.publisher_factory().postar_asset(
                asset_path,
                caption,
                qa_evidence=qa,
            )
            if result.get("ok"):
                returned_id = str(result.get("post_id") or "")
                self.bridge.update_campaign_publication(
                    campaign_id,
                    "PUBLICADA",
                    platform="Instagram",
                    returned_id=returned_id,
                )
                self._update_local(
                    local_record,
                    "PUBLICADA",
                    asset_path=asset_path,
                    returned_id=returned_id,
                    platform="Instagram",
                )
                return self._finish(
                    command_id,
                    True,
                    False,
                    campaign_id=campaign_id,
                    result={
                        "status": "PUBLICADA",
                        "platform": "Instagram",
                        "returned_id": returned_id,
                        "executor": "linux_worker",
                    },
                )

            error = str(result.get("erro") or "Publicação recusada pela Meta.")
            self._record_failure(command_id, campaign_id, local_record, asset_path, error)
            return {
                "ok": False,
                "command_id": command_id,
                "campaign_id": campaign_id,
                "error": error,
            }
        except Exception as exc:
            error = f"Falha inesperada no worker: {exc}"
            self._record_failure(command_id, campaign_id, local_record, asset_path, error)
            return {
                "ok": False,
                "command_id": command_id,
                "campaign_id": campaign_id,
                "error": error,
            }

    def _update_local(
        self,
        current: dict[str, Any],
        status: str,
        *,
        asset_path: str,
        platform: str = "",
        returned_id: str = "",
        error_message: str = "",
    ) -> None:
        config = {
            "_campaign_id": current.get("campaign_id"),
            "publico_slug": current.get("publico", ""),
            "golpe_id": current.get("golpe", ""),
            "canal": current.get("canal", ""),
            "midia": current.get("midia", ""),
            "preset_midia": current.get("preset") or {},
            "_revision": current.get("revisao", 0),
        }
        creative = {
            "campaign_id": current.get("campaign_id"),
            "gancho_atencao_inicial": (current.get("headline") or ""),
            "desenvolvimento_copy": current.get("roteiro", ""),
            "legenda": current.get("legenda", ""),
        }
        assets = {
            "basename": Path(asset_path).stem,
            "commercial_video_file": asset_path
            if asset_path.lower().endswith(".mp4")
            else "",
            "static_image_file": asset_path
            if not asset_path.lower().endswith(".mp4")
            else "",
        }
        self.catalog.update(
            str(current["campaign_id"]),
            status,
            config,
            creative,
            assets,
            platform=platform,
            returned_id=returned_id,
            error_message=error_message,
            actor="linux_worker",
        )

    def _record_failure(
        self,
        command_id: str,
        campaign_id: str,
        current: dict[str, Any],
        asset_path: str,
        error: str,
    ) -> None:
        try:
            self.bridge.update_campaign_publication(
                campaign_id,
                "ERRO_PUBLICACAO",
                platform="Instagram",
                error_message=error,
            )
            self._update_local(
                current,
                "ERRO_PUBLICACAO",
                asset_path=asset_path,
                platform="Instagram",
                error_message=error,
            )
            self.bridge.complete_command(
                command_id,
                success=False,
                result={
                    "status": "ERRO_PUBLICACAO",
                    "platform": "Instagram",
                    "campaign_id": campaign_id,
                    "executor": "linux_worker",
                },
                error=error,
            )
        except Exception:
            pass

    def _finish(
        self,
        command_id: str,
        success: bool,
        dry_run: bool,
        *,
        campaign_id: str,
        error: str = "",
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not dry_run and command_id:
            self.bridge.complete_command(
                command_id,
                success=success,
                result=result or {"campaign_id": campaign_id, "executor": "linux_worker"},
                error=error,
            )
        response = {
            "ok": success,
            "dry_run": dry_run,
            "command_id": command_id,
            "campaign_id": campaign_id,
        }
        if error:
            response["error"] = error
        if result:
            response["result"] = result
        return response


def main() -> int:
    parser = argparse.ArgumentParser(description="Processa comandos Desktop ↔ Linux.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Executa publicação real; sem esta opção, apenas dry-run.",
    )
    args = parser.parse_args()
    try:
        worker = CampaignCommandWorker(os.path.dirname(os.path.abspath(__file__)))
        results = worker.run_once(limit=args.limit, dry_run=not args.execute)
    except SupabaseBridgeError as exc:
        print(f"❌ {exc}")
        return 2

    for result in results:
        print(result)
    if not results:
        print("✅ Nenhum comando pendente.")
    return 0 if all(item.get("ok") for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
