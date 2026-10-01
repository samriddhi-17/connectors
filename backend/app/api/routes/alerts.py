"""Grafana -> OpenSRE alert webhook.

Grafana Alerting is configured (see grafana/provisioning/alerting/) to POST
webhook notifications to ``/api/v1/alerts``. Each payload is normalized into
OpenSRE's alert JSON schema, persisted under ``OPENSRE_ALERTS_DIR`` and —
when enabled — fed straight into ``opensre investigate``.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.opensre import invoke_cli, normalize_alert, recent_alerts, save_alert

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_alert(body: dict, request: Request) -> dict:
    settings = request.app.state.settings
    logger = request.app.state.logger
    config = settings.opensre

    alert = normalize_alert(body)
    path = save_alert(alert, config.alerts_dir)
    logger.info("alert persisted to %s", path)

    cli_result = await invoke_cli(path, config, logger)

    return {
        "accepted": True,
        "alert_id": alert["alert"].get("alert_id"),
        "file": str(path),
        "opensre": cli_result,
    }


@router.get("")
async def list_alerts(request: Request) -> dict:
    alerts_dir = request.app.state.settings.opensre.alerts_dir
    return {"alerts": recent_alerts(alerts_dir)}