"""Shared pytest fixtures.

Connectors are pointed at unreachable loopback ports and tiny timeouts so the
test suite runs fast and exercises the graceful-degradation path (no real
Aerospike/Yugabyte databases required).
"""
from __future__ import annotations

import httpx
import pytest

from app.config import get_settings_for_testing
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return get_settings_for_testing(
        app={"app_name": "connects-test", "cors_origins": "*", "metrics_prefix": "test_demo"},
        aerospike={
            "enabled": True,
            "host": "127.0.0.1",
            "port": 39999,
            "connect_timeout_s": 0.2,
            "query_timeout_s": 0.2,
        },
        yugabyte={
            "enabled": True,
            "host": "127.0.0.1",
            "port": 39998,
            "connect_timeout_s": 0.2,
            "query_timeout_s": 0.2,
            "pool_min": 1,
            "pool_max": 1,
        },
        opensre={"alerts_dir": str(tmp_path / "alerts")},
    )


@pytest.fixture
def app(settings):
    return create_app(settings=settings)


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c