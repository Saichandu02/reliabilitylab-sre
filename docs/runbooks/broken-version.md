# Runbook — Broken version deployed (Exercise B)

**Signals:** after a deploy, readiness probes fail / error rate spikes
while the previous version was healthy. In Kubernetes this is the
pod-level form of the local latency/outage exercises; it is
**config-only on machines without Docker/kind**.

## Diagnose

1. Confirm it is the deploy: `helm -n lab history lab` /
   `kubectl -n lab rollout history deploy/lab-reliabilitylab`, and
   compare the image tag + `BUILD_VERSION` (`/api/status`) with the
   last healthy release.
2. Check probe behaviour: a version that fails `/readyz` should get
   **no traffic** from the Service — if users are unaffected, the
   readiness separation is doing its job; a version that fails
   `/healthz` will restart-loop, which the logs will show.

## Recover (rollback)

```bash
helm -n lab rollback lab <last-good-revision>
kubectl -n lab rollout status deploy/lab-reliabilitylab
BASE_URL=http://127.0.0.1:8000 python3 scripts/smoke_test.py
```

Rollback is a return to a known-good chart + image, not a hand edit of
the running pod, so the fix survives the next reconcile.

## After

- Keep the broken tag quarantined; do not re-promote it.
- Record the timeline (deploy time, first alert, rollback time,
  recovery verification) in a postmortem like
  `docs/postmortem-local-exercise.md`.
