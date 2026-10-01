# One-time environment setup for Windows (or Windows PowerShell on WSL2).
# Installs / verifies: podman, kind, kubectl, opensre.
# Run from the repository root:  scripts\setup-windows.ps1
$ErrorActionPreference = "Stop"

function Test-Tool($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Show-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

Show-Step "Checking required tools..."

# ---- podman -------------------------------------------------------------
if (Test-Tool "podman") {
    Write-Host "  podman: OK ($(podman --version))"
} else {
    Show-Step "podman not found. Installing via winget..."
    if (Test-Tool "winget") {
        winget install -e --id RedHat.Podman --accept-package-agreements --accept-source-agreements
        Write-Host "  podman installed. Initializing the machine (WSL2 backend)..."
        podman machine init
        podman machine start
    } else {
        Write-Host "  winget not available. Install Podman Desktop / podman manually from https://podman.io/docs/installation"
    }
}

# ---- kind ---------------------------------------------------------------
if (Test-Tool "kind") {
    Write-Host "  kind: OK ($(kind version | Select-Object -First 1))"
} else {
    Show-Step "kind not found. Downloading kind.exe from GitHub releases..."
    $release = Invoke-RestMethod "https://api.github.com/repos/kubernetes-sigs/kind/releases/latest"
    $asset = $release.assets | Where-Object { $_.name -like "kind-windows-amd64*" } | Select-Object -First 1
    if (-not $asset) { throw "Could not find kind-windows-amd64 asset in latest release" }
    $dest = Join-Path $env:LOCALAPPDATA "bin\kind.exe"
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $dest
    [Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path", "User") + ";$env:LOCALAPPDATA\bin", "User")
    Write-Host "  kind installed to $dest (new terminals will pick it up)."
}

# ---- kubectl ------------------------------------------------------------
if (Test-Tool "kubectl") {
    Write-Host "  kubectl: OK ($(kubectl version --client --output=json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty clientVersion | Select-Object -ExpandProperty gitVersion))"
} else {
    Write-Host "  kubectl: not found. It is usually bundled with Docker Desktop; otherwise run: winget install -e --id Kubernetes.kubectl"
}

# ---- opensre ------------------------------------------------------------
if (Test-Tool "opensre") {
    Write-Host "  opensre: OK"
} else {
    Show-Step "opensre not found. Installing (https://install.opensre.com)..."
    Write-Host "  Run:  irm https://install.opensre.com | iex"
    Write-Host "  Then run:  opensre onboard   (choose your LLM provider + model)"
}

Show-Step "Done."
Write-Host @"

Next steps:
  1. Restart your terminal so PATH changes apply.
  2. podman machine start            (if you just installed podman)
  3. Copy-Item .env.example .env     (edit values as needed)
  4. scripts\deploy-compose.ps1      # local demo via podman compose
     -- or --
     scripts\deploy-kind.ps1         # kubernetes demo via kind + podman
  5. opensre onboard                 # configure the OpenSRE CLI
     opensre investigate -i opensre\alerts\example-alert.json
"@