# rest-cache Helm Chart

Helm chart for Varnish Cache OSS with REST-aware VCL invalidation.

## Why This Chart Is Local

Varnish Software publishes an official Helm chart, but the current documentation describes it as
covering Varnish Enterprise, Varnish Controller, and Controller Router. It also documents Enterprise
image pull-secret and license flows. This project uses the OSS `varnish` image, so the chart here is
small and self-contained.

The upstream chart still matters if you later choose Varnish Enterprise. It supports custom VCL via
`server.vclConfig`, and the REST VCL from this chart can be ported into that value.

## Install

```powershell
helm install rest-cache ./charts/rest-cache `
  --set varnish.backend.host=my-api.default.svc.cluster.local
```

Point Varnish at a real service:

```powershell
helm upgrade --install rest-cache ./charts/rest-cache `
  --set varnish.backend.host=my-api.default.svc.cluster.local `
  --set varnish.backend.port=8080
```

## Validate

```powershell
helm lint ./charts/rest-cache --set varnish.backend.host=my-api.default.svc.cluster.local
helm template rest-cache ./charts/rest-cache --set varnish.backend.host=my-api.default.svc.cluster.local
```

## Configuring Dependency Bans

The chart derives cache tags from the REST path shape. You configure dependencies by resource
family, not by concrete URL or id.

With `apiPrefix: /api/v1`, the family is the first segment after the prefix:

```text
/api/v1/users/123        -> family: users
/api/v1/resources/search -> family: resources
/api/v1/permissions      -> family: permissions
```

Varnish automatically assigns collection tags to cached GET responses:

```text
GET /api/v1/users
GET /api/v1/users?active=true
GET /api/v1/users/search?q=ron
-> collection:users

GET /api/v1/users/123
-> resource:users:123
-> collection:users
```

Same-family invalidation is automatic:

```text
PUT /api/v1/users/123
-> ban resource:users:123
-> ban collection:users

POST /api/v1/users
-> ban collection:users
```

`dependencyBans` is only for extra cross-family dependencies. For example, if changing a user can
change permission list/search responses, configure:

```yaml
varnish:
  dependencyBans:
    - family: users
      collectionKeys:
        - collection:permissions
```

That means:

```text
Any POST/PUT/PATCH/DELETE under /api/v1/users...
-> also ban every cached GET tagged collection:permissions
```

Do not put concrete ids in `collectionKeys`:

```yaml
# Good: family-level collection dependency.
collectionKeys:
  - collection:permissions

# Wrong: this chart does not configure per-id dependency rules here.
collectionKeys:
  - collection:permissions:123
  - /api/v1/permissions/123
```

If no other resource family depends on a mutation, leave `dependencyBans` empty. The chart still
handles normal same-family invalidation.
