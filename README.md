# Connects — demo project

A small demo of a modern SRE stack: a **React + FastAPI** application with
**Aerospike** and **Yugabyte** connectors, observability via **Prometheus +
Grafana**, and automated incident investigation wired into
**[OpenSRE](https://github.com/Tracer-Cloud/opensre)**. Runs with
**podman-compose** locally or on **kind (Kubernetes)** using the podman
runtime.

Nothing in this project is hard-coded: every knob (hosts, ports, credentials,
features) is driven by environment variables, `.env`, ConfigMaps and Secrets.

```
                    ┌──────────────────────────────────────────────┐
                    │                 Browser                       │
                    └──────────────┬───────────────────────────────┘
                                   │ :8080 / :30080
                    ┌──────────────▼───────────────────────────────┐
                    │            frontend (React/Vite/nginx)       │
                    └──────────────┬───────────────────────────────┘
                                   │ /api · /metrics · /healthz (nginx proxy)
                    ┌──────────────▼───────────────────────────────┐
                    │              backend (FastAPI)               │
                    │  connectors:  aerospike · yugabyte           │
                    │  endpoints:   /healthz · /readyz · /metrics  │
                    │               /api/connectors · /api/query   │
                    │               /api/v1/alerts  (OpenSRE bridge)│
                    └──┬───────────┬──────────────┬────────────────┘
                       │           │              │
               Aerospike       Yugabyte      ┌────▼──────────────────────┐
               (:3000)         (:5433)       │  Prometheus               │
                                             └────┬──────────────────────┘
                                                  │ scrape /metrics
                                             ┌────▼──────────────────────┐
                                             │  Grafana                  │
                                             │  dashboards · alerting    │
                                             └────┬──────────────────────┘
                                                  │ webhook POST /api/v1/alerts
                                             ┌────▼──────────────────────┐
                                             │  OpenSRE (CLI)            │
                                             │  investigates alert JSON  │
                                             │  → RCA report             │
                                             └───────────────────────────┘
```

## Repo layout

| Path | What it is |
| --- | --- |
| `backend/` | FastAPI app: env-driven config, connector framework, Aerospike + Yugabyte connectors, Prometheus metrics, OpenSRE bridge. Tests included. |
| `frontend/` | React (Vite) dashboard that shows connector health and runs demo queries. Runtime config injected by nginx, not at build time. |
| `grafana/` | Grafana image with provisioned Prometheus datasource, demo dashboard, and alert rules that webhook into the OpenSRE bridge. |
| `prometheus/` | Prometheus scrape config. |
| `compose.yaml` | podman-compose stack (backend, frontend, prometheus, grafana, aerospike, yugabyte). |
| `k8s/` | kind cluster config (podman provider) + Kubernetes manifests (Deployments, Services, ConfigMaps, Secrets). |
| `opensre/` | OpenSRE integration guide, sample alert file, `integrations.example.json`. |
| `scripts/` | Windows + bash setup / deploy / seed scripts. |

## Requirements

- **podman** (4.7+, with a running machine — WSL2 backend on Windows)
- **kind** ≥ 0.20
- **kubectl**
- Python 3.11+, Node 18+ (only if you run the backend/frontend without containers)
- `opensre` CLI (for the incident-investigation part)

Install/verify them with `scripts\setup-windows.ps1`.

## 1. Run locally with podman compose

```powershell
Copy-Item .env.example .env        # edit values to taste
scripts\deploy-compose.ps1
```

| Service | URL |
| --- | --- |
| Frontend | http://localhost:8080 |
| Backend API docs | http://localhost:8000/docs |
| Grafana | http://localhost:3000 (`admin`/`admin`) |
| Prometheus | http://localhost:9090 |
| Aerospike | localhost:3000 |
| Yugabyte | localhost:5433 |

## 2. Run on Kubernetes (kind + podman)

```powershell
scripts\deploy-kind.ps1            # creates cluster, builds+pushes images via a local registry, applies manifests
```

| Service | URL |
| --- | --- |
| Frontend | http://localhost:30080 |
| Backend API docs | http://localhost:30081/docs |
| Grafana | http://localhost:30090 |
| Prometheus | http://localhost:30091 |

Manifests, the ConfigMap and the `connects-secrets` Secret are created from
`.env` / `k8s\secret.env` (copy from `secret.env.example`) by the script —
nothing is baked into images.

## Grafana

- Provisioned at startup from `grafana/provisioning/`:
  - Prometheus datasource (URL from `PROMETHEUS_URL`),
  - **Connects Demo** dashboard (connector up, error rate, query p95, HTTP requests),
  - alert rule **ConnectorUnavailable** (`demo_connector_up == 0` for 1m) that
    sends webhook notifications to `POST /api/v1/alerts` on the backend
    (`GRAFANA_ALERT_WEBHOOK_URL`).
- The dashboard + alerts keep working even if your local backend is flaky —
  connectors degrade gracefully (see below).

## OpenSRE integration

OpenSRE is the open-source AI SRE agent framework (RCA from alert JSON files).
Full guide: [`opensre/README.md`](opensre/README.md). In short:

```powershell
irm https://install.opensre.com | iex        # install CLI
opensre onboard                              # configure LLM provider
opensre integrations setup grafana           # point OpenSRE at the demo Grafana
opensre investigate -i opensre\alerts\example-alert.json
```

When Grafana fires an alert, the backend bridge (`app/opensre/bridge.py`)
converts the webhook payload into OpenSRE's alert schema and writes it under
`opensre/alerts/`. Set `OPENSRE_INVOKE_CLI=true` to auto-run
`opensre investigate -i`; otherwise investigate the files manually.

Trigger a synthetic alert any time with `scripts\seed-alert.ps1` (kind) or
`scripts\seed-alert.sh`.

## Connectors & graceful degradation

Both connectors implement `app/connectors/base.py` and are discovered from
`Settings` (no hard-coded names):

- **Aerospike** (`app/connectors/aerospike/`) — lazy-loads the `aerospike`
  client (it's a C extension that may not build everywhere). When the library
  is missing the connector reports `degraded` instead of breaking the app.
- **Yugabyte** (`app/connectors/yugabyte/`) — speaks the PostgreSQL wire
  protocol via `psycopg`. A small async connection pool; unreachable DBs
  report `unavailable`.

If a database is down, `/healthz` and `/api/connectors` keep serving with
per-connector status and the API returns `502` for queries against the
unreachable connector. `/readyz` returns `503` until everything is `ok`
(used by the Kubernetes readiness probe).

## "Nothing is hard-coded"

- Backend: `app/config.py` reads every value from the environment (`ENV_FILE`
  points at your env-file; default `.env`).
- Frontend: nginx entrypoint generates `/config.json` from `VITE_API_BASE` /
  `VITE_GRAFANA_URL` at container start (no build-time env, no baked URLs).
- Grafana: provisioning YAML uses `${VAR}` expansion with defaults.
- k8s: config in ConfigMaps, secrets in a Secret generated from
  `k8s/secret.env`.
- compose: `${VAR}` interpolation from `.env`.

## Tests

```powershell
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m pytest -q
```

15 tests cover health/readiness, the connector registry (graceful
degradation with no databases running), the query endpoint, and the OpenSRE
alert bridge (payload normalization + file persistence).

## Troubleshooting

- **Yugabyte connector error "cannot use the ProactorEventLoop"** — fixed by
  `backend/run.py`, which serves uvicorn with a selector loop factory on
  Windows. Always start the backend with `python run.py`, not bare `uvicorn`.
- **Grafana alert rules provisioning** targets Grafana 11 (`notification_settings`);
  on other major versions the default notification policy still routes every
  alert to the OpenSRE webhook.
- **Aerospike on Windows (dev)** — the client isn't installed; the connector
  reports `degraded`. In containers it installs from manylinux wheels.
- **OpenSRE can't find the CLI** — set `OPENSRE_INVOKE_CLI=false` (default)
  and run `opensre investigate -i <file>` yourself, or install the CLI inside
  the backend image.
