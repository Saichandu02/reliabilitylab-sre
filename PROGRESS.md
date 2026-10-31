# Progress — ReliabilityLab

## Done (2026-10-31, executed on this VM)
- [x] FastAPI order API: orders CRUD subset, status page, /healthz vs
      /readyz separation, bounded-label /metrics, request-ID JSON logs
- [x] SQLite persistence (OrderStore seam); persistence-across-restart test
- [x] Local lab mode: dependency down/up + latency toggles, guarded
      (off = 404, loopback/token), used only for exercises
- [x] pytest: 13 passed (API, readiness/outage, latency, metrics, persistence)
- [x] Incident exercise executed end-to-end: baseline → +300 ms latency
      → dependency outage → recovery → process restart; evidence JSON
      + postmortem written from the real timeline
- [x] Alert rules (5) — promtool check + promtool test SUCCESS;
      rule_test.py passes against recorded exercise evidence
- [x] Grafana dashboard JSON (7 panels) + provisioning; Prometheus and
      Alertmanager (local webhook) configs validated
- [x] Helm chart lint + template clean; kind config written
- [x] Smoke test PASS on a live server; bounded Python load run
      (100 req, c5, 0 errors); k6 script written
- [x] Docs: README, architecture, demo, decisions, verification, SLOs,
      3 runbooks, postmortem, release checklist

## Config-only / pending (honest boundaries)
- [ ] Docker Compose stack execution — no Docker on this VM
- [ ] Kubernetes exercises A (pod kill), B (broken version + rollback),
      C against a real DB in kind — no Docker/kind here; runbooks +
      chart are ready, app-level equivalents were executed instead
- [ ] Live Prometheus scrape + Alertmanager delivery + Grafana UI
- [ ] k6 run (script ready; Python runner used here)
- [ ] Public deployment (needs an authorized account) and demo recording

## Resume point
If resuming: run the Compose stack first, then the kind exercises,
and update docs/verification.md + the postmortem with cluster evidence.
Do not edit the recorded local numbers.
