"""Liveness / readiness / overall health probes.

``/livez`` is always 200 while the process is alive.
``/readyz`` returns 503 unless every enabled connector reports ``ok`` —
suitable for Kubernetes readiness probes.
``/healthz`` always returns 200 with a per-connector breakdown (used by the
frontend), reporting ``degraded`` / ``unavailable`` rather than failing.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.connectors.base import ConnectorStatus

router = APIRouter()

HEALTH_SUMMARY = {
    ConnectorStatus.OK: "ok",
    ConnectorStatus.DEGRADED: "degraded",
    ConnectorStatus.UNAVAILABLE: "unavailable",
}


@router.get("/livez")
async def livez() -> dict:
    return {"status": "ok"}


@router.get("/healthz")
async def healthz(request: Request) -> dict:
    connectors = request.app.state.connectors
    results = await asyncio.gather(*(c.timed_check() for c in connectors.values()))
    statuses = {name: result for name, result in zip(connectors.keys(), results, strict=False)}

    worst = ConnectorStatus.OK
    for result in statuses.values():
        if _severity(result.status) > _severity(worst):
            worst = result.status

    return {
        "status": HEALTH_SUMMARY[worst],
        "app": request.app.state.settings.app.app_name,
        "environment": request.app.state.settings.app.environment,
        "connectors": {
            name: {
                "status": HEALTH_SUMMARY[result.status],
                "latency_ms": result.latency_ms,
                "detail": result.detail,
                "checked_at": result.checked_at.isoformat(),
            }
            for name, result in statuses.items()
        },
    }


@router.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    connectors = request.app.state.connectors
    if not connectors:
        return JSONResponse(status_code=503, content={"status": "not ready", "reason": "no connectors enabled"})
    results = await asyncio.gather(*(c.timed_check() for c in connectors.values()))
    all_ok = all(r.status == ConnectorStatus.OK for r in results)
    body = {"status": "ready" if all_ok else "not ready", "connectors": {c.name: r.status.value for c, r in zip(connectors.values(), results, strict=False)}}
    return JSONResponse(status_code=200 if all_ok else 503, content=body)


def _severity(status: ConnectorStatus) -> int:
    return {
        ConnectorStatus.OK: 0,
        ConnectorStatus.DEGRADED: 1,
        ConnectorStatus.UNAVAILABLE: 2,
    }[status]