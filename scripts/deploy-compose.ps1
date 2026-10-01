# Local demo via podman compose.
#   scripts\deploy-compose.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Created .env from .env.example" }

# podman 4.7+ has a built-in compose ("podman compose"); fall back to podman-compose.
$composeCmd = "podman"
$composeArgs = @("compose")
if (-not (& podman compose version *> $null; $LASTEXITCODE -eq 0)) {
    if (Get-Command podman-compose -ErrorAction SilentlyContinue) {
        $composeCmd = "podman-compose"
        $composeArgs = @()
    } else {
        throw "Neither 'podman compose' nor 'podman-compose' is available."
    }
}

& $composeCmd @composeArgs up --build -d
if ($LASTEXITCODE -ne 0) { throw "compose up failed" }

Write-Host @"

Connects demo is starting...
  Frontend   http://localhost:8080
  Backend    http://localhost:8000  (docs: /docs)
  Grafana    http://localhost:3000  (admin / admin)
  Prometheus http://localhost:9090
  Aerospike  localhost:3000
  Yugabyte   localhost:5433

  seed an alert:    scripts\seed-alert.ps1
  investigate:      opensre investigate -i opensre\alerts\*.json
  stop:             $composeCmd $($composeArgs -join ' ') down
"@