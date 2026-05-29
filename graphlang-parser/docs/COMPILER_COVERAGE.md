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

What is not proven:

- every possible combination/order of documented methods
- deep traversal with `min_depth`/`max_depth`
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
g.V().hasLabel('collection')
g.V().hasLabel('collection_a', 'collection_b')
g.V().hasLabel('collection').hasId(TextP.endingWith('/admin'))
```

Status: unit-tested and e2e-tested.

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

Status: unit-tested and e2e-tested for default and directional traversal.

Limitations:

- `min_depth` and `max_depth` parse but compilation currently only supports the
  default depth of `1`
- non-default depth raises `UnsupportedOpiumCompilationError`

### `into`

Supported:

```python
into()
into('node_collection')
```

Compilation:

```groovy
.otherV()
.otherV().hasLabel('node_collection')
```

Status: unit-tested and e2e-tested.

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
```

Compilation:

- `_key` projects from `id()` and strips the collection prefix
- other fields compile to `.values('field')`

Status: unit-tested and e2e-tested for traversal result projection.

Portability concern:

- `_key` projection uses a Groovy closure

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

- condition operands that are subqueries or variables are parsed but not fully
  compiled
- regex assumes `TextP.regex(...)` is available in the target Gremlin runtime

## Currently Unsupported Documented Areas

The transcript mentions that condition arguments can be:

- a sub-query that starts with the current result
- a variable / mark
- a literal value
- a specific field name

The compiler supports literals and field names well. It does not yet fully
support subquery operands or variable operands inside conditions.

The transcript also documents `min_depth` and `max_depth` for `traverse`. Those
are parsed and validated, but non-default depth is not compiled yet.

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

1. define exact semantics for deep traversal
2. harden `assign`/`select`/`array` against real workflows
3. decide whether Groovy closures are acceptable for `_key` projection
4. add more e2e cases for variable scoping and nested conditions
5. run generated queries against representative real data volume

