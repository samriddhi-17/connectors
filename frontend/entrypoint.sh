#!/bin/sh
# Generates /config.json (consumed by src/main.jsx) from runtime environment
# variables so the frontend needs no build-time configuration.
set -e

: "${VITE_API_BASE:=}"
: "${VITE_GRAFANA_URL:=http://localhost:3000}"

cat > /usr/share/nginx/html/config.json <<EOF
{"apiBase": "${VITE_API_BASE}", "grafanaUrl": "${VITE_GRAFANA_URL}"}
EOF

exec "$@"