# Decisions — ReliabilityLab

1. **SQLite locally, Postgres in Compose topology.** Docker is not
   available on the build machine, so the executable path uses SQLite
   behind the `OrderStore` seam in `app/db.py` (one connection per
   operation, file-backed, restart-persistent). `docker-compose.yml`
   provisions PostgreSQL as the deployment database service alongside
   the app's persistent volume. Tradeoff: local tests prove persistence
   and outage behaviour, not Postgres-specific behaviour; that is
   stated in `verification.md` rather than hidden.
2. **Liveness ≠ readiness.** `/healthz` is process-only; `/readyz`
   checks the dependency. This is the single most important probe
   decision: coupling liveness to the DB would restart-loop every pod
   during a database outage.
3. **Simulated dependency, clearly named.** The local exercise toggles
   an in-process simulated dependency state (`/lab/*`, lab mode only).
   It exercises the *application's* response to an outage — readiness,
   503s, metrics, alerts, recovery — without pretending to be a real
   database failure or a Kubernetes pod kill. The k8s exercises that
   would prove those remain config-only here.
4. **Bounded metric labels.** Method, route template, status only.
   Order IDs and customer refs live in structured logs (by request ID),
   never in metrics.
5. **Alert rules tested two ways.** `promtool test rules` against
   synthetic series (CI), plus `scripts/rule_test.py` evaluating the
   same thresholds against the exercise's recorded evidence, so alert
   claims don't depend on a live Prometheus being up.
6. **`/api/status` stays up during an outage.** It reports
   `degraded/down` with a 200 so operators (and the demo page) can see
   state during an incident; business endpoints return 503.
7. **Small load, honest numbers.** The k6 script and the Python load
   runner are bounded sanity loads. Their results are quoted with
   request count, concurrency, and hardware, never as capacity claims.
8. **Admin surfaces stay private.** Prometheus, Grafana, Alertmanager
   and Postgres bind to loopback in Compose; only the app port is
   published. No external alert destination is configured by default.
