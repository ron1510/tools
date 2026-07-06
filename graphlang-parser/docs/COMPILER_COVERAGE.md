# Compiler Coverage And Readiness

This project is not a complete Opium-to-Gremlin compiler yet. It is a working
first implementation for the documented common subset, with live validation
against the local ArangoDB TinkerPop Provider lab.

## Current Readiness

Parser status: solid v1.

Compiler status: useful v0.1, not complete production coverage.

What is proven:

- parser unit tests cover all documented syntax categories in the transcript
- compiler unit tests assert exact Gremlin strings for many common operations
- e2e tests execute representative generated Gremlin against ArangoDB TinkerPop
  Provider in `COMPLEX` mode
- collection labels and edge labels were verified live against the provider
- `_key` behavior was corrected based on live provider output
- subscript projection now returns raw scalar values, while `select(...)`
  returns maps/documents
- deep traversal is supported for documented `min_depth`/`max_depth` behavior
- live e2e tests cover a richer graph with role, user, ability, team, membership,
  hierarchy, subscription, role-ability, department, project, service, incident,
  region, environment, and document collections
- float literals are rendered as Java double literals for ArangoDB provider
  compatibility
- match operands can now be field names, current-row subqueries, or row-scoped
  variables for the tested comparison forms
- traversal aggregation inside `match(...)` is supported for `count()` and
  `unique().count()` numeric comparisons
- `is_null(field)` now matches missing fields or explicit null values in the
  live provider test graph
- unprojected terminal vertex results materialize as plain maps with `_key`,
  `_id`, and document properties
- unprojected terminal edge results materialize as plain maps with `_key`,
  `_id`, `_from`, `_to`, and edge properties, including dangling endpoint ids

What is not proven:

- every possible combination/order of documented methods
- all scoping behavior for complex `assign`, `array`, and `select` expressions
- performance on large graphs
- compatibility with Gremlin Server configurations that disable Groovy closures
- behavior against non-`COMPLEX` provider mode

## Supported And Tested Methods

### `get`

Supported:

```python
get('collection')
get('collection_a', 'collection_b')
get('collection', _key='admin')
```

Compilation:

```groovy
g.V().hasLabel('collection').map{...}
g.V().hasLabel('collection_a', 'collection_b').map{...}
g.V().hasLabel('collection').hasId(TextP.endingWith('/admin')).map{...}
```

Status: unit-tested and e2e-tested.

Unprojected `get(...)` returns document maps:

```python
[{"_key": "admin", "_id": "users-data-product.user_roles/admin", ...}]
```

Subscript projection returns scalar values:

```python
["admin"]
```

Use `select('_key')` when a map/document shape is required:

```python
[{"_key": "admin"}]
```

### `traverse`, `traverse_any`, `traverse_out`, `traverse_in`

Supported:

```python
traverse()
traverse('edge_collection')
traverse('edge_collection', direction='inbound')
traverse_any('edge_collection')
traverse_out('edge_collection')
traverse_in('edge_collection')
```

Compilation:

```groovy
.bothE(...)
.outE(...)
.inE(...)
```

Status: unit-tested and e2e-tested for default, directional, and deep traversal.

Depth behavior:

- `traverse(max_depth=N).into()` returns vertices at intermediate depths through
  `N`
- `traverse(min_depth=M, max_depth=N)` before `into()` returns edges at depths
  `M..N`

### `into`

Supported:

```python
into()
into('node_collection')
```

Compilation:

```groovy
.flatMap{...g.V(target)...}
.flatMap{...g.V(source)...}
.as('opium_current_vertex').bothE(...).flatMap{...g.V(other)...}
```

Status: unit-tested and e2e-tested. The compiler parses endpoint ids from the
provider edge string and looks them up with `g.V(id)`, because adjacent-vertex
steps fail on dangling endpoints. Dangling edge documents may be inspected as
edge results, but `into(...)` only returns materialized vertices.

### `skip`, `limit`

Supported:

```python
skip(100)
limit(100)
```

Compilation:

```groovy
.skip(100)
.limit(100)
```

Status: unit-tested and e2e-tested.

### `count`, `unique`

Supported:

```python
count()
unique()
```

Compilation:

```groovy
.count()
.dedup()
```

Status: unit-tested and e2e-tested.

### `array`, `flatten`

Supported for simple documented subquery shapes:

