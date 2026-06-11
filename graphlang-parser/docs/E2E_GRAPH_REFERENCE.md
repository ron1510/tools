# E2E Graph Reference

This document describes the synthetic graph seeded by
`scripts/seed_opium_e2e.py`.

The graph is not meant to be production-sized. It is meant to be broad enough to
exercise many compiler assumptions against a real ArangoDB TinkerPop Provider.

## Size

Current size:

```text
73 vertices
118 edges
11 vertex collections
13 edge collections
```

## Vertex Collections

| Collection | Count | Purpose |
| --- | ---: | --- |
| `users-data-product.user_roles` | 5 | Role hierarchy, role matching, `_key` tests |
| `users-data-product.users` | 5 | User/team/department/role traversals |
| `permissions-data-product.abilities` | 4 | Role ability traversal and unique aggregation |
| `org-data-product.teams` | 4 | Team hierarchy traversal |
| `org-data-product.departments` | 6 | Department to project traversal |
| `delivery-data-product.projects` | 8 | Project to service traversal |
| `platform-data-product.services` | 12 | Service dependency graph |
| `ops-data-product.incidents` | 9 | Reverse traversal into incidents |
| `infra-data-product.regions` | 5 | Service region lookup |
| `infra-data-product.environments` | 4 | Service environment lookup |
| `knowledge-data-product.documents` | 15 | Deep document-link traversal |

## Edge Collections

| Collection | Count | From | To | Purpose |
| --- | ---: | --- | --- | --- |
| `users-data-product.user_role_subscriptions` | 4 | roles | roles | same-collection role hierarchy |
| `permissions-data-product.role_abilities` | 5 | roles | abilities | cross-collection traversal |
| `org-data-product.user_memberships` | 5 | users | teams | user to team traversal |
| `org-data-product.team_hierarchy` | 3 | teams | teams | deep hierarchy traversal |
| `users-data-product.user_role_assignments` | 7 | users | roles | user role binding graph |
| `org-data-product.department_memberships` | 7 | users | departments | user to department graph |
| `delivery-data-product.department_projects` | 8 | departments | projects | department to project graph |
| `platform-data-product.project_services` | 16 | projects | services | project to service fan-out |
| `platform-data-product.service_dependencies` | 14 | services | services | service dependency graph |
| `ops-data-product.incident_impacts` | 9 | incidents | services | reverse incident lookup |
| `infra-data-product.service_regions` | 12 | services | regions | service to region lookup |
| `infra-data-product.service_environments` | 14 | services | environments | service to environment lookup |
| `knowledge-data-product.document_links` | 14 | documents | documents | deep document chain |

## Why This Shape Exists

The graph intentionally includes:

- same-collection edges
- cross-collection edges
- multi-hop chains
- fan-out relationships
- reverse traversal cases
- mixed endpoint labels
- edge properties
- explicit null fields
- missing fields
- numeric fields
- boolean fields
- string fields

This gives the compiler a realistic correctness target without requiring a huge
dataset.

## Query Patterns Covered

The e2e suite covers:

- `get(...).count()`
- multi-resource `get(a, b)`
- `_key` and `_id` projection
- missing field projection
- keyword match
- function-style match
- binary comparison match
- containment match
- regex match
- missing and explicit-null checks
- inbound traversal
- outbound traversal
- any-direction traversal
- edge projection before `into()`
- deep traversal
- `skip`
- `limit`
- `unique`
- `count`
- `array(...).flatten()` simple shape
- subquery operands inside `match`
- variable operands inside `match`
- larger cross-domain traversal chains

## What It Does Not Prove

The graph does not prove:

- production performance
- query planning quality on very large data
- behavior under high concurrency
- all possible `assign(...)` semantics
- all possible `array(...)` semantics
- compatibility with non-`COMPLEX` provider mode

Use it as a correctness graph, not as a benchmark.
