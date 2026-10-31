# ReliabilityLab — Observable Service and Incident Recovery

A small order API built to demonstrate SRE practice, not just an app:
**a failure is caused on purpose, detected by readiness/metrics/alert
rules, diagnosed with structured logs, and recovered — with timestamped
evidence.** Personal project; all orders are fictional.

![status](docs/screenshot.txt) — text capture of the running app
(a rendered screenshot is pending; see `docs/demo.md`).

**Live demo:** local only — no public deployment exists.
Verified local URL during the build: `http://127.0.0.1:8000/` when
started with the quickstart below. Public deployment: **pending**
(route prepared in `docker-compose.yml`, needs a deployment account).

## Three concrete capabilities

1. **Observable by default** — Prometheus metrics with bounded labels
   (request count, duration histogram, `dependency_up`, build info),
   one structured JSON log line per request keyed by request ID,
   provisioned Grafana dashboard, and alert rules that are unit-tested
   with `promtool` *and* evaluated against recorded incident evidence.
2. **Failure + recovery, exercised** — a local lab mode injects a
   dependency outage and latency; the run records baseline vs fault vs
   recovery traffic, readiness detection, alert conditions, and proves
   orders persist through recovery and a process restart
   (`docs/evidence/exercise-latest.json`,
   `docs/postmortem-local-exercise.md`).
3. **Liveness ≠ readiness** — `/healthz` never touches the DB, so a
   dependency outage makes the service unready without restart-looping
   it; `/readyz` reflects the dependency.

## Architecture

See `docs/architecture.md`. FastAPI + SQLite (local) / Postgres
(Compose topology), Prometheus + Alertmanager + Grafana, Helm chart
for kind/Kubernetes, k6 load script (plus a Python load runner).

```text
user ─▶ FastAPI (orders, status page, probes, metrics)
          │            ├─▶ SQLite file (local persistence)
Prometheus┘ (scrape)   └─▶ structured JSON logs (request IDs)
   └─ alerts.yml ─▶ Alertmanager ─▶ local webhook sink
Grafana ◀─ Prometheus (provisioned dashboard)
```

## Quickstart (Docker-free local)

```bash
bash scripts/bootstrap.sh                 # venv + deps (PowerShell: scripts/bootstrap.ps1)
DATABASE_PATH=data/orders.db RELIABILITYLAB_LAB_MODE=true \
  .venv/bin/uvicorn app.main:app --port 8000
# UI:        http://127.0.0.1:8000/
# OpenAPI:   http://127.0.0.1:8000/docs
# Windows:   $env:DATABASE_PATH='data/orders.db'; $env:RELIABILITYLAB_LAB_MODE='true'; .\.venv\Scripts\uvicorn app.main:app --port 8000
```

If port 8000 is busy, pass another `--port` (e.g. `8010`) and use that
in the URLs. Full stack (app + Postgres + Prometheus + Grafana +
Alertmanager): `docker compose up --build` — admin tools bind to
loopback only; lab mode is **off** in Compose by default.

## API examples

```bash
curl -X POST localhost:8000/api/orders -H 'Content-Type: application/json' \
  -d '{"item":"widget","quantity":2,"unit_price_minor":1500,"customer_ref":"demo-customer"}'
# 201 {"id":"…","item":"widget","quantity":2,"unit_price_minor":1500,
#      "total_minor":3000,"customer_ref":"demo-customer",
#      "status":"created","created_at":"…"}

curl localhost:8000/api/orders/<id>
curl localhost:8000/api/status
curl localhost:8000/healthz   # liveness (process only)
curl localhost:8000/readyz    # readiness (dependency)
curl localhost:8000/metrics
```

Endpoint contract: `GET /healthz`, `GET /readyz`, `GET /metrics`,
`POST /api/orders`, `GET /api/orders/{id}`, `GET /api/orders`,
`GET /api/status`. Lab-only (`RELIABILITYLAB_LAB_MODE=true`,
loopback/token-guarded): `POST /lab/dependency/down|up`,
`POST /lab/latency`.

## Run the incident exercise

```bash
.venv/bin/python scripts/exercise.py      # baseline → latency → outage → recovery → restart
.venv/bin/python scripts/rule_test.py --phases-file docs/evidence/exercise-latest.json
BASE_URL=http://127.0.0.1:8000 .venv/bin/python scripts/smoke_test.py   # server running
.venv/bin/python scripts/load_test.py --base-url http://127.0.0.1:8000 --requests 100 --concurrency 5
```

## Tests and measured results (2026-10-31, this VM)

- `pytest`: **13 passed** (API, persistence across restart, readiness
  during outage, metric label bounds).
- Exercise: baseline 40 req / 0 errors (p95 66.76 ms) → fault 16 req /
  75% 5xx with `/healthz` still 200 and `dependency_up=0` → recovery
  20 req / 0 errors; pre-fault order survived recovery **and** a
  process restart (order count 18).
- Alert rules: `promtool check rules` SUCCESS (5 rules);
  `promtool test rules` SUCCESS; thresholds also pass against the
  recorded exercise evidence.
- Load (Python runner, 100 req, concurrency 5, shared 4-core VM):
  0 errors, p50 79.54 ms, p95 113.54 ms — a sanity load, not capacity.
- Full detail, including everything that did **not** run (Docker,
  Kubernetes exercises, live Prometheus/Grafana, k6), is in
  `docs/verification.md`. SLIs/SLOs: `docs/slo.md`. Runbooks:
  `docs/runbooks/`. Postmortem: `docs/postmortem-local-exercise.md`.

## Limitations and tradeoffs

- Local persistence is SQLite behind a repository seam; Compose
  provisions Postgres, but Postgres-specific behaviour is unverified
  here (no Docker on the build VM).
- The local outage is a *simulated* dependency inside the app process;
  Kubernetes pod-kill / broken-version exercises are documented and
  charted but were not executed here.
- SLOs in `docs/slo.md` are design targets; no long-term availability
  is measured or claimed.
- Fault injection is lab-only, off by default, and must never be
  enabled on a publicly reachable deployment.

## Repository topics / description

Description: *Observable order API with an exercised incident-recovery
lab: Prometheus/Grafana, tested alert rules, liveness/readiness
separation, and timestamped failure → detection → recovery evidence.*
Topics: `fastapi, sre, observability, prometheus, grafana, alerting,
incident-response, helm, kubernetes, reliability`

## Resume bullets (personal project, from measured evidence only)

- Built an observable FastAPI order service with bounded-label
  Prometheus metrics, structured request-ID logs, and liveness/readiness
  separation; verified with 13 passing tests and promtool-tested alert
  rules (5 rules, unit tests SUCCESS).
- Ran a recorded fault-injection exercise (dependency outage + 300 ms
  latency): fault-phase error rate hit 75% with liveness still green,
  recovery restored 0-error traffic, and orders persisted through
  recovery and a process restart — all evidenced with timestamps in
  the repo's postmortem.

## License

MIT — see `LICENSE`. All data is fictional; no third-party datasets.
