"""Yugabyte connector.

YugabyteDB speaks the PostgreSQL wire protocol, so this connector uses the
``psycopg`` driver with a small async connection pool. When the database is
unreachable the pool fails to open and health checks report the connector as
``unavailable`` — the application keeps serving.
"""
from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any

from app.connectors.base import Connector, ConnectorStatus, HealthResult, QueryResult

if TYPE_CHECKING:
    from app.metrics import Metrics


class YugabyteConnector(Connector):
    name = "yugabyte"
    kind = "yugabyte"

    def __init__(self, settings, logger, metrics: Metrics) -> None:
        super().__init__(settings, logger, metrics)
        self._pool: Any = None
        self._pool_ready: bool = False

    async def startup(self) -> None:
        self.logger.info(
            "yugabyte connector starting (db=%s@%s:%s)",
            self.settings.database,
            self.settings.host,
            self.settings.port,
        )
        from psycopg_pool import AsyncConnectionPool  # noqa: PLC0415

        try:
            self._pool = AsyncConnectionPool(
                self.settings.conninfo,
                min_size=self.settings.pool_min,
                max_size=self.settings.pool_max,
                timeout=float(self.settings.connect_timeout_s),
                open=False,
            )
            await self._pool.open()
            self._pool_ready = True
            self.logger.info("yugabyte pool opened")
        except Exception as exc:  # noqa: BLE001
            self._pool_ready = False
            self.logger.warning("yugabyte pool open failed: %s", exc)

    async def shutdown(self) -> None:
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception:  # noqa: BLE001
                pass
            self._pool = None
            self._pool_ready = False

    async def _acquire(self):
        if not self._pool_ready or self._pool is None:
            raise ConnectionError("YugabyteDB connection pool is not open")
        return self._pool.connection()

    async def check(self) -> HealthResult:
        start = time.perf_counter()
        try:
            async with await self._acquire() as conn:
                cur = await conn.execute("SELECT 1")
                row = await cur.fetchone()
            if row != (1,):
                return HealthResult(
                    status=ConnectorStatus.DEGRADED,
                    latency_ms=0.0,
                    detail="unexpected probe response",
                )
            latency = round((time.perf_counter() - start) * 1000, 3)
            return HealthResult(
                status=ConnectorStatus.OK,
                latency_ms=latency,
                detail=f"connected to {self.settings.host}:{self.settings.port}/{self.settings.database}",
            )
        except Exception as exc:  # noqa: BLE001
            return HealthResult(
                status=ConnectorStatus.UNAVAILABLE,
                latency_ms=0.0,
                detail=f"{type(exc).__name__}: {exc}",
            )

    async def query(self, operation: str, payload: dict) -> QueryResult:
        table = self.settings.table_name
        key = payload.get("key") or str(uuid.uuid4())
        value = payload.get("value") or f"hello from connects at {time.time()}"

        ddl = (
            f"CREATE TABLE IF NOT EXISTS {table} ("
            "  id TEXT PRIMARY KEY, "
            "  value TEXT NOT NULL, "
            "  updated_at TIMESTAMPTZ DEFAULT now()"
            ")"
        )
        async with await self._acquire() as conn:
            if operation == "upsert":
                await conn.execute(ddl)
                await conn.execute(
                    f"INSERT INTO {table} (id, value) VALUES (%s, %s) "
                    f"ON CONFLICT (id) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
                    (key, value),
                )
                return QueryResult(ok=True, data={"operation": "upsert", "key": key}, latency_ms=0.0)

            if operation == "select":
                await conn.execute(ddl)
                cur = await conn.execute(f"SELECT id, value FROM {table} WHERE id = %s", (key,))
                row = await cur.fetchone()
                return QueryResult(
                    ok=row is not None,
                    data={"key": key, "row": {"id": row[0], "value": row[1]} if row else None},
                    latency_ms=0.0,
                )

            if operation == "list":
                await conn.execute(ddl)
                cur = await conn.execute(f"SELECT id, value FROM {table} ORDER BY updated_at DESC LIMIT 20")
                rows = await cur.fetchall()
                return QueryResult(
                    ok=True,
                    data={"rows": [{"id": r[0], "value": r[1]} for r in rows]},
                    latency_ms=0.0,
                )

            return QueryResult(
                ok=False,
                data={},
                latency_ms=0.0,
                error=f"unsupported operation {operation!r} for yugabyte (try 'upsert', 'select' or 'list')",
            )

    def public_info(self) -> dict:
        info = super().public_info()
        info["database"] = self.settings.database
        info["table"] = self.settings.table_name
        info["endpoint"] = f"{self.settings.host}:{self.settings.port}"
        return info