#!/usr/bin/env bash
# Deploy the Connects demo to a kind cluster backed by podman (Linux / WSL2).
#   scripts/deploy-kind.sh [cluster-name]
set -euo pipefail

CLUSTER="${1:-connects}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for tool in podman kind kubectl; do
  command -v "$tool" >/dev/null || { echo "Missing '$tool' — run scripts/setup-windows.ps1 or install it."; exit 1; }
done

[ -f .env ] || cp .env.example .env

REGISTRY="connects-registry"
NET="kind"

# kind load docker-image is broken for the podman-only provider (kind inspects
# images with the docker CLI), so images are shipped via a local registry on
# the `kind` podman network (marked insecure in k8s/kind-config.yaml).

if ! podman container exists "$REGISTRY" 2>/dev/null; then
  echo "==> Starting local registry $REGISTRY ..."
  podman run -d --name "$REGISTRY" -p 127.0.0.1:5000:5000 docker.io/library/registry:2
fi
podman start "$REGISTRY" 2>/dev/null || true
podman network connect "$NET" "$REGISTRY" 2>/dev/null || true   # ignore "already connected"

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  echo "==> Building images with podman..."
  podman build -t connects-backend:local ./backend
  podman build -t connects-frontend:local ./frontend
  podman build -t connects-grafana:local ./grafana
fi

echo "==> Pushing images to $REGISTRY ..."
for img in backend frontend grafana; do
  podman tag "localhost/connects-${img}:local" "localhost:5000/connects-${img}:local"
  podman push --tls-verify=false "localhost:5000/connects-${img}:local"
done

if ! kind get clusters | grep -q "$CLUSTER"; then
  echo "==> Creating kind cluster '$CLUSTER' with podman provider..."
  kind create cluster --name "$CLUSTER" --config k8s/kind-config.yaml --provider podman
fi
podman network connect "$NET" "$REGISTRY" 2>/dev/null || true

echo "==> Applying config and secrets..."
kubectl create namespace connects-demo --dry-run=client -o yaml | kubectl apply -f -
SECRET_FILE="k8s/secret.env"
if [[ ! -f "$SECRET_FILE" ]]; then
  echo "k8s/secret.env not found; using demo defaults."
  SECRET_FILE="k8s/secret.env.example"
fi
kubectl -n connects-demo create secret generic connects-secrets --from-env-file="$SECRET_FILE" --dry-run=client -o yaml | kubectl apply -f -

echo "==> Applying manifests..."
kubectl apply -f k8s/namespace.yaml -f k8s/configmap.yaml -f k8s/backend.yaml -f k8s/frontend.yaml \
  -f k8s/prometheus.yaml -f k8s/grafana.yaml -f k8s/aerospike.yaml -f k8s/yugabyte.yaml

if [[ "${SKIP_ROLLOUT_WAIT:-0}" != "1" ]]; then
  echo "==> Waiting for rollout..."
  kubectl -n connects-demo rollout status deploy/backend --timeout=240s || true
  kubectl -n connects-demo rollout status deploy/frontend --timeout=120s || true
  kubectl -n connects-demo rollout status deploy/grafana --timeout=120s || true
fi

kubectl -n connects-demo get pods,svc

cat <<EOF

Connects demo is up on kind + podman.
  Frontend    http://localhost:30080
  Backend     http://localhost:30081  (docs: /docs)
  Grafana     http://localhost:30090
  Prometheus  http://localhost:30091

  seed an alert:  scripts/seed-alert.sh
  investigate:    opensre investigate -i opensre/alerts/<file>.json
  delete:         kind delete cluster --name $CLUSTER
EOF