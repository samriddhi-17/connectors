"""Connector framework.

A connector wraps an external datastore behind a small async interface with
*graceful degradation*: if a database is unreachable (or its client library is
not installed) the app keeps running and reports the connector as
``degraded`` / ``unavailable`` instead of crashing.
"""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ConnectorStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class HealthResult:
    status: ConnectorStatus
    latency_ms: float
    detail: str = ""
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    extra: dict = field(default_factory=dict)


@dataclass
class QueryResult:
    ok: bool
    data: dict
    latency_ms: float
    error: str = ""


class Connector(ABC):
    """Base class for datastore connectors."""

    name: str = ""
    kind: str = ""

    def __init__(self, settings, logger, metrics) -> None:
        self.settings = settings
        self.logger = logger
        self.metrics = metrics

    @abstractmethod
    async def startup(self) -> None:
        """Open any persistent connections/resources."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Close connections/resources."""

    @abstractmethod
    async def check(self) -> HealthResult:
        """Return a health result for a single probe."""

    @abstractmethod
    async def query(self, operation: str, payload: dict) -> QueryResult:
        """Run a demo read/write operation against the datastore."""

    # -- shared helpers ---------------------------------------------------

    async def timed_check(self) -> HealthResult:
        """Run :meth:`check` with timing and metric bookkeeping.

        Any exception is converted into an ``unavailable`` result so callers
        never have to handle exceptions from a probe.
        """
        start = time.perf_counter()
        try:
            result = await self.check()
        except Exception as exc:  # noqa: BLE001 - intentional catch-all
            self.logger.warning("connector=%s health check failed: %s", self.name, exc)
            self.metrics.connector_errors_total.labels(connector=self.name, error_type="check").inc()
            result = HealthResult(
                status=ConnectorStatus.UNAVAILABLE,
                latency_ms=0.0,
                detail=str(exc),
            )
        result.latency_ms = round((time.perf_counter() - start) * 1000, 3)
        self.metrics.connector_check_seconds.labels(connector=self.name).observe(result.latency_ms / 1000)
        self.metrics.connector_up.labels(connector=self.name, kind=self.kind).set(
            1 if result.status == ConnectorStatus.OK else 0
        )
        return result

    async def timed_query(self, operation: str, payload: dict) -> QueryResult:
        """Run :meth:`query` with timing and metric bookkeeping."""
        start = time.perf_counter()
        try:
            result = await self.query(operation, payload)
        except Exception as exc:  # noqa: BLE001 - intentional catch-all
            self.logger.warning("connector=%s query %r failed: %s", self.name, operation, exc)
            self.metrics.connector_errors_total.labels(connector=self.name, error_type="query").inc()
            result = QueryResult(ok=False, data={}, latency_ms=0.0, error=str(exc))
        result.latency_ms = round((time.perf_counter() - start) * 1000, 3)
        status = "ok" if result.ok else "error"
        self.metrics.connector_query_duration_seconds.labels(connector=self.name, status=status).observe(
            result.latency_ms / 1000
        )
        return result

    def public_info(self) -> dict:
        """Non-secret connection details for the API."""
        return {"name": self.name, "kind": self.kind}