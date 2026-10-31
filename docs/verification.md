# Verification — what actually ran (2026-10-31, this VM)

Environment: Python 3.12.3, 4 cores, ~8 GB RAM shared with other work.
**No Docker, no kind/kubectl** on this machine. Helm v3.16.2 and
Prometheus promtool v2.54.1 were downloaded as official static binaries
into `/tmp` for validation only (not committed). All timestamps UTC.

## Executed

### 1. Automated tests — 13 passed

```text
$ .venv/bin/python -m pytest -q
13 passed in 1.71s
```

Coverage: order create/get/list + validation, status page, request-ID
header, readiness during dependency outage (liveness green / readiness
503 / business 503 / recovery), lab endpoints 404 when lab mode is off,
simulated latency applies and clears, metric label bounds (no order IDs
or customer refs in `/metrics`, `dependency_up` follows the outage),
and **persistence across a restart** (new app instance, same DB file).

### 2. Incident exercise — PASS (app-level local lab, NOT Kubernetes)

```text
$ .venv/bin/python scripts/exercise.py
EXERCISE PASS — evidence written to docs/evidence/exercise-latest.json
```

Real run, 2026-10-31 08:17:32–08:17:40 UTC (server on an ephemeral
loopback port, fresh SQLite DB):

| Phase | Requests | Errors | p50 | p95 | Notes |
|---|---|---|---|---|---|
| Baseline | 40 | 0 | 5.65 ms | 66.76 ms | 10× 201 + 30× 200 |
| Latency +300 ms | 8 | 0 | 306.24 ms | 316.31 ms | injected latency visible 1:1 |
| **Fault (dependency down)** | 16 | **12 (75%)** | 5.11 ms | 73.37 ms | 12× 503 on order routes; 4× 200 are `/api/status` reporting `degraded` by design; `/healthz` stayed **200**; readiness 503 detected in **4.1 ms** of polling; `dependency_up` = **0.0** |
| Recovery | 20 | 0 | 4.94 ms | 68.96 ms | readiness 200 in **4.0 ms** of polling; pre-fault order retrievable |
| Process restart | — | — | — | — | server restarted on the same DB file; pre-fault order retrievable; order count **18** |

Alert evidence from that run:
`DependencyDown` would fire (`dependency_up == 0`) and `HighErrorRate`
would fire (75% > 25% threshold) — evaluated by
`scripts/rule_test.py --phases-file docs/evidence/exercise-latest.json`
→ `PASS: alert conditions match the recorded evidence`, and the same
fault metrics snapshot reported `dependency_up 0.0`.

**How to read the detection/recovery times:** they are in-process
readiness-poll observations. A live Prometheus adds scrape interval +
the rule's `for:` (DependencyDown: 15 s) before paging. No live
Prometheus ran here; the rule *logic* is verified by promtool below.
No uptime percentage is claimed from this ~8-second exercise.

### 3. Alert rules — promtool

```text
$ promtool check rules prometheus/alerts.yml
SUCCESS: 5 rules found
$ promtool test rules prometheus/alerts_test.yml   (run inside prometheus/)
Unit Testing: alerts_test.yml
  SUCCESS
$ promtool check config prometheus/prometheus.yml
SUCCESS (5 rules found via the config)
```

### 4. Smoke test against a live server — PASS

Server on port 8231 (lab mode off), then
`BASE_URL=http://127.0.0.1:8231 python scripts/smoke_test.py`:

```text
PASS: healthz ok / readyz ready / create order 201 / get order round-trip
PASS: status reports version + dependency up / metrics expose dependency_up
SMOKE PASS
```

Sample business request/response from that server class of run:

```text
POST /api/orders {"item":"smoke-widget","quantity":1,"unit_price_minor":999,"customer_ref":"smoke"}
→ 201 {"id":"<12-hex>","item":"smoke-widget","quantity":1,
       "unit_price_minor":999,"total_minor":999,
       "customer_ref":"smoke","status":"created","created_at":"<UTC ISO>"}
```

Structured logs: one JSON line per request, e.g.
`{"ts": "...", "level": "info", "request_id": "60a7349ffd724f1c", "method": "GET", "route": "/healthz", "status": 200, "duration_ms": 4.41}` —
106 request-ID log lines were recorded in the load-run server log.

### 5. Bounded load (Python runner; k6 not installed here)

```text
$ python scripts/load_test.py --base-url http://127.0.0.1:8231 \
    --requests 100 --concurrency 5
requests 100, concurrency 5, wall 1.61s, errors 0,
p50 79.54 ms, p95 113.54 ms, max 493.28 ms
```

Recorded in `docs/evidence/load-latest.json`. This is a small sanity
load on a shared 4-core VM against a single uvicorn worker with SQLite
writes — **not** a capacity result. The primary load script is
`load/k6.js` (thresholds p95 < 500 ms, error rate < 1%); k6 was not
available here, so it is config-only in this verification.

### 6. Helm + config validation

```text
$ helm lint charts/reliabilitylab
1 chart(s) linted, 0 chart(s) failed
$ helm template lab charts/reliabilitylab
→ ServiceAccount, PersistentVolumeClaim, Service, Deployment
  (runAsNonRoot: true, liveness /healthz, readiness /readyz,
   resource requests/limits from values)
```

YAML/JSON parsed OK: `docker-compose.yml`, Prometheus + Alertmanager
configs, Grafana provisioning, the Grafana dashboard JSON (7 panels:
traffic, error rate, p50/p95/p99, dependency, restarts, orders,
by-status), `k8s/kind-config.yaml`, and the CI workflow. That workflow
(`.github/workflows/ci.yml`) is committed but no remote CI run is
claimed as executed.

## Config-only — NOT executed, and why

| Item | Status | Reason |
|---|---|---|
| Docker Compose stack (app/Postgres/Prometheus/Grafana/Alertmanager) | Config only (YAML-validated) | No Docker on this VM |
| Exercise A in Kubernetes (pod kill) | Config/runbook only; app-level equivalent (process restart) **executed** in §2 | No Docker/kind/kubectl |
| Exercise B in Kubernetes (broken-version rollout + `helm rollback`) | Config/runbook only (`docs/runbooks/broken-version.md`) | No cluster |
| Exercise C against a real database (stop Postgres / real latency) | Simulated at app level and **executed** (§2); real-DB form config only | No Docker/Postgres here |
| Live Prometheus scraping + Alertmanager delivery | Config only; rules unit-tested with promtool, thresholds evaluated against recorded evidence | Prometheus server not run here (promtool only) |
| k6 load | Script only; Python load runner executed instead (§5) | k6 not installed |
| Grafana UI | Dashboard JSON + provisioning only | No Docker |
| Public deployment / demo video | Pending | No authorized deployment account; recording script in `docs/demo.md`; screenshot substitute in `docs/screenshot.txt` |

## Local completion statement

Local completion = the Docker-free path: venv + uvicorn + SQLite,
verified above (tests, exercise, smoke, load). Public deployment is
**pending**; the Compose / single-VM route (app behind HTTPS, admin
tools loopback-only, persistent volumes) is the prepared route and
requires a deployment account the build did not have.
