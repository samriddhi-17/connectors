"""Demo query endpoint that exercises a connector's read/write path."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/query", tags=["query"])


class QueryRequest(BaseModel):
    operation: str = Field(..., description="e.g. get/put for aerospike; upsert/select/list for yugabyte")
    payload: dict = Field(default_factory=dict)


@router.post("/{name}")
async def run_query(name: str, body: QueryRequest, request: Request) -> dict:
    connector = request.app.state.connectors.get(name)
    if connector is None:
        raise HTTPException(status_code=404, detail=f"connector {name!r} not found")

    result = await connector.timed_query(body.operation, body.payload)
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.error)

    return {"connector": name, "operation": body.operation, "data": result.data, "latency_ms": result.latency_ms}