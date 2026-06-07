# Opium Semantics

This document records the agreed semantics for the documented Opium subset.
The primary source is `opium_keywords_transcript.md`; this file should explain
that transcript in implementation-friendly terms without inventing new language
behavior.

It is the source of truth for compiler behavior. The questions that are still
open live in `docs/QUESTIONS_FOR_COMPILER_COMPLETION.md`.

## Backend Model

The target backend is ArangoDB accessed through ArangoDB TinkerPop Provider in
`COMPLEX` mode.

ArangoDB collection names are exposed as Gremlin labels:

- vertex collections are Gremlin vertex labels
- edge collections are Gremlin edge labels

Example:

```python
get('users-data-product.user_roles')
```

targets vertices with label:

```text
users-data-product.user_roles
```

Example:

```python
traverse_out('users-data-product.user_role_subscriptions')
```

targets outgoing edges with label:

```text
users-data-product.user_role_subscriptions
```

## Default Result Shape

By default, a query returns the full current documents/entities.

Example:

```python
get('users-data-product.user_roles')
```

returns all user role documents with all available fields, as if all fields were
selected.

Ordering is unspecified unless an explicit ordering operation is introduced.
Tests and callers should not rely on result order unless the query explicitly
asks for it.

## Projection Semantics

Subscript projection returns the scalar value of one field for each current
result. It does not return one-field maps.

Example:

```python
get('users-data-product.user_roles')['_key']
```

returns:

```python
[
    "first",
    "second",
]
```

Multiple field projection should be expressed with `select(...)`, not with
`[]`.

If the selected field is missing, the current compiler preserves the row and
returns `None` for that projection. The transcript is explicit about missing
fields in `select(...)`; scalar projection uses the same missing-field behavior
for now so row counts do not silently change.

## Internal Arango Fields

### `_key`

`_key` is the part after the slash in the Gremlin/Arango id.

Example id:

```text
users-data-product.user_roles/admin
```

means:

```text
_key == "admin"
```

The compiler should treat `_key` as a derived internal field, not as a normal
Gremlin property.

### `_id`

`_id` projection should return the full Arango id in `collection/key` form.

Example:

```text
users-data-product.user_roles/admin
```

### `_from` And `_to`

`_from` and `_to` are normal mandatory fields on edge documents.

If the current cursor is on edges, projecting `_from` or `_to` should return
those system field values. If the Gremlin provider does not expose them as normal
properties, the compiler may use provider-specific Gremlin such as `outV().id()`
and `inV().id()` to preserve the Opium result shape.

`_from` and `_to` values are full ids, equivalent to the ids of the source and
target nodes.

## Traversal Semantics

### `traverse`

`traverse()` moves the current cursor from vertex documents to connected edge
documents.

If no select/projection is specified after `traverse()`, the result should be
the full edge documents.

Example:

```python
get('users-data-product.user_roles', _key='admin').traverse()
```

returns the full edge documents connected to the user role whose `_key` is
`admin`.

### `into`

`into()` consumes the current edge cursor and continues the walk to the nodes on
the other side of those edges.

Example:

```python
get('users-data-product.user_roles', _key='admin').traverse().into()
```

returns the full connected node documents reached from the edges found by
`traverse()`.

### Direction

`direction` constrains which connected edges are found by `traverse`.

Mappings:

```text
outbound -> outgoing edges from the current node
inbound  -> incoming edges into the current node
any      -> both incoming and outgoing edges
```

The actual direction is determined by the edge document's `_from` and `_to`
fields. Every edge document is expected to have `_from` and `_to`, similar to how
every entity is expected to have `_key`.

### Depth

`min_depth` and `max_depth` describe traversal depth in number of edges.

For this graph:

```text
A -> B -> C -> D
```

this query:

```python
get('nodes', _key='A').traverse(max_depth=3).into()
```

returns nodes at every depth from the default minimum depth through the maximum
depth:

```text
B, C, D
```

Since `traverse` returns edges before `into()` is applied:

```python
get('nodes', _key='A').traverse(min_depth=2, max_depth=3)
```

returns edges at depth 2 and depth 3.

Depth results include intermediate depths, not only the final depth.

## `var(...)` Placement

`var(...)` may legally appear in all expression positions discussed so far,
including:

- `select`
- `match`
- subqueries
- projections

Individual compiler support may still be implemented incrementally, but the
language semantics allow `var(...)` broadly.

Inside `match(...)`, variables are evaluated from the current row's variable
scope.

Example:

```python
get('users-data-product.user_roles')
    .as_var('role')
    .match(eq(var('role')['_key'], 'admin'))
```

returns the current `user_roles` entities whose bound `role` variable has
`_key == "admin"`. In this example, the result is equivalent to matching the
current row's `_key` against `"admin"`.

## `select(...)` Semantics

`select(...)` returns maps/documents containing the selected fields and computed
columns. This is intentionally different from `[]`, which returns scalar field
values.

Example:

