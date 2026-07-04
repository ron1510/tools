# Compiler Walkthrough

This document explains how `opium_parser/compiler.py` turns a typed Opium AST
into Gremlin Groovy.

## Entry Points

There are two public compiler APIs:

```python
compile_opium_to_gremlin(source: str) -> str
compile_ast_to_gremlin(query: Query) -> str
```

`compile_opium_to_gremlin(...)` parses first:

```text
source text -> parse_opium(...) -> Query -> compile_ast_to_gremlin(...)
```

`compile_ast_to_gremlin(...)` assumes parsing already happened.

## Internal Shape

The compiler uses a small helper:

```python
GremlinTraversal(start: str, steps: list[str])
```

This is an append-only string builder:

```python
GremlinTraversal("g.V()")
  .add(".hasLabel('users')")
  .add(".limit(10)")
  .render()
```

renders:

```groovy
g.V().hasLabel('users').limit(10)
```

This is not a full Gremlin AST. It is a deliberately small internal
representation for the current Groovy-string compiler.

## Recursive Compilation Model

Opium chains are represented as nested AST nodes.

Example:

```python
get('users').limit(10)['_key']
```

AST shape:

```text
SubscriptExpr(
  receiver=MethodCallExpr(
    receiver=CallExpr(function='get', ...),
    method='limit',
  ),
  field='_key',
)
```

The compiler recursively compiles the receiver first, then appends the current
operation.

So:

```text
CallExpr get       -> g.V().hasLabel('users')
MethodCall limit  -> .limit(10)
Subscript _key    -> .id().map{...strip collection prefix...}
```

## Root Traversals vs Child Traversals

The compiler distinguishes:

```python
child=False
child=True
```

Root traversal:

```groovy
g.V()
```

Child traversal:

```groovy
__
```

Child traversals appear inside constructs such as:

```python
array(traverse().into())
match(eq(traverse().into()['_key'], 'admin'))
```

In Gremlin, `__` means anonymous traversal from the current traverser. This is
how Opium subqueries start from the current row.

## `get(...)`

Opium:

```python
get('users-data-product.user_roles')
```

Gremlin:

```groovy
g.V().hasLabel('users-data-product___user_roles')
```

Reason:

- in the current provider mode, Arango collections are labels
- documented `get` examples target entity collections
- edge documents are normally reached through `traverse(...)`

With `_key`:

```python
get('users-data-product.user_roles', _key='admin')
```

Gremlin:

```groovy
g.V()
 .hasLabel('users-data-product___user_roles')
 .hasId(TextP.endingWith('/admin'))
```

The suffix match exists because provider ids are `collection/key`.

## Traversal

Opium traversal is edge-first.

```python
traverse_out('edge_collection')
```

means:

```groovy
outE('edge_collection')
```

It returns edge traversers.

Then:

```python
into('node_collection')
```

means:

```groovy
flatMap{...parse _to id from edge string; g.V(target)...}.hasLabel('node_collection')
```

This split is important. It lets Opium users inspect edge documents before
moving into connected vertices.

For shallow `into(...)`, the compiler chooses the endpoint id from the edge
direction that produced the current edge cursor, then looks that id up with
`g.V(id)`:

```text
traverse_out(...).into(...) -> parse target id after `->`
traverse_in(...).into(...)  -> parse source id before `-edgeLabel->`
traverse_any(...).into(...) -> parse both ids and choose the one that is not
                               the labeled current vertex
```

That keeps edge inspection broad while making endpoint materialization explicit.
Dangling edge documents can still be returned by `traverse(...)`, but they do
not produce vertex rows after `into(...)`.

## Direction

Current mapping:

```text
traverse_any / direction='any'      -> bothE
traverse_out / direction='outbound' -> outE
traverse_in / direction='inbound'   -> inE
```

This is based on Arango `_from` and `_to` semantics.

## Deep Traversal

For:

```python
traverse_out('edge', max_depth=3).into('node')
```

the compiler uses:

```groovy
repeat(outE('edge').as('opium_edge').flatMap{...g.V(target)...}).emit().times(3)
```

When `into()` is present, the repeat body already moves to vertices, so emitted
results are vertices.

Without `into()`:

```python
traverse_out('edge', min_depth=2, max_depth=3)
```

the compiler selects the labeled edge:

```groovy
repeat(outE('edge').as('opium_edge').flatMap{...g.V(target)...})
  .emit(loops().is(P.gte(2)))
  .times(3)
  .select('opium_edge')
```

This preserves the rule that `traverse(...)` returns edges.

## Projection

Subscript projection:

```python
get('users')['_key']
```

returns scalar values:

```python
["admin"]
```

Compiler shape:

