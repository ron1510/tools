# Operations

## Deploy

Validate first:

```powershell
helm lint charts/rest-cache
helm template rest-cache charts/rest-cache --set varnish.backend.host=my-api.default.svc.cluster.local
```

Install against a real backend:

```powershell
helm upgrade --install rest-cache charts/rest-cache `
  --set varnish.backend.host=my-api.default.svc.cluster.local `
  --set varnish.backend.port=8080
```

Install with the separate lab backend:

```powershell
helm upgrade --install rest-cache-lab charts/rest-cache-lab
helm upgrade --install rest-cache charts/rest-cache `
  --set varnish.backend.host=rest-cache-lab.default.svc.cluster.local
```

For a real service, set `varnish.backend.host` and `varnish.backend.port` in chart values.

## OpenShift Notes

The chart is designed to let OpenShift restricted SCC assign the runtime UID/GID. By default it does
not render `podSecurityContext` or container `securityContext` fields. Configure those later in your
environment-specific values if your platform team requires explicit settings.

Varnish listens on container port `6081`, not `80`:

```text
container: 0.0.0.0:6081
service:   port 80 -> targetPort varnish -> 6081
```

This matters because OpenShift normally runs containers as non-root. Non-root processes cannot bind
privileged ports below `1024`, so binding Varnish directly to `:80` can fail with:

```text
could not get socket :80 permission denied
```

Do not override Varnish args to `-a 0.0.0.0:80` unless you also deliberately grant the container
the privileges needed to bind low ports.

## Existing Varnish Charts

Varnish Software publishes an official Helm chart, but the current documentation describes it as
covering Varnish Enterprise, Varnish Controller, and Controller Router. It also documents Enterprise
image pull-secret and license workflows. This project uses Varnish Cache OSS, so it ships a small
local chart instead.

If you later move to Varnish Enterprise, port the generated VCL into the upstream chart's
`server.vclConfig` value.

## Inspect

Check rollout:

```powershell
kubectl rollout status deployment/rest-cache-varnish
kubectl get pods -l app.kubernetes.io/name=rest-cache
kubectl get endpoints rest-cache
```

Port-forward Varnish:

```powershell
kubectl port-forward svc/rest-cache 8080:80
```

Then call through the cache:

```powershell
curl.exe -i http://127.0.0.1:8080/api/v1/resources/123
```

Responses include:

```text
X-Cache: MISS
X-Cache: HIT
```

## Tuning

Primary knobs in VCL:

- `beresp.ttl`: long fallback bound for cached objects
- `beresp.grace`: stale object availability while refetching
- dependency mapping in `invalidate_for_mutation`

Primary Kubernetes knobs:

- Varnish memory storage argument: `-s malloc,256m`
- container memory limit
- CPU request

Keep `replicas: 1` unless an invalidation fanout mechanism is added.

## Safety Defaults

The VCL caches GET responses by host and normalized URL only. It intentionally ignores auth,
tenant, user-scope, and cookie request headers for GET cache identity.

The VCL bypasses or avoids storing cache for:

- paths outside `/api/v1`
- non-2xx backend responses
- responses with `Set-Cookie`

These defaults assume cached GET responses are safe to share for the same URL.

## Validation

Run schema validation:

```powershell
helm template rest-cache charts/rest-cache --set varnish.backend.host=my-api.default.svc.cluster.local
```

If available:

```powershell
helm template rest-cache charts/rest-cache --set varnish.backend.host=my-api.default.svc.cluster.local | kubeconform -strict -kubernetes-version 1.30.0
```

Run lab backend checks:

```powershell
cd lab/backend
python -m pytest
python -m ruff check src tests
python -m mypy
```
