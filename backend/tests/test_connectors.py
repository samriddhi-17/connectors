async def test_list_connectors(client):
    resp = await client.get("/api/connectors")
    assert resp.status_code == 200
    body = resp.json()
    names = {c["name"] for c in body["connectors"]}
    assert names == {"aerospike", "yugabyte"}
    for c in body["connectors"]:
        assert c["status"] in {"ok", "degraded", "unavailable"}


async def test_connector_detail(client):
    resp = await client.get("/api/connectors/aerospike")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "aerospike"
    assert body["kind"] == "aerospike"


async def test_connector_detail_missing(client):
    resp = await client.get("/api/connectors/does-not-exist")
    assert resp.status_code == 404


async def test_query_unknown_connector(client):
    resp = await client.post("/api/query/nope", json={"operation": "get", "payload": {}})
    assert resp.status_code == 404


async def test_query_yugabyte_unreachable_is_502(client):
    resp = await client.post(
        "/api/query/yugabyte", json={"operation": "upsert", "payload": {"key": "a", "value": "b"}}
    )
    assert resp.status_code == 502
    assert "detail" in resp.json()


async def test_query_aerospike_unsupported_operation(client):
    resp = await client.post(
        "/api/query/aerospike", json={"operation": "explode", "payload": {}}
    )
    assert resp.status_code == 502
    assert "unsupported operation" in resp.json()["detail"]