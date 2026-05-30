# Questions For Completing The Opium Gremlin Compiler

This file contains only unresolved semantic questions.

Answered decisions are recorded in `docs/OPIUM_SEMANTICS.md`.

Please edit this file and answer questions inline. Concrete expected result
examples are more useful than prose.

## 1. `array(...)` Semantics

### 1.1 Is `array(sub_query)` per current row or global?

Example:

```python
get('users-data-product.user_roles').array(traverse().into())
```

Should this return:

```text
one neighbor array per user role
one global array for all user roles
something else
```

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```text
array(sub_query) is per current row. For each input row, run sub_query from that
row and fold the subquery result into one array for that row.
```

### 1.2 Does `array(...)` replace the current row or attach to it?

Example:

```python
get('users-data-product.user_roles', _key='admin')
    .array(
        traverse_out('permissions-data-product.role_abilities')
            .into('permissions-data-product.abilities')['_key']
    )
```

Should this return just the array:

```python
[
    [
        {"_key": "approve"},
        {"_key": "delete"},
        {"_key": "write"},
    ]
]
```

or should it preserve the original admin row and attach the array somehow:

```python
[
    {
        "_key": "admin",
        "array": [
            {"_key": "approve"},
            {"_key": "delete"},
            {"_key": "write"},
        ],
    }
]
```

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```text
array(...) replaces the current row with the array result. Use assign(...).select(...)
when the original row should be preserved and the computed array should be
attached as a named column.
```

### 1.3 What should this exact query return?

Using the e2e seed data:

```python
get('users-data-product.user_roles', _key='admin')
    .array(traverse_out('permissions-data-product.role_abilities')
    .into('permissions-data-product.abilities')['_key'])
```

Expected result:

```python
# TODO
```

Answer:

```text
TODO
```

## 2. `assign(...)`, `as_var(...)`, And `var(...)`

### 2.1 Is `assign(sub_query, name)` per current row?

Example:

```python
get('users-data-product.user_roles')
    .assign(traverse().into(), 'neighborhood')
```

Should each current user role get its own `neighborhood`, or should
`neighborhood` be one global value shared by all rows?

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```text
assign(sub_query, name) is per current row. For each input row, run sub_query
from that row, bind the result to name, and preserve the original current row.
```

### 2.2 Does `assign(...)` store one value or an array?

Example:

```python
get('users-data-product.user_roles')
    .assign(traverse().into(), 'neighborhood')
```

Should `neighborhood` always be an array of all subquery results, even when it
has zero or one result?

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```text
assign(...) stores an array of subquery results. Zero matches becomes an empty
array, one match becomes a one-item array.
```

### 2.3 What should this query return?

Using the e2e seed data:

```python
get('users-data-product.user_roles', _key='admin')
    .assign(
        traverse_in('users-data-product.user_role_subscriptions')
            .into('users-data-product.user_roles'),
        'neighborhood'
    )
    .select('_key', neighbors=var('neighborhood')['_key'])
```

Expected result:

```python
# TODO
```

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```python
[
    {
        "_key": "admin",
        "neighbors": [
            {"_key": "auditor"},
            {"_key": "editor"},
        ],
    }
]
```

Ordering should remain unspecified unless Opium gets an ordering operation.

### 2.4 What is the difference between `as_var` and `assign`?

Example:

```python
get('users-data-product.user_roles').as_var('role')
```

versus:

```python
get('users-data-product.user_roles')
    .assign(traverse().into(), 'neighbors')
```

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```text
as_var(name) binds the current row itself to name and preserves the current row.

assign(sub_query, name) runs sub_query from the current row, stores the subquery
result under name, and preserves the current row.
```

### 2.5 Does projection over an array variable map over array elements?

Example:

```python
select('_key', neighbors=var('neighborhood')['_key'])
```

If `neighborhood` is an array of entities, should `var('neighborhood')['_key']`
project `_key` for each entity in that array?

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```text
Yes. Projection over an array variable maps the projection over every array
element.
```

## 3. Aggregation Inside `match(...)`

### 3.1 What syntax should express "at least N connected nodes"?

Example candidate:

```python
get('users-data-product.user_roles')
    .match(
        traverse_out('permissions-data-product.role_abilities')
            .into('permissions-data-product.abilities')
            .count() >= 3
    )
```

Should this syntax be supported?

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```text
Yes. A traversal aggregation inside match should run from the current row. The
current row is kept when the aggregated value satisfies the comparison.
```

### 3.2 Should aggregation count duplicates or unique connected entities?

Example:

```python
get('platform-data-product.services')
    .match(
        traverse_out('platform-data-product.service_dependencies')
            .into('platform-data-product.services')
            .count() >= 3
    )
```

Should `count()` count every traversal result, or should the compiler deduplicate
connected entities before counting?

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```text
count() counts traversal results exactly as produced. Use unique().count() when
duplicates should be removed before counting.
```

### 3.3 Should zero connected nodes produce count `0`?

If a row has no matching connected nodes, should:

```python
traverse_out('x').into('y').count()
```

inside `match(...)` evaluate to `0` for that row?

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```text
Yes. Empty subquery aggregation should produce 0 for count().
```

### 3.4 Which aggregations should be allowed inside `match(...)`?

Currently documented aggregation methods include:

```python
count()
unique()
```

Should match aggregation support only `count()` for now, or also combinations
such as:

```python
unique().count()
array(...).flatten().count()
```

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```text
Support traversal.count() and traversal.unique().count() first. Leave array
aggregation inside match unsupported until array semantics are finalized.
```

### 3.5 How should non-numeric comparisons against count behave?

Should this be rejected?

```python
get('users-data-product.user_roles')
    .match(traverse().into().count() == '3')
```

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```text
Reject non-numeric comparisons against count() as invalid Opium semantics.
```

## 4. Existential Traversal Conditions

These are already implemented for simple field projection operands:

```python
get('users-data-product.user_roles')
    .match(eq(traverse().into()['_key'], 'admin'))
```

Current behavior is existential: the row is kept if at least one result from the
subquery satisfies the comparison.

### 4.1 Should `ne(...)` also be existential?

Example:

```python
get('users-data-product.user_roles')
    .match(ne(traverse_out('permissions-data-product.role_abilities')
        .into('permissions-data-product.abilities')['_key'], 'delete'))
```

Should this mean:

```text
keep rows where at least one reachable ability is not delete
```

or:

```text
keep rows where no reachable ability is delete
```

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```text
All traversal field comparisons are existential. Therefore ne(subquery[field],
value) means at least one subquery result has field != value. If we need "none
match value", add an explicit negation operator later.
```

### 4.2 Should `value_in(...)` be existential?

Example:

```python
get('users-data-product.user_roles')
    .match(value_in(
        traverse_out('permissions-data-product.role_abilities')
            .into('permissions-data-product.abilities')['_key'],
        ['read', 'approve']
    ))
```

Should this keep rows where at least one reachable ability key is in the list?

Answer:

```text
TODO
```

Recommended answer to approve or reject:

```text
Yes. value_in(subquery[field], values) is existential.
```
