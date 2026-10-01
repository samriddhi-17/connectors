GRAFANA_PAYLOAD = {
    "status": "firing",
    "labels": {
        "alertname": "ConnectorDown",
        "severity": "critical",
        "connector": "yugabyte",
    },
    "annotations": {
        "summary": "Yugabyte connector is down",
        "description": "The Yugabyte connector health check is failing",
    },
    "startsAt": "2026-08-14T00:00:00Z",
    "endsAt": "0001-01-01T00:00:00Z",
    "generatorURL": "http://grafana:3000/graph/abc",
    "fingerprint": "abc123",
    "title": "[FIRING:1] ConnectorDown critical",
    "state": "alerting",
    "message": "Connector yugabyte is not reachable",
    "orgID": 1,
    "dashboardURL": "http://grafana:3000/d/connectors",
    "panelURL": "http://grafana:3000/d/connectors/1",
}


async def test_ingest_alert_writes_opensre_file(client, settings):
    resp = await client.post("/api/v1/alerts", json=GRAFANA_PAYLOAD)
    assert resp.status_code == 202
    body = resp.json()
    assert body["accepted"] is True
    assert body["opensre"]["invoked"] is False

    from pathlib import Path

    files = list(Path(settings.opensre.alerts_dir).glob("*.json"))
    assert len(files) == 1


async def test_normalize_alert_matches_opensre_schema(client, settings):
    resp = await client.post("/api/v1/alerts", json=GRAFANA_PAYLOAD)
    assert resp.status_code == 202

    from pathlib import Path

    path = next(Path(settings.opensre.alerts_dir).glob("*.json"))
    import json

    alert = json.loads(path.read_text())
    assert "_meta" in alert
    assert alert["_meta"]["source"] == "grafana-alerting-webhook"
    entry = alert["alert"]["alerts"][0]
    assert entry["labels"]["alertname"] == "ConnectorDown"
    assert entry["status"] == "firing"
    assert entry["annotations"]["summary"] == "Yugabyte connector is down"
    assert alert["alert"]["commonLabels"]["connector"] == "yugabyte"
    assert alert["alert"]["alert_id"] == "abc123"


async def test_list_alerts(client, settings):
    await client.post("/api/v1/alerts", json=GRAFANA_PAYLOAD)
    resp = await client.get("/api/v1/alerts")
    assert resp.status_code == 200
    assert len(resp.json()["alerts"]) == 1


async def test_ingest_batched_alerts(client, settings):
    payload = {"alerts": [GRAFANA_PAYLOAD, {**GRAFANA_PAYLOAD, "fingerprint": "def456"}]}
    resp = await client.post("/api/v1/alerts", json=payload)
    assert resp.status_code == 202
    from pathlib import Path

    files = list(Path(settings.opensre.alerts_dir).glob("*.json"))
    assert len(files) == 1

    import json

    alert = json.loads(files[0].read_text())
    assert len(alert["alert"]["alerts"]) == 2