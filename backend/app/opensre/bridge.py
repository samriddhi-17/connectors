"""OpenSRE bridge.

OpenSRE (https://github.com/Tracer-Cloud/opensre) is the open-source AI SRE
agent framework. It investigates incidents from alert JSON files, e.g.::

    opensre investigate -i tests/e2e/kubernetes/fixtures/datadog_k8s_alert.json

This module bridges Grafana Alerting into OpenSRE:

1. Grafana's webhook contact point POSTs an alert payload to
   ``POST /api/v1/alerts``.
2. :func:`normalize_alert` converts that payload into OpenSRE's alert schema
   (``_meta`` + ``alert`` with an ``alerts`` array of Alertmanager-style
   entries).
3. :func:`save_alert` writes the JSON to ``OPENSRE_ALERTS_DIR``.
4. Optionally :func:`invoke_cli` shells out to ``opensre investigate -i`` so
   an RCA run starts automatically.

The schema mirrors the fixture OpenSRE itself ships for k8s investigations so
the demo alerts are drop-in compatible.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.config import OpensreConfig

META_SOURCE = "grafana-alerting-webhook"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _alert_entry_from_payload(payload: dict) -> dict:
    """Extract a single OpenSRE-compatible alert entry from a webhook payload."""
    return {
        "status": payload.get("status", "firing"),
        "labels": payload.get("labels", {}),
        "annotations": payload.get("annotations", {}),
        "startsAt": payload.get("startsAt") or _iso_now(),
        "endsAt": payload.get("endsAt") or "0001-01-01T00:00:00Z",
        "generatorURL": payload.get("generatorURL", ""),
        "fingerprint": payload.get("fingerprint", ""),
    }


def normalize_alert(payload: dict) -> dict:
    """Convert a Grafana (or Alertmanager-style) webhook payload into the
    OpenSRE alert JSON schema.

    Grafana webhooks arrive either as a single alert object or — when
    ``maxAlerts`` batching is enabled — as ``{"alerts": [...]}``. Both shapes
    are handled.
    """
    raw_alerts = payload.get("alerts") or [payload]

    entries = []
    for entry in raw_alerts:
        if isinstance(entry, dict):
            entries.append(_alert_entry_from_payload(entry))

    common_labels: dict[str, str] = {}
    common_annotations: dict[str, str] = {}
    for entry in entries:
        common_labels.update(entry.get("labels", {}))
        common_annotations.update(entry.get("annotations", {}))

    alert_id = payload.get("alert_id") or payload.get("fingerprint") or entries[0].get("fingerprint") or "grafana-alert"

    return {
        "_meta": {
            "schema_version": 1,
            "source": META_SOURCE,
            "captured_at": _iso_now(),
        },
        "alert": {
            "alerts": entries,
            "version": "4",
            "externalURL": payload.get("externalURL", ""),
            "truncatedAlerts": payload.get("truncatedAlerts", 0),
            "groupLabels": payload.get("groupLabels", {}),
            "commonLabels": common_labels,
            "commonAnnotations": common_annotations,
            "groupKey": payload.get("groupKey", "{}"),
            "title": payload.get("title") or entries[0].get("annotations", {}).get("summary", "OpenSRE demo alert"),
            "state": payload.get("state", "alerting"),
            "message": payload.get("message") or entries[0].get("annotations", {}).get("description", ""),
            "alert_id": alert_id,
        },
        "evidence": {},
    }


def _slug(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in value)[:80]


def save_alert(alert: dict, alerts_dir: str) -> Path:
    """Persist an OpenSRE-compatible alert to ``OPENSRE_ALERTS_DIR``."""
    directory = Path(alerts_dir)
    directory.mkdir(parents=True, exist_ok=True)

    alert_id = alert["alert"].get("alert_id") or "alert"
    name = alert["alert"].get("commonLabels", {}).get("alertname", "")
    when = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{when}_{_slug(alert_id)}_{_slug(name)}.json"
    path = directory / filename

    path.write_text(json.dumps(alert, indent=2), encoding="utf-8")
    return path


async def invoke_cli(alert_path: Path, config: "OpensreConfig", logger) -> dict:
    """Run ``opensre investigate -i <file>`` as a subprocess.

    Only invoked when ``OPENSRE_INVOKE_CLI=true`` and the binary is reachable.
    Failures are reported in the returned dict — the bridge never raises.
    """
    binary = shutil.which(config.bin)
    if not config.invoke_cli or binary is None:
        return {
            "invoked": False,
            "reason": "OPENSRE_INVOKE_CLI is false or the opensre binary was not found",
        }
    try:
        process = await asyncio.create_subprocess_exec(
            binary,
            "investigate",
            "-i",
            str(alert_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=config.cli_timeout_s
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return {"invoked": True, "timeout": True, "rc": -1}
        logger.info("opensre investigate rc=%s", process.returncode)
        return {
            "invoked": True,
            "rc": process.returncode,
            "stdout": stdout.decode(errors="replace")[:8000],
            "stderr": stderr.decode(errors="replace")[:4000],
        }
    except Exception as exc:  # noqa: BLE001
        return {"invoked": True, "error": str(exc)}


def recent_alerts(alerts_dir: str, limit: int = 20) -> list[dict]:
    """List the most recently written alert files."""
    directory = Path(alerts_dir)
    if not directory.exists():
        return []
    files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "file": path.name,
            "written_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        }
        for path in files[:limit]
    ]