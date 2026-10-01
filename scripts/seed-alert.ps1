# POST a synthetic Grafana alert to the backend webhook to exercise the
# OpenSRE bridge.
#   scripts\seed-alert.ps1 [-WebhookUrl http://localhost:30081/api/v1/alerts]
param(
    [string]$WebhookUrl = "http://localhost:30081/api/v1/alerts"
)

$payload = @{
    status = "firing"
    labels = @{
        alertname   = "ConnectorUnavailable"
        severity    = "critical"
        connector   = "yugabyte"
        environment = "production"
    }
    annotations = @{
        summary     = "Yugabyte connector is down"
        description = "demo_connector_up == 0 — the Yugabyte connector health check is failing"
    }
    startsAt      = (Get-Date).ToUniversalTime().ToString("o")
    fingerprint   = "seed-" + (Get-Random -Minimum 100000 -Maximum 999999)
    title         = "[FIRING:1] ConnectorUnavailable critical - yugabyte"
    message       = "Connector yugabyte is not reachable. See /healthz."
    state         = "alerting"
}

$json = $payload | ConvertTo-Json -Depth 6
try {
    $resp = Invoke-RestMethod -Method Post -Uri $WebhookUrl -ContentType "application/json" -Body $json
    Write-Host "Accepted. alert_id=$($resp.alert_id) file=$($resp.file)" -ForegroundColor Green
    Write-Host "opensre CLI: invoked=$($resp.opensre.invoked)"
} catch {
    Write-Error "Webhook failed: $_"
    exit 1
}