```groovy
.id().map{it.get().substring(it.get().lastIndexOf('/') + 1)}
```

Projection handling:

- `_key`: derive from `id()` suffix
- `_id`: full Gremlin/Arango id
- `_from`: source vertex id for edge traversers
- `_to`: target vertex id for edge traversers
- normal field: `coalesce(values(field), constant(null))`

The normal field projection uses `coalesce` because plain `values(field)` drops
the current row when the property is missing.

## `select(...)`

Opium:

```python
select('_key', 'name')
```

Gremlin:

```groovy
project('_key', 'name').by(...).by(...)
```

Computed columns:

```python
select('_key', role_id=var('role')['_id'])
```

compile by rendering each computed expression as a `by(...)` traversal.

Current computed support is intentionally narrow:

- string literals
- `var('name')`
- `var('name')[field]`

Complex computed expressions are still a future area.

## `match(...)`

Keyword equality:

```python
match(active=True)
```

Gremlin:

```groovy
has('active', true)
```

Comparison function:

```python
match(gt('age', 48))
```

Gremlin:

```groovy
has('age', P.gt(48))
```

Binary comparison:

```python
match(age > 48)
```

Gremlin:

```groovy
has('age', P.gt(48))
```

`match(...)` and `match_all(...)` are AND. Conditions are appended as sequential
filter steps.

`match_any(...)` is OR:

```groovy
or(__.has(...), __.has(...))
```

## Match Subquery Operands

Opium:

```python
get('roles')
  .match(eq(traverse_out('role_abilities').into('abilities')['_key'], 'write'))
```

Gremlin shape:

```groovy
g.V().hasLabel('roles')
 .filter(
   __.outE('role_abilities')
     .otherV()
     .hasLabel('abilities')
     .hasId(TextP.endingWith('/write'))
 )
```

The child traversal starts from the current row. The filter keeps only rows for
which that child traversal finds a matching result.

Traversal aggregation inside `match(...)` uses the same current-row child
traversal model:

```python
get('roles')
  .match(
    traverse_out('role_abilities')
      .into('abilities')
      .count() >= 3
  )
```

Gremlin shape:

```groovy
g.V().hasLabel('roles')
 .filter(
   __.outE('role_abilities')
     .otherV()
     .hasLabel('abilities')
     .count()
     .is(P.gte(3))
 )
```

`count()` counts raw subquery results. `unique().count()` adds `dedup()` before
`count()`. Empty subqueries count as `0`, and count comparisons require numeric
literals.

## Match Variable Operands

Opium:

```python
get('roles').as_var('role').match(eq(var('role')['_key'], 'admin'))
```

Gremlin shape:

```groovy
g.V().hasLabel('roles')
 .as('role')
 .filter(__.select('role').hasId(TextP.endingWith('/admin')))
```

`var('role')` is compiled as `select('role')`.

## Null Checks

Opium:

```python
is_null('nullable_field')
```

Gremlin:

```groovy
or(
  __.not(__.has('nullable_field')),
  __.has('nullable_field', null)
)
```

This matches missing properties and explicit null values.

## Float Literals

Opium:

```python
score >= 90.0
```

Gremlin:

```groovy
P.gte(90.0d)
```

The `d` suffix is intentional. Plain Groovy decimal literals are `BigDecimal`,
and the current ArangoDB TinkerPop Provider rejected `BigDecimal` predicate
values during live testing.

## `array(...)` And `flatten(...)`

Current `array` shape:

```groovy
local(__...).fold()
```

Current `flatten(depth=N)` shape:

```groovy
unfold().unfold()...
```

This supports simple shapes. Complex row-scope and interaction with `assign`
still require more live validation.

## `assign(...)`

Current shape:

```groovy
sideEffect(__...fold().as('name'))
```

This is a first-pass implementation. It is not yet live-proven for complex
computed projections, and the exact semantics are still under review.

## Where To Change Things

For labels/resource behavior:

- `_compile_call`
- `get` branch
- `_apply_traverse`

For `_key`, `_id`, `_from`, `_to`:

- `_compile_by_projection`
- `_compile_key_filter`
- `_compile_key_membership`

For match behavior:

- `_apply_match`
- `_compile_condition`
- `_compile_condition_call`
- `_compile_operand_condition`
- `_compile_field_condition`

For traversal depth:

- `_apply_traverse`
- `_apply_deep_traverse_into`
- `_compile_deep_traverse_step`
- `_compile_deep_repeat_body`

For select/computed columns:

- `_apply_select`
- `_compile_projection_expr`

For array/assign:

- `_apply_method`, `array` branch
- `_apply_method`, `flatten` branch
- `_apply_assign`
