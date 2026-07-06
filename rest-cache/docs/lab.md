# Lab Guide

The lab backend is a small FastAPI service with an in-memory store. It exists only to test Varnish
cache behavior and invalidation rules.

## Deploy

The easiest way to start the full local lab is:

```powershell
.\scripts\start-lab.ps1
```

The script creates a `rest-cache-lab` kind cluster when needed, builds and loads the sample backend
image, installs both Helm charts, waits for rollout, and starts a background port-forward:

```text
http://127.0.0.1:8080 -> svc/rest-cache:80
```

Use a different local port if `8080` is already taken:

```powershell
.\scripts\start-lab.ps1 -LocalPort 18080
```

To keep the port-forward attached to the current terminal instead of starting it in the background:

```powershell
.\scripts\start-lab.ps1 -ForegroundPortForward
```

Run the cache behavior smoke test:

```powershell
.\scripts\smoke-test.ps1
```

The smoke test checks `MISS -> HIT`, normalized query caching, mutation invalidation, and the sample
`users -> permissions` dependency ban.

Manual equivalent:

```powershell
docker build -t rest-cache-lab-backend:e2e .\lab\backend
kind load docker-image rest-cache-lab-backend:e2e --name rest-cache-lab
helm upgrade --install rest-cache-lab charts/rest-cache-lab `
  --set image.repository=rest-cache-lab-backend `
  --set image.tag=e2e `
  --set image.pullPolicy=IfNotPresent
helm upgrade --install rest-cache charts/rest-cache `
  --set varnish.backend.host=rest-cache-lab.default.svc.cluster.local
kubectl rollout status deployment/rest-cache-lab
kubectl rollout status deployment/rest-cache-varnish
kubectl port-forward svc/rest-cache 8080:80
```

## Shared GET Cache

GET cache identity ignores auth, tenant, user-scope, and cookie request headers. The same host and
URL share one cached object across callers.

## Miss Then Hit

```powershell
curl.exe -i http://127.0.0.1:8080/api/v1/resources/123
curl.exe -i http://127.0.0.1:8080/api/v1/resources/123
```

Expected:

```text
first response:  X-Cache: MISS
second response: X-Cache: HIT
```

## Query Normalization

```powershell
curl.exe -i "http://127.0.0.1:8080/api/v1/resources?b=2&a=1"
curl.exe -i "http://127.0.0.1:8080/api/v1/resources?a=1&b=2"
```

Expected: the second request can hit the first cached object because VCL sorts query parameters.

## Resource and Collection Invalidation

Warm a resource and collection:

```powershell
curl.exe -i http://127.0.0.1:8080/api/v1/resources/123
curl.exe -i http://127.0.0.1:8080/api/v1/resources
```

Mutate the resource:

```powershell
curl.exe -i -X PUT -H "Content-Type: application/json" `
  -d "{\"name\":\"changed\"}" http://127.0.0.1:8080/api/v1/resources/123
```

Read again:

```powershell
curl.exe -i http://127.0.0.1:8080/api/v1/resources/123
curl.exe -i http://127.0.0.1:8080/api/v1/resources
```

Expected: both are cache misses after the mutation.

## Dependency Invalidation

The sample VCL maps:

```text
users -> permissions
resources -> users
```

This comes from `varnish.dependencyBans` in the main chart values. For the first rule,
`family: users` means "when any mutation targets `/api/v1/users...`", and
`collection:permissions` means "ban cached permission list/search responses". No concrete user id
or permission id is configured.

Warm permissions:

```powershell
curl.exe -i http://127.0.0.1:8080/api/v1/permissions
```

Mutate a user:

```powershell
curl.exe -i -X PUT -H "Content-Type: application/json" `
  -d "{\"name\":\"changed\"}" http://127.0.0.1:8080/api/v1/users/1
```

Read permissions again:

```powershell
curl.exe -i http://127.0.0.1:8080/api/v1/permissions
```

Expected: permissions is a miss because mutating `users` bans `collection:permissions`.
