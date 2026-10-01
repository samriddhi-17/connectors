"""FastAPI application factory for the Connects demo.

Everything is wired from ``Settings`` (environment-driven); nothing here is
hard-coded. Creating the app with ``create_app(settings=...)`` lets tests
inject a specific configuration.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.api.routes import alerts_router, connectors_router, health_router, query_router
from app.config import Settings, get_settings
from app.connectors import build_connectors
from app.metrics import Metrics

# psycopg's async connections require a selector-based event loop on Windows;
# the default ProactorEventLoop breaks the Yugabyte connector there. This must
# be set before uvicorn creates its loop, which is guaranteed because uvicorn
# imports ``app.main:app`` before starting the loop.
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except (AttributeError, ValueError):  # pragma: no cover - non-Windows build
        pass


def configure_logging(settings: Settings) -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, settings.app.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return logging.getLogger(settings.app.app_name)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logger = configure_logging(settings)
    metrics = Metrics(settings.app.metrics_prefix)
    connectors = build_connectors(settings, logger, metrics)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        for connector in connectors.values():
            try:
                await connector.startup()
            except Exception as exc:  # noqa: BLE001
                logger.error("connector %s startup failed: %s", connector.name, exc)
        yield
        for connector in connectors.values():
            try:
                await connector.shutdown()
            except Exception as exc:  # noqa: BLE001
                logger.error("connector %s shutdown failed: %s", connector.name, exc)

    app = FastAPI(
        title=settings.app.app_name,
        version=settings.app.version,
        description="Connects demo: React + FastAPI, Aerospike & Yugabyte connectors, Grafana, and an OpenSRE alert bridge.",
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.logger = logger
    app.state.metrics = metrics
    app.state.connectors = connectors

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def http_metrics(request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration = time.perf_counter() - start
        path = request.url.path
        metrics.http_requests_total.labels(method=request.method, path=path, status=response.status_code).inc()
        metrics.http_request_duration_seconds.labels(method=request.method, path=path).observe(duration)
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint() -> Response:
        return Response(content=metrics.render(), media_type=metrics.content_type)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "app": settings.app.app_name,
            "version": settings.app.version,
            "docs": "/docs",
            "health": "/healthz",
            "metrics": "/metrics",
        }

    app.include_router(health_router)
    app.include_router(connectors_router)
    app.include_router(query_router)
    app.include_router(alerts_router)

    return app


app = create_app()