"""Aerospike connector.

The official ``aerospike`` client is a C extension that is not always
buildable on every platform (Windows in particular). The connector therefore
imports the client lazily: when the package is missing the connector stays
healthy-but-degraded and the rest of the application is unaffected.
"""
from __future__ import annotations

import sys
import time
import uuid
from typing import TYPE_CHECKING, Any

from app.connectors.base import Connector, ConnectorStatus, HealthResult, QueryResult

if TYPE_CHECKING:
    from app.metrics import Metrics


def _load_client() -> Any:
    """Import the Aerospike client, raising ImportError if unavailable."""
    try:
        import aerospike  # noqa: PLC0415 - lazy import on purpose
    except ImportError as exc:  # pragma: no cover - depends on env
        raise ImportError(
            "Aerospike client is not installed. Install with: "
            "pip install 'connects-backend[aerospike]'"
        ) from exc
    return aerospike


class AerospikeConnector(Connector):
    name = "aerospike"
    kind = "aerospike"

    def __init__(self, settings, logger, metrics: Metrics) -> None:
        super().__init__(settings, logger, metrics)
        self._client: Any = None
        self._aerospike: Any = None
        self._missing_client: bool = False

    @property
    def _config(self) -> dict:
        cfg: dict = {
            "hosts": [(self.settings.host, self.settings.port)],
            "timeout": int(self.settings.connect_timeout_s * 1000),
            "max_retries": 1,
        }
        auth = self.settings.auth_mode or "none"
        if auth not in ("none",):
            cfg["user"] = self.settings.username
            cfg["password"] = self.settings.password
        return cfg

    async def startup(self) -> None:
        self.logger.info("aerospike connector starting (host=%s:%s)", self.settings.host, self.settings.port)
        try:
            self._aerospike = _load_client()
        except ImportError as exc:
            self._missing_client = True
            self.logger.warning("aerospike client unavailable: %s", exc)

    async def shutdown(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
            self._client = None

    def _load_client_module(self) -> None:
        if self._aerospike is None and not self._missing_client:
            try:
                self._aerospike = _load_client()
            except ImportError as exc:
                self._missing_client = True
                self.logger.warning("aerospike client unavailable: %s", exc)

    def _connect(self) -> Any:
        self._load_client_module()
        if self._missing_client:
            raise RuntimeError(
                "Aerospike client not installed; "
                "pip install 'connects-backend[aerospike]'"
            )
        if self._client is None:
            client = self._aerospike.client(self._config)
            client.connect()
            self._client = client
        return self._client

    async def check(self) -> HealthResult:
        if self._missing_client:
            return HealthResult(
                status=ConnectorStatus.DEGRADED,
                latency_ms=0.0,
                detail="Aerospike client library not installed",
                extra={"missing_client": True},
            )
        start = time.perf_counter()
        try:
            client = self._connect()
            if not client.is_connected():
                return HealthResult(
                    status=ConnectorStatus.UNAVAILABLE,
                    latency_ms=0.0,
                    detail="not connected",
                )
            self._info(client, "statistics")
            latency = round((time.perf_counter() - start) * 1000, 3)
            return HealthResult(
                status=ConnectorStatus.OK,
                latency_ms=latency,
                detail=f"connected to {self.settings.host}:{self.settings.port}",
            )
        except Exception as exc:  # noqa: BLE001
            return HealthResult(
                status=ConnectorStatus.UNAVAILABLE,
                latency_ms=0.0,
                detail=f"{type(exc).__name__}: {exc}",
            )

    def _info(self, client: Any, command: str) -> Any:
        """Issue an info ``command`` against one node.

        The aerospike client renamed its info API across major versions
        (``info_node`` -> ``info_single_node``/``info_random_node``/``info_all``),
        so the connector probes whatever entry point the installed client
        exposes.
        """
        if hasattr(client, "info_random_node"):
            return client.info_random_node(command)
        if hasattr(client, "info_single_node"):
            return client.info_single_node(self._first_host(), command)
        if hasattr(client, "info_all"):
            return client.info_all(command)
        if hasattr(client, "info_node"):  # pre-12.x clients
            return client.info_node(command, self._first_host())
        raise RuntimeError("no usable aerospike client info() API found")

    def _first_host(self) -> str:
        return f"{self.settings.host}:{self.settings.port}"

    async def query(self, operation: str, payload: dict) -> QueryResult:
        if operation not in ("put", "get"):
            return QueryResult(
                ok=False,
                data={},
                latency_ms=0.0,
                error=f"unsupported operation {operation!r} for aerospike (try 'put' or 'get')",
            )

        self._load_client_module()
        if self._missing_client:
            return QueryResult(
                ok=False,
                data={},
                latency_ms=0.0,
                error="Aerospike client library not installed",
            )
        client = self._connect()
        key = payload.get("key") or str(uuid.uuid4())
        bin_name = payload.get("bin") or "value"
        value = payload.get("value") or f"hello from connects at {time.time()}"

        if operation == "put":
            client.put((self.settings.namespace, self.settings.set_name, key), {bin_name: value})
            return QueryResult(ok=True, data={"operation": "put", "key": key}, latency_ms=0.0)

        _, _, bins = client.get((self.settings.namespace, self.settings.set_name, key))
        return QueryResult(ok=True, data={"key": key, "bins": bins}, latency_ms=0.0)

    def public_info(self) -> dict:
        info = super().public_info()
        info["namespace"] = self.settings.namespace
        info["set"] = self.settings.set_name
        info["endpoint"] = f"{self.settings.host}:{self.settings.port}"
        return info