```python
array(traverse().into())
array(traverse_out('edge').into('node')['_key']).flatten()
flatten()
flatten(depth=2)
```

Compilation shape:

```groovy
.local(__...).fold()
.unfold()
```

Status: unit-tested and simple e2e-tested.

Limitations:

- only simple local child traversals are supported
- complex nesting/scoping has not been fully validated

### `as_var`, `var`, `assign`, `select`

Supported simple shapes:

```python
as_var('name')
var('name')
assign(traverse().into(), 'neighborhood')
select('_key', neighbors=var('neighborhood')['_key'])
```

Compilation shape:

```groovy
.as('name')
select('name')
.sideEffect(__...fold().as('neighborhood'))
.project(...).by(...)
```

Status: unit-tested.

Limitations:

- e2e tests do not yet deeply prove all variable/select semantics
- `assign` currently uses `sideEffect(...fold().as(...))`, which may not match
  all desired Opium semantics for per-row computed values
- complex computed columns beyond `var(...)` and `var(...)[field]` are not
  supported

### Projection / `[]`

Supported:

```python
get('collection')['_key']
var('name')['_key']
get('collection')['name']
get('collection')['_id']
get('edge_collection')['_from']
get('edge_collection')['_to']
```

Compilation:

- `_key` projects from `id()` and strips the collection prefix
- `_id` projects the full `collection/key` id
- other fields compile through `coalesce(values(field), constant(null))`
- the result shape is a scalar value for each current result

Status: unit-tested and e2e-tested for traversal result projection.

Portability concern:

- `_key` projection uses a Groovy closure
- `_from` and `_to` are Opium edge system fields. The current ArangoDB TinkerPop
  lab does not expose them via `values('_from')` / `values('_to')`, so the
  compiler parses them from the provider edge string. This keeps dangling edge
  endpoint ids projectable without materializing missing vertices.

### `match`, `match_all`, `match_any`

Supported:

```python
match(_key='hello')
match(name='goodbye')
match(eq('_key', 'hello'))
match(gt('age', 48), lte('age', 85))
match(age > 48, age <= 85)
match(ne('_key', 'hello'))
match(value_in('_key', ['one', 'two']))
match(nin('_key', ['one', 'two']))
match(is_null('field'))
match(regex_matches('name', '^a', caseInsensitive=True))
match_any(eq('_key', 'admin'), eq('_key', 'viewer'))
match(traverse_out('edge').into('node').count() >= 3)
match(traverse_out('edge').into('node').unique().count() >= 3)
```

Compilation uses:

- `.has(...)`
- `P.gt`, `P.lt`, `P.gte`, `P.lte`, `P.neq`
- `P.within`, `P.without`
- `TextP.regex`
- `.or(...)`
- `.not(...)`

Status: unit-tested and e2e-tested for the main predicate forms.

Limitations:

- deeply nested condition operands beyond the tested subquery/variable shapes
  may still need expansion
- aggregation inside match is limited to numeric comparisons against `count()`
  and `unique().count()`
- regex assumes `TextP.regex(...)` is available in the target Gremlin runtime

## Currently Unsupported Documented Areas

The transcript mentions that condition arguments can be:

- a sub-query that starts with the current result
- a variable / mark
- a literal value
- a specific field name

The compiler supports literals, field names, current-row traversal field
predicates, row-scoped variable predicates, and traversal `count()` predicates
for the tested shapes. It does not yet fully support every possible nested
subquery/variable condition shape.

`array` and `flatten` are implemented for the simple local traversal shapes now
covered by tests. The transcript supports per-row array replacement semantics,
but deeper interactions with `assign(...)`, variables, and nested arrays still
need more live validation before treating them as complete.

## Undocumented Keywords

The transcript lists these as currently undocumented:

- `to_graph`
- `field`
- `literal`
- `negate/not`
- `any_in_path`
- `all_in_path`

They remain unsupported by both parser allow-list and compiler.

## Bottom Line

The project is ready for team review and experimentation against the lab stack.
It is not ready to claim complete Opium compatibility.

Before calling it production-ready, the main missing work is:

1. define exact semantics for complex `array` and `assign`
2. decide when to move from Gremlin Groovy strings to Gremlin Python bytecode
3. add more e2e cases for variable scoping and nested conditions
4. run generated queries against representative real data volume
