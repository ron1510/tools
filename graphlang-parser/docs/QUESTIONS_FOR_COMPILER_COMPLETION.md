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

### 1.2 What should this exact query return?

Using the e2e seed data:

```python
get('users-data-product.user_roles', _key='admin')
    .array(traverse_out('veto-data-product.role_abilities')
    .into('veto-data-product.abilities')['_key'])
```

Expected result:

```python
# TODO
```

Answer:

```text
TODO
```

### 1.3 How should nested arrays behave with `flatten(depth=...)`?

Examples:

```python
flatten()
flatten(depth=1)
flatten(depth=2)
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

### 2.2 What should this query return?

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

### 2.3 What is the difference between `as_var` and `assign`?

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

## 3. Computed `select(...)` Columns

### 3.1 How should computed columns work?

Example:

```python
select('_key', neighbors=var('neighborhood')['_key'])
```

Should computed columns be scalar, arrays, maps, or whatever the expression
returns?

Answer:

```text
TODO
```

## 4. Match Conditions

### 4.1 Can condition operands be subqueries?

Example:

```python
match(eq(traverse().into()['_key'], 'admin'))
```

Should this be supported? If yes, what should it mean?

Answer:

```text
TODO
```

### 4.2 Can condition operands be variables?

Example:

```python
match(eq(var('role')['_key'], 'admin'))
```

Should this be supported? If yes, what should it mean?

Answer:

```text
TODO
```

### 4.3 How should `is_null(field)` behave?

Should `is_null('x')` match:

```text
missing property only
explicit null only
missing property OR explicit null
```

Answer:

```text
TODO
```

