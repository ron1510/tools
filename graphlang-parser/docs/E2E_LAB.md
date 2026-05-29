# ArangoDB Gremlin E2E Lab

The e2e lab validates generated Gremlin against a real ArangoDB TinkerPop
Provider setup.

The tests are optional and skipped by default because they require:

- Kubernetes access
- ArangoDB pod
- Gremlin Server pod
- local port-forward to Gremlin Server
- `gremlinpython==3.8.1`

## Lab Assumptions

The sibling repository is expected at:

```text
../arangodb-tinkerpop-gremlin
```

The Gremlin chart is deployed into:

```text
namespace: gremlin-lab
release: gremlin-arangodb-poc
service: gremlin-arangodb-poc
```

The ArangoDB chart is deployed into:

```text
namespace: gremlin-lab
pod: arangodb-lab-0
service: arangodb-lab
user: root
password: change-me
database: my_db
graph: my_graph
```

## Seed Data

Seed script:

```text
scripts/seed_opium_e2e.js
```

It drops and recreates `my_graph` in `my_db` with these collections:

Vertex collections:

- `users-data-product.user_roles`
- `veto-data-product.abilities`

Edge collections:

- `users-data-product.user_role_subscriptions`
- `veto-data-product.role_abilities`

Seeded user roles:

- `admin`
- `editor`
- `viewer`
- `auditor`

Seeded abilities:

- `read`
- `write`
- `delete`

Seeded relationships:

- `editor -> admin`
- `viewer -> editor`
- `auditor -> admin`
- `admin -> delete`
- `admin -> write`
- `editor -> write`
- `viewer -> read`

## Gremlin COMPLEX Config

Values file:

```text
e2e/gremlin-opium-values.yaml
```

This configures the ArangoDB TinkerPop Provider in `COMPLEX` mode with Opium
collection names as vertex and edge labels.

The currently used lab chart renders only the first `edgeDefinitions` list item,
so the values file stores both edge definitions in one preformatted string. This
is a workaround for the existing chart template.

## Commands

Install e2e dependency:

```powershell
python -m pip install -e ".[e2e]"
```

Seed ArangoDB:

```powershell
kubectl cp scripts/seed_opium_e2e.js gremlin-lab/arangodb-lab-0:/tmp/seed_opium_e2e.js
kubectl exec -n gremlin-lab arangodb-lab-0 -- arangosh --server.endpoint tcp://127.0.0.1:8529 --server.username root --server.password change-me --javascript.execute /tmp/seed_opium_e2e.js
```

Deploy Gremlin Server for the Opium graph:

```powershell
helm upgrade --install gremlin-arangodb-poc ..\arangodb-tinkerpop-gremlin\charts\gremlin-arangodb-poc --namespace gremlin-lab -f e2e\gremlin-opium-values.yaml
kubectl rollout status deployment/gremlin-arangodb-poc -n gremlin-lab --timeout=120s
```

Port-forward:

```powershell
kubectl port-forward -n gremlin-lab service/gremlin-arangodb-poc 8182:8182
```

Run e2e tests:

```powershell
$env:OPIUM_RUN_E2E='1'
$env:GREMLIN_URI='ws://localhost:8182/gremlin'
python -m pytest tests\test_e2e_gremlin_arangodb.py -q
```

## Manual Gremlin Inspection

Helper:

```text
scripts/gremlin_submit.py
```

Example:

```powershell
python scripts\gremlin_submit.py "g.V().hasLabel('users-data-product.user_roles').limit(4).elementMap()"
```

Useful probes:

```groovy
g.V().label().dedup()
g.E().label().dedup()
g.V().hasLabel('users-data-product.user_roles').limit(4).elementMap()
g.E().limit(4).project('id','label','props').by(id()).by(label()).by(valueMap())
```

## What The E2E Tests Prove

The current e2e tests prove:

- Arango collections are visible as Gremlin labels in `COMPLEX` mode
- `get(...).count()` returns expected counts
- `_key` filters work through `hasId(TextP.endingWith('/key'))`
- `_key` projection works through `id()` prefix stripping
- match predicates work for boolean, numeric, containment, null, and regex cases
- outbound and inbound edge traversal works across Opium collection names
- `skip`, `limit`, `unique`, projection, `array`, and `flatten` work for simple
  tested shapes

## Known E2E Gaps

The e2e tests do not yet prove:

- non-default traversal depth
- complex `assign`/`select` semantics
- subquery operands inside conditions
- variable operands inside conditions
- behavior on large datasets
- behavior if Gremlin Server disables Groovy closure execution

