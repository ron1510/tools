# ArangoDB Gremlin E2E Lab

For a table-oriented description of the seeded graph, read
`docs/E2E_GRAPH_REFERENCE.md`.

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
- `users-data-product.users`
- `permissions-data-product.abilities`
- `org-data-product.teams`
- `org-data-product.departments`
- `delivery-data-product.projects`
- `platform-data-product.services`
- `ops-data-product.incidents`
- `infra-data-product.regions`
- `infra-data-product.environments`
- `knowledge-data-product.documents`

Edge collections:

- `users-data-product.user_role_subscriptions`
- `permissions-data-product.role_abilities`
- `org-data-product.user_memberships`
- `org-data-product.team_hierarchy`
- `users-data-product.user_role_assignments`
- `org-data-product.department_memberships`
- `delivery-data-product.department_projects`
- `platform-data-product.project_services`
- `platform-data-product.service_dependencies`
- `ops-data-product.incident_impacts`
- `infra-data-product.service_regions`
- `infra-data-product.service_environments`
- `knowledge-data-product.document_links`

Seeded user roles:

- `admin`
- `editor`
- `viewer`
- `auditor`
- `owner`

Seeded users:

- `alice`
- `bob`
- `carol`
- `dave`
- `erin`

Seeded abilities:

- `read`
- `write`
- `delete`
- `approve`

Seeded teams:

- `platform`
- `security`
- `executive`
- `qa`

Seeded relationships:

- `editor -> admin`
- `viewer -> editor`
- `auditor -> admin`
- `admin -> owner`
- `admin -> delete`
- `admin -> write`
- `admin -> approve`
- `editor -> write`
- `viewer -> read`
- `alice -> platform`
- `bob -> security`
- `carol -> executive`
- `dave -> qa`
- `erin -> platform`
- `platform -> executive`
- `security -> executive`
- `qa -> platform`
- users -> roles
- users -> departments
- departments -> projects
- projects -> services
- services -> services
- incidents -> services
- services -> regions
- services -> environments
- documents -> documents

Current graph size:

```text
73 vertices across 11 vertex collections
118 edges across 13 edge collections
```

## Gremlin COMPLEX Config

Values file:

```text
e2e/gremlin-opium-values.yaml
```

This configures the ArangoDB TinkerPop Provider in `COMPLEX` mode with Opium
collection names as vertex and edge labels.

The currently used lab chart renders only the first `edgeDefinitions` list item,
so the values file stores all edge definitions in one preformatted string. This
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
python -m pytest tests\e2e -q
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
- complex mixed queries work for filtering, traversal, projection, unique, and
  count aggregation in one chain
- outbound, inbound, and any-direction edge traversal works across Opium
  collection names
- multi-domain traversal works across roles, abilities, users, memberships, and
  team hierarchy collections
- larger cross-domain traversal works across departments, projects, services,
  incidents, regions, environments, and document-link chains
- match operands based on current-row subqueries
- match operands based on row-scoped variables
- `is_null(field)` matching missing fields or explicit null values
- `_id`, `_from`, and `_to` projection works for the currently tested shapes
- `skip`, `limit`, `unique`, projection, `array`, and `flatten` work for simple
  tested shapes
- projected field access returns maps such as `{"_key": "admin"}`
- deep traversal returns intermediate depths as defined in
  `docs/OPIUM_SEMANTICS.md`

## Known E2E Gaps

The e2e tests do not yet prove:

- complex `assign`/`select` semantics
- default full-document materialization
- behavior on large datasets
- behavior if Gremlin Server disables Groovy closure execution
- complex `_from`/`_to` use outside direct edge projections
