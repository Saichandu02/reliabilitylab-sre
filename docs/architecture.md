# Architecture — ReliabilityLab

```text
                         ┌─────────────────────────────┐
  user / demo page ─────▶│ FastAPI order API           │
                         │  /            status page   │
                         │  /api/orders  POST + GET    │
                         │  /api/status                │
                         │  /healthz  liveness (no DB) │
                         │  /readyz   readiness (DB)   │
                         │  /metrics  bounded labels   │
                         │  /lab/*    local lab only   │
                         └──────────────┬──────────────┘
                                        │
                              OrderStore (app/db.py)
                              local: SQLite file (persists)
                              compose/k8s: Postgres topology +
                              persistent volume (see decisions)
                                        │
  Prometheus ──scrape /metrics──▶ (app) │
  Prometheus ──rules alerts.yml──▶ Alertmanager ──webhook──▶ local sink
  Grafana ◀── Prometheus (provisioned datasource + dashboard JSON)
```

## Components

- **Order API** (`app/main.py`, `app/db.py`): fictional orders with
  integer minor-unit pricing, per-operation DB connections, request-ID
  middleware that emits one structured JSON log line per request and
  records count/duration metrics with bounded labels.
- **Observability**: Prometheus exposition on `/metrics`
  (`http_requests_total`, `http_request_duration_seconds`,
  `dependency_up`, `orders_created_total`, `app_build_info`, process
  metrics), alert rules in `prometheus/alerts.yml`, a provisioned
  Grafana dashboard, Alertmanager routing to a local webhook sink.
- **Local lab mode**: `RELIABILITYLAB_LAB_MODE=true` enables `/lab/*`
  routes that toggle a *simulated* dependency outage or latency inside
  the process. Disabled by default, 404 when off, loopback-or-token
  guarded, and never part of a public deployment.
- **Deployment shapes**: Docker Compose (app + Postgres + Prometheus +
  Grafana + Alertmanager, admin tools on loopback) and Helm/kind for
  the Kubernetes exercises. Both are configuration in this repo; which
  ones actually executed is recorded in `docs/verification.md`.

## Reliability choices that matter

- Liveness (`/healthz`) never touches the DB, readiness (`/readyz`)
  does — a dependency outage makes the service *unready*, not
  *restarting*, avoiding a restart loop during an outage.
- Orders persist in a file-backed store and survive process restarts
  (proven by test and by the exercise's restart phase).
- No high-cardinality metric labels: route templates only.
