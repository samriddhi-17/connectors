# Deploy the Connects demo to a kind cluster backed by podman.
#   scripts\deploy-kind.ps1
param(
    [string]$Cluster = "connects",
    [switch]$SkipBuild,
    [switch]$SkipRolloutWait
)
$ErrorActionPreference = "Stop"

$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

foreach ($tool in @("podman", "kind", "kubectl")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "'$tool' is required. Run scripts\setup-windows.ps1 first."
    }
}

if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Created .env from .env.example" }

# kind load docker-image is broken for the podman-only provider (kind v0.32
# inspects images with the docker CLI), so images are shipped via a local
# registry attached to the `kind` podman network. The cluster config marks it
# insecure (k8s/kind-config.yaml -> containerdConfigPatches).

$registry = "connects-registry"
$net = "kind"

# ---- local registry ----------------------------------------------------
if (-not (podman container exists $registry 2>$null)) {
    Write-Host "==> Starting local registry $registry ..."
    podman run -d --name $registry -p 127.0.0.1:5000:5000 docker.io/library/registry:2
} elseif (-not (podman container inspect $registry --format '{{.State.Running}}' 2>$null -eq "true")) {
    podman start $registry
}
if (-not (podman network exists $net)) {
    throw "podman network '$net' not found — create the kind cluster first."
}
podman network connect $net $registry 2>$null   # already-connected is a no-op error, ignore

# ---- build + push images (podman) --------------------------------------
if (-not $SkipBuild) {
    Write-Host "==> Building images with podman..."
    podman build -t connects-backend:local ./backend
    podman build -t connects-frontend:local ./frontend
    podman build -t connects-grafana:local ./grafana
}
Write-Host "==> Pushing images to $registry ..."
foreach ($img in @("backend", "frontend", "grafana")) {
    podman tag "localhost/connects-$img`:local" "localhost:5000/connects-$img`:local"
    podman push --tls-verify=false "localhost:5000/connects-$img`:local"
}

# ---- cluster ------------------------------------------------------------
$clusters = @(kind get clusters)
if ($clusters -notcontains $Cluster) {
    Write-Host "==> Creating kind cluster '$Cluster' with podman provider..."
    kind create cluster --name $Cluster --config k8s/kind-config.yaml --provider podman
} else {
    Write-Host "==> kind cluster '$Cluster' already exists."
}
podman network connect $net $registry 2>$null

# ---- config + secrets ---------------------------------------------------
Write-Host "==> Applying config and secrets..."
kubectl create namespace connects-demo --dry-run=client -o yaml | kubectl apply -f -
$secretFile = "k8s/secret.env"
if (-not (Test-Path $secretFile)) {
    Write-Warning "k8s/secret.env not found; using demo defaults from k8s/secret.env.example"
    $secretFile = "k8s/secret.env.example"
}
kubectl -n connects-demo create secret generic connects-secrets --from-env-file=$secretFile --dry-run=client -o yaml | kubectl apply -f -

# ---- manifests ----------------------------------------------------------
Write-Host "==> Applying manifests..."
kubectl apply -f k8s/namespace.yaml -f k8s/configmap.yaml -f k8s/backend.yaml -f k8s/frontend.yaml `
    -f k8s/prometheus.yaml -f k8s/grafana.yaml -f k8s/aerospike.yaml -f k8s/yugabyte.yaml

# ---- wait ---------------------------------------------------------------
if (-not $SkipRolloutWait) {
    Write-Host "==> Waiting for rollout..."
    kubectl -n connects-demo rollout status deploy/backend --timeout=240s
    kubectl -n connects-demo rollout status deploy/frontend --timeout=120s
    kubectl -n connects-demo rollout status deploy/grafana --timeout=120s
}

kubectl -n connects-demo get pods,svc

Write-Host @"

Connects demo is up on kind + podman.
  Frontend   http://localhost:30080
  Backend    http://localhost:30081  (docs: /docs)
  Grafana    http://localhost:30090  (admin / password from k8s\secret.env)
  Prometheus http://localhost:30091

  seed an alert:     scripts\seed-alert.ps1
  investigate:       opensre investigate -i opensre\alerts\<file>.json
  delete cluster:    kind delete cluster --name $Cluster
"@