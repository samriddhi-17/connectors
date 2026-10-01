# OpenSRE integration

[OpenSRE](https://github.com/Tracer-Cloud/opensre) is the open-source AI SRE
agent framework. It investigates production incidents from **alert JSON
files**, querying your observability stack (Grafana, Prometheus, …) as
evidence, and produces a root-cause report.

This demo bridges Grafana Alerting into OpenSRE in three steps:

1. **Grafana fires an alert** (e.g. `demo_connector_up == 0`, provisioned in
   `grafana/provisioning/alerting/`).
2. The alert's webhook contact point POSTs to the backend
   `POST /api/v1/alerts`, which **normalizes it into OpenSRE's alert schema**
   and writes `opensre/alerts/<timestamp>_<alert_id>_<name>.json`
   (`app/opensre/bridge.py`).
3. If `OPENSRE_INVOKE_CLI=true` (and the `opensre` binary is on `PATH`), the
   bridge runs `opensre investigate -i <file>` automatically. Otherwise you
   run it manually (below).

## 1. Install the OpenSRE CLI

```powershell
irm https://install.opensre.com | iex          # Windows
curl -fsSL https://install.opensre.com | bash  # Linux / WSL2
```

## 2. Connect OpenSRE to the demo Grafana

```powershell
opensre onboard          # choose your LLM provider + model
opensre integrations setup grafana
# Instance URL:      http://localhost:30090   (kind) or http://localhost:3000 (compose)
# Service account token: create one in Grafana → Administration → Service accounts → Add
```

Or configure it declaratively by copying the template and editing:

```powershell
Copy-Item opensre\integrations.example.json .opensre\integrations.json
```

(You can also set the same values as env vars: `GRAFANA_INSTANCE_URL`,
`GRAFANA_READ_TOKEN`, `GRAFANA_VERIFY_SSL`. See
https://www.opensre.com/docs/grafana.)

Verify: `opensre integrations verify grafana`

## 3. Investigate an alert

```powershell
opensre investigate -i opensre\alerts\example-alert.json
# or any file written by the bridge:
opensre investigate -i opensre\alerts\*.json
```

The bridge output files are byte-compatible with the fixtures OpenSRE ships
for Kubernetes investigations (`tests/e2e/kubernetes/fixtures/*_alert.json`).

## Alert schema

Each bridge output matches OpenSRE's alert schema:

```jsonc
{
  "_meta": { "schema_version": 1, "source": "grafana-alerting-webhook", "captured_at": "…" },
  "alert": {
    "alerts": [ { "status": "firing", "labels": {…}, "annotations": {…},
                  "startsAt": "…", "endsAt": "…", "generatorURL": "…", "fingerprint": "…" } ],
    "version": "4", "title": "…", "state": "alerting", "message": "…", "alert_id": "…",
    "groupLabels": {…}, "commonLabels": {…}, "commonAnnotations": {…}, "groupKey": "…"
  },
  "evidence": {}
}
```

## Triggering a demo alert

Run `scripts\seed-alert.ps1` (kind) / `scripts\seed-alert.sh` (compose or
kind) to POST a synthetic Grafana alert straight to the webhook. Watch the
bridge write a new file under `opensre/alerts/`, then investigate it.