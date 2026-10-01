"""Build the connector registry from configuration.

Connectors are created lazily per enabled entry in ``Settings``. The registry
is a plain dict keyed by connector name so the API layer can look connectors
up without any hard-coded assumptions beyond the config-driven names.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.connectors.base import Connector

if TYPE_CHECKING:
    import logging

    from app.config import Settings
    from app.metrics import Metrics


def build_connectors(settings: Settings, logger: logging.Logger, metrics: Metrics) -> dict[str, Connector]:
    connectors: dict[str, Connector] = {}

    if settings.aerospike.enabled:
        from app.connectors.aerospike import AerospikeConnector

        connectors[AerospikeConnector.name] = AerospikeConnector(settings.aerospike, logger, metrics)

    if settings.yugabyte.enabled:
        from app.connectors.yugabyte import YugabyteConnector

        connectors[YugabyteConnector.name] = YugabyteConnector(settings.yugabyte, logger, metrics)

    return connectors