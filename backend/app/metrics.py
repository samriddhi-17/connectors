"""Prometheus metrics registry used by the app.

All collectors are registered on a private :class:`CollectorRegistry` so the
app can be instantiated multiple times (e.g. in tests) without colliding with
the global default registry.
"""
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest

QUERY_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class Metrics:
    def __init__(self, prefix: str) -> None:
        self.registry = CollectorRegistry()
        self.prefix = prefix

        self.connector_up = Gauge(
            f"{prefix}_connector_up",
            "Whether a connector's last health check succeeded (1) or not (0).",
            ["connector", "kind"],
            registry=self.registry,
        )
        self.connector_check_seconds = Histogram(
            f"{prefix}_connector_check_seconds",
            "Duration of connector health checks in seconds.",
            ["connector"],
            buckets=QUERY_BUCKETS,
            registry=self.registry,
        )
        self.connector_query_duration_seconds = Histogram(
            f"{prefix}_connector_query_duration_seconds",
            "Duration of connector data queries in seconds, by outcome.",
            ["connector", "status"],
            buckets=QUERY_BUCKETS,
            registry=self.registry,
        )
        self.connector_errors_total = Counter(
            f"{prefix}_connector_errors_total",
            "Total connector errors by error type.",
            ["connector", "error_type"],
            registry=self.registry,
        )
        self.http_requests_total = Counter(
            f"{prefix}_http_requests_total",
            "HTTP requests served by the app.",
            ["method", "path", "status"],
            registry=self.registry,
        )
        self.http_request_duration_seconds = Histogram(
            f"{prefix}_http_request_duration_seconds",
            "HTTP request latency in seconds.",
            ["method", "path"],
            buckets=QUERY_BUCKETS,
            registry=self.registry,
        )

    def render(self) -> bytes:
        return generate_latest(self.registry)

    @property
    def content_type(self) -> str:
        return CONTENT_TYPE_LATEST