# Runbook — Pod / process restart and recovery (Exercise A)

**Goal:** prove the service recovers from a restart and orders persist.
Kubernetes form (kind): this exercise is **config-only on machines
without Docker/kind**; the local process-restart form below is what
`scripts/exercise.py` executes automatically (phase 5).

## Kubernetes form

```bash
kubectl -n lab get pods
kubectl -n lab delete pod -l app=reliabilitylab   # force a restart
kubectl -n lab rollout status deploy/lab-reliabilitylab
curl -s localhost:8000/readyz                      # via port-forward
curl -s localhost:8000/api/orders/<pre-restart-id> # must still exist
```

Watch in Grafana: process-start panel jumps, traffic dips, readiness
returns, error rate stays flat after recovery.

## Local form (executed)

`scripts/exercise.py` starts the server, creates a durable order,
terminates the process, restarts it against the same SQLite file, and
asserts the order is still retrievable and the order count is intact.
Evidence: `docs/evidence/exercise-latest.json` → `phases.restart`.

## If recovery fails

- Readiness 503 after restart → follow
  `docs/runbooks/dependency-outage.md` (the DB/volume is suspect, not
  the restart itself).
- Order missing → check `DATABASE_PATH` points at the persistent
  volume/file, not an ephemeral path; in Kubernetes check the PVC is
  bound and mounted at `/data`.
