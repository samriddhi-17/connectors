"""Connector metadata + live health endpoints."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/connectors", tags=["connectors"])


@router.get("")
async def list_connectors(request: Request) -> dict:
    connectors = request.app.state.connectors
    results = await asyncio.gather(*(c.timed_check() for c in connectors.values()))
    return {
        "connectors": [
            {
                **connector.public_info(),
                "status": result.status.value,
                "latency_ms": result.latency_ms,
                "detail": result.detail,
            }
            for connector, result in zip(connectors.values(), results, strict=False)
        ]
    }


@router.get("/{name}")
async def connector_detail(name: str, request: Request) -> dict:
    connector = request.app.state.connectors.get(name)
    if connector is None:
        raise HTTPException(status_code=404, detail=f"connector {name!r} not found")
    result = await connector.timed_check()
    return {
        **connector.public_info(),
        "status": result.status.value,
        "latency_ms": result.latency_ms,
        "detail": result.detail,
        "checked_at": result.checked_at.isoformat(),
        "extra": result.extra,
    }