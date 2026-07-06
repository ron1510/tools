# Varnish-Only REST Cache

This project deploys **Varnish Cache OSS** as a REST API cache with automatic, prefix-aware
invalidation rules written in VCL. There is no custom cache-router service.

Traffic flows through Varnish for reads and mutations:

```text
client / ingress -> Varnish -> backend
```

Varnish decides what to cache for `GET` requests. For mutation methods, Varnish derives invalidation
tags from the request path, bans matching cached objects, and then passes the mutation to the backend.

The default API prefix is `/api/v1`. The full URL including `/api/v1` remains part of the cache key,
while invalidation classification strips the prefix and uses the remaining REST resource family/id.

## Directory Layout

```text
charts/rest-cache/         Production Helm chart for Varnish
charts/rest-cache-lab/     Optional lab backend Helm chart
docs/                      Architecture, operations, and lab guide
lab/backend/               Small FastAPI backend for cache behavior testing
```

## Validate

```powershell
helm lint charts/rest-cache --set varnish.backend.host=my-api.default.svc.cluster.local
helm lint charts/rest-cache-lab
helm template rest-cache charts/rest-cache --set varnish.backend.host=my-api.default.svc.cluster.local
helm template rest-cache-lab charts/rest-cache-lab
helm template rest-cache charts/rest-cache --set varnish.backend.host=my-api.default.svc.cluster.local | kubeconform -strict -kubernetes-version 1.30.0

cd lab/backend
python -m pytest
python -m ruff check src tests
python -m mypy
```

`kubeconform` is optional but recommended when it is installed locally or in CI.
