# Architecture

## Goal

This cache layer provides REST-aware caching and invalidation without maintaining a custom
application service. Varnish is both the reverse proxy and the invalidation decision point.

```text
client / ingress -> Varnish -> backend REST API
```

The backend remains a normal REST API. Varnish handles cache policy in VCL.

## What Varnish Can Infer

HTTP gives Varnish useful method semantics:

- `GET` is cacheable when the request and response are safe to cache.
- `POST`, `PUT`, `PATCH`, and `DELETE` are mutations and should pass through.
- Query strings are part of the request identity.

The VCL adds a project-specific REST convention:

```text
/api/v1/{family}
/api/v1/{family}/{id}
/api/v1/{family}/search
```

This is generic parsing. It does not require hardcoding each path parameter value.

## What Must Be Configured

Varnish cannot know business dependencies by itself. For example, it cannot infer that mutating
`users` should also invalidate `permissions`. Those relationships belong in the VCL dependency
mapping section:

```vcl
if (req.http.X-Cache-Family == "users") {
  ban("obj.http.X-Cache-Collection-Key == collection:permissions");
}
```

That is cache policy configuration, not application business code.

In the Helm chart this is configured with `varnish.dependencyBans`:

```yaml
varnish:
  dependencyBans:
    - family: users
      collectionKeys:
        - collection:permissions
```

Read this as:

```text
When a mutation request targets the users family,
also invalidate cached collection/list/search responses for permissions.
```

`dependencyBans` is not a route table and it is not a list of concrete resource ids. It is a small
resource-family dependency map.

## Collection Keys and Dependency Bans

The generated VCL creates two kinds of invalidation tags:

```text
resource:{family}:{id}
collection:{family}
```

The `family` is the first path segment after `apiPrefix`:

```text
/api/v1/users/123        -> family: users
/api/v1/resources/search -> family: resources
/api/v1/permissions      -> family: permissions
```

`collectionKeys` are the collection tags to ban as a side effect of mutating another family. They
are named `collectionKeys` because each value must match the collection tag stored on cached
objects:

```text
collection:users
collection:resources
collection:permissions
```

Cached GET examples:

```text
GET /api/v1/permissions
GET /api/v1/permissions?user=123
GET /api/v1/permissions/search?q=read
-> tagged collection:permissions

GET /api/v1/users/123
-> tagged resource:users:123
-> tagged collection:users
```

Mutation examples:

```text
PUT /api/v1/users/123
-> automatically bans resource:users:123
-> automatically bans collection:users

POST /api/v1/users
-> automatically bans collection:users
```

Those same-family bans do not need to be configured. Configure `dependencyBans` only when another
family's cached collections also become stale:

```yaml
varnish:
  dependencyBans:
    - family: users
      collectionKeys:
        - collection:permissions
    - family: orders
      collectionKeys:
        - collection:customers
```

This means:

```text
Mutating users also invalidates permissions collections.
Mutating orders also invalidates customers collections.
```

Do not configure paths or concrete ids in `collectionKeys`:

```yaml
# Good
collectionKeys:
  - collection:permissions

# Wrong for this chart
collectionKeys:
  - /api/v1/permissions
  - collection:permissions:123
  - resource:permissions:123
```

If you later need precise per-id cross-family dependencies, that is a different invalidation model
and the chart would need an explicit `resourceKeys`-style feature. The current chart intentionally
keeps dependencies broad and family-level because it matches REST list/search caching without
requiring per-id path configuration.

## Cache Keys vs Invalidation Tags

The cache key keeps the full normalized request identity:

- HTTP method
- host
- full URL including `/api/v1`

GET cache entries intentionally do not vary by `Authorization`, `Cookie`, `X-Tenant-ID`,
`X-User-Scope`, or other caller identity headers. The same host and URL share one cached object
across callers. This is the lean, centralized cache mode and is only correct when cached GET
responses are safe to share for that URL.

The invalidation tags strip the API prefix conceptually:

```text
GET /api/v1/resources/123
cache key includes: /api/v1/resources/123
tags include: resource:resources:123, collection:resources
```

Keeping `/api/v1` in the cache key prevents accidental collisions with future API versions.

## Default Invalidation Rules

```text
GET /api/v1/{family}/{id}
-> resource:{family}:{id}
-> collection:{family}

GET /api/v1/{family}
GET /api/v1/{family}?...
GET /api/v1/{family}/search?...
-> collection:{family}

PUT/PATCH/DELETE /api/v1/{family}/{id}
-> ban resource:{family}:{id}
-> ban collection:{family}

PUT/PATCH/DELETE /api/v1/{family}
-> ban collection:{family}

POST /api/v1/{family}
-> ban collection:{family}
```

Mutation requests are still forwarded to the backend after Varnish adds the local bans.

## Why One Varnish Replica

OSS Varnish bans are local to the Varnish instance that receives the request. With multiple pods,
a mutation routed to one pod would not automatically invalidate objects stored in another pod.

The default deployment therefore uses one active Varnish replica for correctness without custom code.

To scale out cache replicas later, add an invalidation fanout mechanism:

- Varnish Broadcaster
- application-triggered invalidation
- Varnish Enterprise Controller/YKey
- another managed invalidation plane

## Helm Chart Choice

The deployment uses the local `charts/rest-cache` chart. Varnish Software provides an official Helm
chart, but its current documentation targets Varnish Enterprise, Varnish Controller, and Controller
Router. This project intentionally uses Varnish Cache OSS and keeps the chart small.

The lab backend is intentionally separate in `charts/rest-cache-lab`, so production installs do not
carry sample-service templates or values.

If Enterprise becomes acceptable later, the REST-aware VCL can be moved into the upstream chart's
custom VCL value.

## Scaling Notes

Thousands of requests per minute is modest for Varnish when the workload is read-heavy and the pod
has reasonable CPU and memory. The main scaling risk is not raw request volume; it is invalidation
shape.

Broad collection bans are correct but can reduce hit rate:

```text
PUT /api/v1/resources/123
-> invalidates every cached /api/v1/resources list/search variant
```

If writes are frequent and collections are broad, cache churn may dominate. In that case, narrow
dependency rules, shorter TTLs on volatile collections, or explicit application invalidation may be
better.
