# Kubernetes path (kind + Helm)

Config only on machines without Docker/kind — the commands below are
the documented exercise route, and `docs/verification.md` records
honestly whether they ran.

```bash
kind create cluster --config k8s/kind-config.yaml
docker build -t reliabilitylab:0.1.0 .
kind load docker-image reliabilitylab:0.1.0 --name reliabilitylab
helm lint charts/reliabilitylab
helm install lab charts/reliabilitylab --namespace lab --create-namespace
kubectl -n lab port-forward svc/lab-reliabilitylab 8000:8000
curl localhost:8000/healthz
```

Incident exercises (full steps in `docs/runbooks/`):
A. Delete a pod and watch readiness/recovery.
B. Deploy image tag `broken` (a version that fails readiness), observe
   alerts, roll back with `helm rollback`.
C. Scale the database / make it unavailable in the lab namespace only,
   observe readiness (not liveness) failing, then restore.

Monitoring in-cluster: install `kube-prometheus-stack` separately; the
app's Service carries Prometheus scrape annotations and the alert rules
in `prometheus/alerts.yml` can be loaded as a PrometheusRule.
