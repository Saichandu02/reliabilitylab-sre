# Postmortem — Local dependency-outage exercise (2026-10-31)

This postmortem covers the **executed local lab exercise**
(`scripts/exercise.py`, evidence in `docs/evidence/exercise-latest.json`).
It is a planned fault-injection exercise against a simulated dependency,
not a production incident, and not a Kubernetes incident.

## Summary

With lab mode enabled, the dependency was toggled down inside the app
process. Readiness failed immediately, business endpoints returned 503,
liveness stayed green, the dependency metric dropped to 0, and both
alert conditions evaluated as *would fire*. On recovery, readiness
returned, traffic succeeded with zero errors, and a pre-fault order was
still retrievable — including after a full process restart.

## Timeline (UTC, 2026-10-31, from the exercise evidence)

| Time | Event |
|---|---|
| 08:17:32.939 | Server started (uvicorn, local lab mode, fresh SQLite DB) |
| 08:17:33.562 | Baseline done: 40 requests, 0 errors, p50 5.65 ms, p95 66.76 ms |
| 08:17:35.644 | Latency phase done: 300 ms injected latency → p50 306.24 ms, p95 316.31 ms over 8 requests; latency then cleared |
| 08:17:35.644 | **Fault injected:** `POST /lab/dependency/down` |
| 08:17:35.948 | Fault observed: readiness returned 503 within 4.1 ms of polling; 16 fault-phase requests → 12× 503 (order routes), 4× 200 (`/api/status` reporting `degraded`, by design); `/healthz` still 200; `dependency_up` = 0 |
| 08:17:35.948 | Alert evaluation: `DependencyDown` would fire (dependency_up == 0); `HighErrorRate` would fire (fault-phase 5xx rate 75% > 25% threshold) |
| 08:17:35.948 | **Recovery:** `POST /lab/dependency/up` |
| 08:17:36.271 | Recovery verified: readiness 200 within 4.0 ms of polling; 20 requests, 0 errors, p50 4.94 ms; pre-fault order retrievable |
| 08:17:36.528 | Server process stopped deliberately (restart phase) |
| 08:17:40.652 | Restarted server: pre-fault order still retrievable; order count 18 (all orders created across phases) |

## Detection and recovery times — read carefully

- The 4.1 ms / 4.0 ms figures are **in-process readiness poll**
  observations (200 ms poll interval, state change is immediate), not
  Prometheus alert latency. In a Prometheus deployment the
  `DependencyDown` alert additionally needs its 15 s `for:` duration
  plus a scrape interval; the rule logic itself is verified separately
  by `promtool test rules` (SUCCESS).
- No monthly availability or uptime percentage is inferred from this
  ~8-second exercise.

## What worked

- Liveness/readiness separation: no restart behaviour during the
  outage; the process stayed up and diagnosable via `/api/status`.
- Metrics told the story without logs: `dependency_up`, status-class
  counts, and the fault-phase error rate all moved as designed.
- Persistence: nothing written during the outage, nothing lost across
  recovery or restart.

## What this did not prove

- Real database failure modes (connection storms, disk full, slow
  queries against Postgres) — the dependency was simulated.
- Kubernetes behaviour (pod kill, rollout of a broken version) — those
  exercises are documented in the runbooks and remain config-only on
  this machine (no Docker/kind).
- Alertmanager delivery — routing config targets a local webhook sink;
  no live Prometheus/Alertmanager ran here.

## Follow-ups

- Run exercises A/B/C in kind where Docker is available and replace
  this postmortem's local timeline with the cluster one.
- Run the Compose stack and repeat the exercise against Postgres.