```python
get('users-data-product.user_roles').select('_key', 'name')
```

returns:

```python
[
    {
        "_key": "fjfj",
        "name": "ron",
    },
]
```

`select('_key')` returns `{"_key": value}` rows. `['_key']` returns raw `value`
rows.

Missing selected fields should appear with a `None` value in Python.

Example:

```python
get('users-data-product.user_roles').select('_key', 'missing_field')
```

returns:

```python
[
    {
        "_key": "fjfj",
        "missing_field": None,
    },
]
```

Computed columns return whatever the computed expression returns.

If the expression returns a scalar, the computed column value is scalar. If the
expression returns an array, the computed column value is an array. If the
expression returns a map/document, the computed column value is a map/document.

Example:

```python
select('_key', neighbors=var('neighborhood')['_key'])
```

If `neighborhood` is bound to an array of entities, then `neighbors` should be an
array of projected `_key` values according to the projection semantics of that
expression.

## Aggregation And Result Shaping

`count()` returns the count of the current result stream.

Example:

```python
get('users-data-product.user_roles').match(active=True).count()
```

returns a one-item result containing the number of active user role documents.

`unique()` removes duplicate current results.

Example:

```python
get('users-data-product.user_roles')
    .traverse_out('permissions-data-product.role_abilities')
    .into('permissions-data-product.abilities')
    .unique()
```

returns each reached ability only once, even if multiple roles reach the same
ability.

`skip(N)` and `limit(N)` operate on the current result stream. Ordering is still
unspecified unless an explicit ordering operation is introduced.

## `array(...)` And `flatten(...)` Semantics

`array(subquery)` runs a subquery from each current row and replaces the current
row with an array containing that subquery's results.

Example:

```python
get('users-data-product.user_roles', _key='admin')
    .array(traverse().into()['_key'])
```

returns one array result for the `admin` row. The array contains scalar `_key`
values because `['_key']` is scalar projection.

Use `assign(...).select(...)` when the original row should be preserved and the
computed subquery result should be exposed as a named output column.

`flatten()` and `flatten(depth=1)` are equivalent.

`flatten(depth=N)` flattens nested arrays by `N` levels.

Examples:

```python
flatten()
flatten(depth=1)
flatten(depth=2)
```

If the current result contains nested arrays, `flatten(depth=2)` removes two
array nesting levels. The operation should not imply additional graph traversal;
it only reshapes array/list results.

## Match Subquery Semantics

Condition operands may be subqueries, but a complete query must still establish
an initial cursor with `get(...)`.

Example:

```python
get('some-things.some')
    .match(eq(traverse().into()['_key'], 'admin'))
```

This returns all `some-things.some` entities for which a depth-1 reachable node
has `_key == "admin"`.

The subquery inside the condition starts from the current row. It is not a
global graph query.

Aggregation subqueries inside `match(...)` also start from the current row.
The supported aggregate form is `count()` and `unique().count()` compared to a
numeric literal.

Example:

```python
get('users-data-product.user_roles')
    .match(
        traverse_out('permissions-data-product.role_abilities')
            .into('permissions-data-product.abilities')
            .count() >= 3
    )
```

returns current roles whose local ability traversal produces at least three
results.

`count()` counts raw traversal results. `unique().count()` deduplicates before
counting. If the subquery has no results, `count()` evaluates to `0` for that
current row. Non-numeric comparisons against `count()` are invalid Opium
semantics.

## Null Semantics

`is_null(field)` matches both:

- documents where `field` is missing
- documents where `field` exists with an explicit null value

Compiler implementations should preserve this distinction from ordinary
equality matching. If the provider cannot directly query explicit null and
missing values in one portable step, the compiler should use provider-specific
Gremlin that produces the same Opium behavior.

## Regex Semantics

Regex matching should behave like regular regex matching. There are no special
Opium-only regex semantics.

The compiler may use whichever Gremlin/provider-supported regex form works best.
The current `TextP.regex(...)` approach is acceptable if it works against the
target provider.

## Unsupported And Future Keywords

Do not support these currently undocumented keywords yet:

- `to_graph`
- `field`
- `literal`
- `negate/not`
- `any_in_path`
- `all_in_path`

`to_graph` is likely to be added soon and should be considered a near-future
extension point. The other undocumented keywords are not important at this time.

## Production Constraints

The eventual target should be Gremlin Python because the clients will be Python
applications and scripts.

Gremlin Groovy string output is useful for the current prototype and tests, but
the desired final compiler output should be Gremlin Python traversal/bytecode
where practical.

Performance is preferred if there is a tradeoff. Readability is less important
than producing efficient provider-friendly Gremlin.

Groovy closures are acceptable for now because the Gremlin Server can be
configured as needed. Removing closure usage is still desirable eventually, but
it is not an immediate blocker.

## Implementation Priorities

1. Deep traversal
2. Match with variables/subqueries
3. Broader e2e coverage
4. Remove Groovy closure usage
5. Assign/select correctness
6. Array/flatten correctness
