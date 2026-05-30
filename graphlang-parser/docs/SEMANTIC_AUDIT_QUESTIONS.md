# Semantic Audit Questions

This document is a stricter audit than
`QUESTIONS_FOR_COMPILER_COMPLETION.md`.

Rule used to create it:

```text
If we cannot write a precise test with a precise expected result, then the
behavior is still a semantic question.
```

The goal is not to make the language complicated. The goal is to remove hidden
ambiguity before the compiler accidentally bakes in the wrong behavior.

## 1. Top-Level Query Shape

### 1.1 Must executable queries always start with `get(...)`?

Current understanding:

```python
get('collection')
```

sets the initial cursor.

Questions:

- Should `traverse(...)` be allowed as a top-level executable query?
- Should `into(...)` be allowed as a top-level executable query?
- Should `var(...)` be allowed as a top-level executable query?
- Should `match(...)` be allowed as a top-level executable query?
- Or should these parse but fail compilation unless they are inside a query?

Recommended decision:

```text
Executable graph queries must start with get(...). Other top-level expressions
may parse for syntax completeness but should not compile as standalone backend
queries unless a concrete use case appears.
```

### 1.2 Can `get(...)` target edge collections?

Questions:

- Is `get('edge_collection')` valid?
- If yes, how does compiler know whether the resource is a vertex collection or
  edge collection?
- Should root edge lookup use `g.E().hasLabel(...)`?
- Should the compiler require a schema/catalog to distinguish vertex resources
  from edge resources?

Recommended decision:

```text
For now, get(...) targets vertex collections only. Edge documents are reached
through traverse(...). If root edge lookup is needed, add an explicit semantic
rule or schema/catalog.
```

## 2. Default Result Materialization

### 2.1 What fields appear when no projection/select is used?

Example:

```python
get('users-data-product.user_roles', _key='admin')
```

Questions:

- Should result include `_key`?
- Should result include `_id`?
- Should result include all user fields?
- Should missing fields be absent or present as `None`?
- Should `_from` and `_to` appear for edge documents?
- Should internal provider fields be filtered out?

Recommended decision:

```text
Default materialization returns a full document-like map. For vertices, include
_key, _id, and stored document fields. For edges, include _key, _id, _from, _to,
and stored edge fields.
```

### 2.2 Is default result shape stable across rows?

If one row has `nullable_field` and another does not:

```python
get('users-data-product.user_roles')
```

Questions:

- Should each row contain only fields present on that row?
- Or should all rows share the union of fields with missing values as `None`?

Recommended decision:

```text
Default materialization returns each document's own fields. Explicit select(...)
is required for a stable output schema with None for missing selected fields.
```

## 3. Ordering

### 3.1 Is result order ever guaranteed?

Questions:

- Is `limit(10)` meaningful without an ordering operation?
- Should tests sort results unless ordering is documented?
- Should Opium add `sort(...)` / `order_by(...)` later?

Recommended decision:

```text
Ordering is unspecified unless a future ordering operation is introduced.
Tests must sort unless the query explicitly orders results.
```

### 3.2 Does `array(...)` preserve traversal order?

Questions:

- Should arrays preserve backend traversal order?
- Should arrays be treated as unordered unless explicitly sorted?

Recommended decision:

```text
Array order is unspecified unless Opium gets ordering semantics.
```

## 4. Duplicate Handling

### 4.1 Do traversals preserve duplicates?

If two different paths reach the same vertex:

```python
get('x').traverse(..., max_depth=3).into()
```

Questions:

- Should duplicate reached vertices appear multiple times?
- Should Opium deduplicate by default?
- Is `unique()` the only deduplication operation?

Recommended decision:

```text
Traversal preserves duplicates. Use unique() to deduplicate.
```

### 4.2 What does `unique()` deduplicate by?

Questions:

- Element id?
- Full document equality?
- Current map result equality?
- Scalar value?

Recommended decision:

```text
For graph elements, unique() deduplicates by element identity. For maps/scalars,
it deduplicates by backend value equality.
```

## 5. Projection

### 5.1 Does `[]` support only one field forever?

Examples:

```python
get('x')['_key']
get('x')[name]
```

Questions:

- Should `get('x')[['_key', 'name']]` ever be supported?
- Should multiple projection stay only in `select(...)`?

Recommended decision:

```text
[] is single-field projection only. Use select(...) for multiple fields.
```

### 5.2 Does projection over arrays map automatically?

Example:

```python
var('neighbors')['_key']
```

when `neighbors` is an array.

Questions:

- Does this map `_key` over array elements?
- Does it fail because the current value is an array?
- Does it return one flattened stream?

Recommended decision:

```text
Projection over an array maps over each array element and preserves array shape.
```

### 5.3 Projection result inside arrays

Example:

```python
array(traverse().into()['_key'])
```

Questions:

- Is the array item `{"_key": "x"}`?
- Or is the array item `"x"`?

Current project convention suggests:

```python
[{"_key": "x"}]
```

But this should be confirmed.

## 6. `select(...)`

### 6.1 Should computed column expressions allow comparisons?

Example:

```python
select('_key', is_admin=var('role')['_key'] == 'admin')
```

Questions:

- Should this return boolean?
- Should computed select expressions support all expression types?
- Or only variables and projections?

Recommended decision:

```text
Computed select should eventually support literal, var, projection, comparison,
and subquery expressions, but implement incrementally with tests.
```

### 6.2 What happens when two selected names collide?

Example:

