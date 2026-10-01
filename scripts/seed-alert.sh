#!/usr/bin/env bash
# POST a synthetic Grafana alert to the backend webhook to exercise the
# OpenSRE bridge.
#   scripts/seed-alert.sh [webhook-url]
set -euo pipefail

WEBHOOK_URL="${1:-http://localhost:30081/api/v1/alerts}"

payload=$(cat <<'JSON'
{
  "status": "firing",
  "labels": {
    "alertname": "ConnectorUnavailable",
    "severity": "critical",
    "connector": "yugabyte",
    "environment": "production"
  },
  "annotations": {
    "summary": "Yugabyte connector is down",
    "description": "demo_connector_up == 0 — the Yugabyte connector health check is failing"
  },
  "fingerprint": "seed-$(date +%s)",
  "title": "[FIRING:1] ConnectorUnavailable critical - yugabyte",
  "message": "Connector yugabyte is not reachable. See /healthz.",
  "state": "alerting"
}
JSON
)

curl -sf -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$payload" | jq . || python -m json.tool

echo "Alert seeded to $WEBHOOK_URL"