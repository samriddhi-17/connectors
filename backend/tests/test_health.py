async def test_livez(client):
    resp = await client.get("/livez")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_healthz_reports_connectors(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert "connectors" in body
    assert "aerospike" in body["connectors"]
    assert "yugabyte" in body["connectors"]
    for name, info in body["connectors"].items():
        assert info["status"] in {"ok", "degraded", "unavailable"}


async def test_readyz_fails_when_databases_unreachable(client):
    resp = await client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json()["status"] == "not ready"


async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json()["app"] == "connects-test"


async def test_metrics_endpoint(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "test_demo_connector_up" in text
    assert "test_demo_http_requests_total" in text