```python
select('_key', _key=var('x')['_key'])
```

Questions:

- Reject duplicate output names?
- Let computed column overwrite positional field?

Recommended decision:

```text
Reject duplicate output names.
```

## 7. `array(...)`

### 7.1 Is `array(subquery)` per-row?

Questions:

- Is the subquery run once per current row?
- Or once globally over all current rows?

Recommended decision:

```text
array(subquery) is per current row.
```

### 7.2 Does `array(...)` replace the current row?

Questions:

- Does `.array(...)` make the current result an array?
- Or attach an array to the existing current row?

Recommended decision:

```text
array(...) replaces the current row with the array result.
```

### 7.3 Empty array behavior

Questions:

- If subquery returns no rows, is result `[]`?
- Or is the current row dropped?

Recommended decision:

```text
Empty subquery result becomes [] and does not drop the row.
```

### 7.4 Nested arrays

Questions:

- Does `array(array(...))` produce nested arrays?
- Does `flatten(depth=1)` remove exactly one layer?
- Does `flatten(depth=999)` over-flatten until scalar, or fail?

Recommended decision:

```text
array(array(...)) produces nested arrays. flatten(depth=N) removes up to N
layers where present and does not fail if fewer layers exist.
```

## 8. `assign(...)`, `as_var(...)`, `var(...)`

### 8.1 Is `assign(...)` per-row?

Recommended decision:

```text
Yes. assign(subquery, name) runs subquery from each current row.
```

### 8.2 Does `assign(...)` always store arrays?

Recommended decision:

```text
Yes. Zero results -> [], one result -> [item], many results -> [items].
```

### 8.3 Variable lifetime

Questions:

- Does a variable survive through later traversals?
- Does a variable survive after `select(...)`?
- Does a variable survive after `array(...)`?
- Can inner variables shadow outer variables?

Recommended decision:

```text
Variables are row-scoped labels available to later operations in the same query.
Shadowing an existing variable name should be rejected for now.
```

### 8.4 `as_var` vs `assign`

Recommended decision:

```text
as_var(name) binds the current row itself.
assign(subquery, name) binds a computed array result from the current row.
```

## 9. Match Semantics

### 9.1 Field condition semantics

Clear:

```python
match(_key='admin')
match(eq('_key', 'admin'))
match(age > 10)
```

Questions:

- Should comparing missing field with `ne` match or not match?
- Should comparing missing field with `eq(None)` behave like `is_null`?

Recommended decision:

```text
Use is_null(field) for missing/null checks. Normal comparisons only match
present comparable values unless explicitly documented otherwise.
```

### 9.2 Traversal field conditions are existential

Implemented shape:

```python
match(eq(traverse().into()['_key'], 'admin'))
```

Question:

- This currently means "at least one subquery result has `_key == admin`".
  Is that correct?

Recommended decision:

```text
Yes. Traversal field comparison is existential.
```

### 9.3 `ne` on traversal operands

Ambiguous:

```python
match(ne(traverse().into()['_key'], 'admin'))
```

Possible meanings:

```text
at least one reachable node is not admin
no reachable node is admin
```

Recommended decision:

```text
ne on traversal operands remains existential: at least one reachable result has
field != value. Add explicit negation later for "none match".
```

## 10. Aggregation Inside `match(...)`

### 10.1 Count of connected nodes

Desired example:

```python
get('users-data-product.user_roles')
    .match(
        traverse_out('permissions-data-product.role_abilities')
            .into('permissions-data-product.abilities')
            .count() >= 3
    )
```

Questions:

- Should this be valid?
- Does the aggregation run from current row?
- Does it keep the row when count satisfies comparison?

Recommended decision:

```text
Yes. Aggregation inside match runs from the current row and returns a scalar
used by the comparison.
```

### 10.2 Count duplicates or unique?

Recommended decision:

```text
count() counts raw results. unique().count() counts unique results.
```

### 10.3 Which aggregations are allowed?

Recommended decision:

```text
Start with count() and unique().count(). Do not support array aggregation inside
match until array semantics are final.
```

## 11. Null And Missing Values

Clear:

```python
is_null(field)
```

matches missing OR explicit null.

Questions:

- Should `eq(field, None)` be identical to `is_null(field)`?
- Should `ne(field, None)` mean present and not null?
- Should `value_in(field, [None, 'x'])` include missing fields?

Recommended decision:

```text
Only is_null has missing-field semantics. Literal None comparisons operate on
explicit values only unless later specified.
```

## 12. Type Coercion

Questions:

- Does string `"3"` equal number `3`?
- Does int `3` equal float `3.0`?
- Are booleans comparable to numbers?
- Are regex operands always strings?

Recommended decision:

```text
No implicit Opium-level type coercion. Let backend compare values as stored, and
reject obviously invalid semantic comparisons where possible.
```

## 13. Error Behavior

Questions:

- Should unsupported but parseable features fail at compile time?
- Should ambiguous semantics fail loudly?
- Should unknown kwargs always fail?

Recommended decision:

```text
Fail loudly with custom parser/compiler exceptions. Never silently guess.
```

## 14. Provider Portability

Questions:

- Is Groovy closure support guaranteed?
- Is `TextP.regex` guaranteed?
- Is `has(field, null)` guaranteed?
- Are labels always collection names?
- Are ids always `collection/key`?

Recommended decision:

```text
Current compiler targets the known ArangoDB TinkerPop Provider COMPLEX setup.
If another provider/config is needed, add a provider profile instead of
weakening the current assumptions.
```
