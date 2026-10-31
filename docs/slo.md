# SLIs and SLOs — ReliabilityLab

These are **design targets for this portfolio service**, measured over
the windows below. A short local exercise does not establish monthly
availability, and no long-term uptime percentage is claimed anywhere in
this repository.

## Availability SLI

- **Definition:** proportion of *eligible* requests that succeed.
  - Eligible: requests to `/api/*` plus `/readyz`.
  - Successful: HTTP status < 500.
  - Excluded: `/healthz`, `/metrics`, `/`, and lab routes (`/lab/*`) —
    health/metrics traffic would swamp product traffic, and lab routes
    exist to *cause* failures.
- **Measurement:** Prometheus, from `http_requests_total{route, status}`
  (bounded labels; see `app/main.py`).
- **Window:** rolling 30 days for the SLO; 2 minutes for the
  `HighErrorRate` alert (a paging signal, not the SLO itself).
- **Target (SLO):** 99.9% successful eligible requests over 30 days.
- **No-traffic behaviour:** with zero eligible requests the ratio is
  undefined, not 100%. Dashboards show "no data" in that case and the
  error-rate alert cannot fire — absence of traffic is not success.

## Latency SLI

- **Definition:** proportion of eligible requests (same set as above)
  completed in ≤ 300 ms, measured server-side by
  `http_request_duration_seconds`.
- **Target (SLO):** 95% of eligible requests ≤ 300 ms over 30 days
  (equivalently p95 ≤ 300 ms at steady traffic).
- **Alert threshold:** p95 > 1 s over 5 m (`HighLatencyP95`) — a
  deliberately looser, paging-level threshold than the SLO so ordinary
  jitter does not page.

## Dependency availability

- `dependency_up` (1/0) is a *diagnostic* signal, not a user-facing
  SLI. It exists so an incident can be attributed quickly:
  `DependencyDown` + readiness failing + liveness green = dependency
  problem, not a process problem.

## Error budget (design)

99.9% over 30 days ≈ 43 minutes of full outage equivalent. This number
is arithmetic from the target, **not** a measured result.
