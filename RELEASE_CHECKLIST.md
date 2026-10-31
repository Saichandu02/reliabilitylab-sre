# Release checklist — ReliabilityLab

- [x] Tests pass locally (`pytest -q` — 13 passed, 2026-10-31)
- [x] Incident exercise run; evidence + postmortem committed
- [x] Alert rules checked and unit-tested with promtool
- [x] Helm chart linted and templated
- [x] Smoke test passes against a live server
- [x] README quickstart matches actual commands; sample request/response real
- [x] No secrets, tokens, or personal data in the repo; `.env.example` only
- [x] Config-only items labelled in `docs/verification.md` (nothing
      unexecuted is described as passed)
- [ ] CI workflow executed remotely (committed, not yet run on GitHub)
- [ ] Demo recording captured (script in `docs/demo.md`)
- [ ] Public deployment verified over HTTPS (pending an account)
- [ ] Tag `v0.1.0` after the items above that apply are done
