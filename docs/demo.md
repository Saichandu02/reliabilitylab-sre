# Demo — ReliabilityLab (60–90 second script)

Recording status: **pending** (no screen-recording tooling on the build
VM). The walkthrough below is exactly reproducible from the commands.

## Local quickstart (Docker-free)

```bash
bash scripts/bootstrap.sh
DATABASE_PATH=data/orders.db RELIABILITYLAB_LAB_MODE=true \
  .venv/bin/uvicorn app.main:app --port 8000
# open http://127.0.0.1:8000/  (status page + order form)
```

## Walkthrough

1. **Status page (0:00)** — open `/`, show `/api/status`: version,
   dependency `up`, order count.
2. **Create orders (0:10)** — submit the form twice; show the orders
   list and `GET /api/orders/{id}` in OpenAPI docs (`/docs`).
3. **Metrics (0:25)** — open `/metrics`; point at
   `http_requests_total` route *templates* (no order IDs) and
   `dependency_up 1`.
4. **Cause the failure (0:35)** —
   `curl -X POST localhost:8000/lab/dependency/down` then show
   `/readyz` → 503 while `/healthz` stays 200, order creation → 503,
   and `dependency_up 0` in `/metrics`.
5. **Recover (0:55)** —
   `curl -X POST localhost:8000/lab/dependency/up`; `/readyz` → 200,
   create another order, and re-open the pre-fault order to show it
   survived.
6. **Evidence (1:10)** — show `docs/verification.md` and
   `docs/evidence/exercise-latest.json`: baseline vs fault vs recovery
   numbers, and the postmortem timeline.

Automated version of steps 2–5: `.venv/bin/python scripts/exercise.py`.
