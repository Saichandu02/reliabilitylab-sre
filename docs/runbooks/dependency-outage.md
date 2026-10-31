# Runbook — Database dependency outage

**Signals:** `DependencyDown` alert, `HighErrorRate` alert,
`/readyz` → 503, `/healthz` → 200, `/api/status` shows
`dependency: down`, `dependency_up 0` in `/metrics`.

## Diagnose

1. Confirm scope: `curl -s localhost:8000/api/status` — if
   `dependency: down` but the process answers, this is a dependency
   incident, not an app crash. Do **not** restart the app first:
   restarts cannot fix a down database and liveness is green by design.
2. Check the database: Compose — `docker compose ps postgres`,
   `docker compose logs postgres`; Kubernetes —
   `kubectl -n lab get pods`, `kubectl -n lab logs deploy/<db>`.
3. Correlate in logs: app logs are JSON lines with `request_id`,
   `route`, `status`, `duration_ms`. Filter `status=503` and compare
   the first failing timestamp with database events.
4. Check for a lab cause first in local environments: is
   `RELIABILITYLAB_LAB_MODE` on, and did someone toggle
   `/lab/dependency/down`?

## Recover

1. Restore the database (restart the DB service/pod, fix disk /
   credentials / network as diagnosed).
2. Watch readiness, not liveness: `watch curl -s -o /dev/null -w
   '%{http_code}' localhost:8000/readyz` → expect 200.
3. Verify recovery with real traffic:
   `BASE_URL=http://127.0.0.1:8000 python3 scripts/smoke_test.py`.
4. Verify data: fetch an order created before the outage —
   `GET /api/orders/{id}` must return it (orders persist across the
   outage; the app writes nothing while the dependency is down).
5. Confirm alerts resolve (`dependency_up 1`, error rate decaying in
   Grafana) before closing the incident.

## Escalate if

Readiness stays 503 after the DB reports healthy (check app DB path /
DSN and volume mount), or orders are missing after recovery (stop and
preserve the DB volume before any cleanup — data loss outranks speed).
