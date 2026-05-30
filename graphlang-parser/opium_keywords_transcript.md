# Opium Keywords

This page describes the various keywords in Opium.

It is recommended to read earlier sections about Opium to understand key details about Opium.

> Note: This transcript was created from screenshots. Some long code examples were cut off horizontally in the images, so unreadable tails are marked with `...`.

## `get`

Specify the sources for a walk.

### Signature and Parameters

```python
get(*sources, _key=None)
```

- `sources` - one or more comma-delimited names of resources, of the form `{data-product-key}.{resource-key}`.
- `_key` - a resource `_key` to filter a specific entity from the resources. This is conceptually the same as appending `match(_key={value})`. Defaults to no filter.

### Examples

```python
get('users-data-product.user_roles')  # lists all 'User Role's

get('users-data-product.user_roles', 'permissions-data-product.abilities')
# lists all 'User Role's and 'Abilities'
```

## `traverse`

Extend the walk by traversing edges. This extends the walk to the edges themselves, not to the nodes. See the keyword `into`.

### Signature and Parameters

```python
traverse(*edge_resources, min_depth=1, max_depth=1, direction='any')
```

`traverse_any`, `traverse_out` and `traverse_in` are also available as syntactic sugar for passing their respective `direction` value.

- `edge_resources` - zero or more comma-delimited names of edge resources to consider, of the form `{data-product-key}.{resource-key}`. Omitting this parameter results in traversing all possible edge resources.
- `min_depth` - minimum amount of edges to traverse. Defaults to `1`.
- `max_depth` - maximum amount of edges to traverse. Defaults to `1`.
- `direction` - direction of the traversal to consider. Can be one of `any`, `outbound`, `inbound`. Defaults to `any`.

### Examples

```python
get('users-data-product.user_roles').traverse()
# lists all edges which are incident to a 'User Role'

get('users-data-product.user_roles').traverse(
    'users-data-product.user_role_subscriptions',
    direction='inbound'
)
# ...
```

## `into`

Extend the walk by traversing into the other side of edges. This is commonly used in conjunction after `traverse`.

### Signature and Parameters

```python
into(*node_resources)
```

- `node_resources` - zero or more comma-delimited names of node resources to consider, of the form `{data-product-key}.{resource-key}`. Omitting this parameter results in traversing into all possible node resources.

### Examples

```python
get('users-data-product.user_roles').traverse().into()
# lists all nodes which are neighbors of some 'User Role'

get('users-data-product.user_roles').traverse().into(
    'users-data-product.user_roles'
)
# lists all 'User Role's ...

get('users-data-product.user_roles').traverse(
    'users-data-product.user_role_subscriptions',
    direction='inbound'
).into(...)
# ...
```

## `skip`

Skip some of the results of a walk. This modifier is shared between all possible results of the current walk, i.e. it is a global modifier.

### Signature and Parameters

```python
skip(n)
```

- `n` - number of results to skip.

### Examples

```python
get('users-data-product.user_roles').skip(100)
# lists all 'User Role's, skipping the first 100

get('users-data-product.user_roles').traverse().skip(100).into(
    'users-data-product.user_roles'
)
# ...

get('users-data-product.user_roles').skip(100).traverse(
    'users-data-product.user_role_subscriptions',
    direction='...'
)
# ...
```

## `limit`

Limit the number of results of a walk. This modifier is shared between all possible results of the current walk, i.e. it is a global modifier.

### Signature and Parameters

```python
limit(n)
```

- `n` - maximum number of results to return.

### Examples

```python
get('users-data-product.user_roles').limit(100)
# lists the first 100 'User Role's

get('users-data-product.user_roles').traverse().limit(100).into(
    'users-data-product.user_roles'
)
# ...

get('users-data-product.user_roles').skip(100).limit(100).traverse(
    'users-data-product.user_role_subscriptions',
    direction='...'
)
# ...
```

## `count`

Count the number of results of a walk. This considers all possible results of the walk, i.e. an aggregation.

### Signature and Parameters

```python
count()
```

### Examples

```python
get('users-data-product.user_roles').count()
# Total number of 'User Role's

get('users-data-product.user_roles').limit(100).count()
# Total number of 'User Role's. Result is <= 100

get('users-data-product.user_roles').limit(100).skip(100).count()
# A creative way to say 0
```

## `array`

Transform the result of a walk into a singular array.

### Signature and Parameters

```python
array(sub_query)
```

- `sub_query` - another query that starts with the current result and generates an array.

### Examples

```python
get('users-data-product.user_roles').array(traverse().into())
# list of neighborhoods of 'User Role's. Each neighborhood ...
```

## `flatten`

Flatten, also known as concat or chain, the result of a walk into a singular array.

### Signature and Parameters

```python
flatten(depth=1)
```

- `depth` - number of nested array levels to flatten. Defaults to `1`.

### Examples

```python
get('users-data-product.user_roles').array(traverse().into()).flatten()
# list of neighboring nodes of 'User Role's
```

## `as_var`

Mark the current result of a walk. The walk itself is not modified, so it should be used in conjunction with `var`.

### Signature and Parameters

```python
as_var(var_name)
```

- `var_name` - a string that represents the name of the mark that would store the current result.

### Examples

```python
get('users-data-product.user_roles').as_var('user_role')
# list of all 'User Role's. Each 'User Role' is marked ...
```

## `var`

Recall the value of a mark. The walk itself is not modified, so it should be used in conjunction with `select`.

Variables support subscript notation. See `[] notation` for details.

> Notice: Variables support additional functions and operations besides `[] notation`, but to keep things simple, only the most basic and commonly used options are presented.

### Signature and Parameters

```python
var(var_name)
```

- `var_name` - a string that represents the name of the mark that stores the result.

### Examples

See the `select` keyword for examples.

## `assign`

Perform a sub-query and assign its result in a variable / mark. The walk itself is not modified, so it should be used in conjunction with `var`.

### Signature and Parameters

```python
assign(sub_query, var_name)
```

- `sub_query` - a query that starts with the current result and generates the result to be stored / marked.
- `var_name` - a string that represents the name of the variable / mark that would store the result.

### Examples

```python
get('users-data-product.user_roles').assign(
    traverse().into(),
    'neighborhood'
)
# list of all 'User Role's. Each ...
```

## `select`

Override the result of a walk.

### Signature and Parameters

```python
select(*columns, **computed_columns)
```

- `columns` - zero or more specific column names to return from the result.
- `computed_columns` - zero or more keyword arguments that specify the columns and their values. The argument's key is the name of the column; the argument's value is the value of the cell in that column. The value can be a mark / variable or a projection thereof. See `[] notation`.

> Notice: The value of a `computed_column` could take other forms, but to keep things simple, only the most basic and commonly used options are presented.

### Examples

```python
get('users-data-product.user_roles').assign(
    traverse().into(),
    'neighborhood'
).select(
    '_key',
    neighbors=var('neighborhood')
)
# ...
```

## `[] notation`

Project the result of a walk into one of its dimensions, i.e. fields or attributes.

### Signature and Parameters

```python
[field_name]
```

- `field_name` - a string that specifies the name of the field.
- This is a subscript notation.

### Examples

```python
get('users-data-product.user_roles')['_key']
# Returns the '_key's of all 'User Role's. This is a list of '_key's.

get('users-data-product.user_roles').assign(
    traverse().into(),
    'neighborhood'
).select(
    '_key',
    neighbors=var('neighborhood')['_key']
)
# ...
```

## `unique`

Deduplicate the results of a walk. This modifier is shared between all possible results of the current walk, i.e. it is a global modifier.

### Signature and Parameters

```python
unique()
```

### Examples

```python
get('users-data-product.user_roles').unique()
# lists all unique 'User Role's. This is redundant, as each entity is already unique.

get('users-data-product.user_roles').traverse().into(
    'users-data-product.user_roles'
).unique()
# lists all unique ...

get('users-data-product.user_roles').traverse(
    'users-data-product.user_role_subscriptions',
    max_depth=4
).unique()
# ...
```

## `match`

Conditionally discard the result of a walk.

### Signature and Parameters

```python
match(*conditions)
```

- `conditions` - zero or more comma-delimited conditions to check. If all of them are true, keep the result; otherwise, discard the result.

`match` is actually an alias for `match_all`. Its counterpart is `match_any`, which keeps the result if any of the conditions are true, and otherwise discards the result.

Conditions are constructed using special functions or operators. The arguments themselves can take the form of:

- a sub-query that starts with the current result and generates the argument's value
- a variable / mark
- a literal value, for example `5` or `"Hello World"`
- a specific field name of the entry in the current result

### Condition Constructions

#### Exact Match

Keyword-style equality comparison.

##### Examples

```python
get('users-data-product.user_roles').match(_key='hello')
# Returns all 'User Role's whose '_key' equals 'hello'.

get('users-data-product.user_roles').match(_key='hello', name='goodbye')
# Returns all 'User Role's whose '_key' equals 'hello' and whose name equals 'goodbye'.

get('users-data-product.user_roles').match_any(_key='hello', name='goodbye')
# ...
```

#### Classical comparison operators

```text
== / eq
<  / lt
>  / gt
<= / lte
>= / gte
ne
```

Classical comparison operators and their respective functions. Note: `ne`, meaning not equal, has no operator equivalent.

##### Examples

```python
get('users-data-product.user_roles').match(_key='hello')
# Returns all 'User Role's whose '_key' equals 'hello'.

get('users-data-product.user_roles').match(eq('_key', 'hello'))
# Another way to write it.

get('users-data-product.user_roles').match(age > 48, age <= 85)
# Returns all 'User Role's whose age, a fictitious field, is between those bounds.

get('users-data-product.user_roles').match(gt('age', 48), lte('age', 85))
# Another way to write it.

get('users-data-product.user_roles').match(ne('_key', 'hello'))
# Returns all 'User Role's whose '_key' is NOT 'hello'.
```

#### `value_in`, `nin`

Containment operator `value_in` and its logical counterpart `nin`.

##### Examples

```python
get('users-data-product.user_roles').match(
    value_in('_key', ['one', 'two', 'three'])
)
# Returns all 'User Role's whose '_key' is one of the listed values.

get('users-data-product.user_roles').match_any(
    match(_key='one'),
    match(_key='two'),
    match(_key='three')
)
# Another way to write it.

get('users-data-product.user_roles').match(
    nin('_key', ['one', 'two', 'three'])
)
# Returns all the other 'User Role's.
```

#### `is_null`

Null check.

##### Examples

```python
get('users-data-product.user_roles').match(
    is_null('<non_existent_field>')
)
# Returns all 'User Role's, as a 'User Role' does not have that field.
```

#### `regex_matches`

Check if a specified regex matches text.

### Signature and Parameters

```python
regex_matches(text, regex, caseInsensitive=False)
```

- `text` - text argument to match against.
- `regex` - a regexp to match against.
- `caseInsensitive` - whether to ignore letter casing during matches. Defaults to `False`.

> Notice: The regexp is not modified whatsoever. Make sure to anchor it as needed, i.e. use `^` and/or `$` as needed for full / partial matches.

##### Examples

```python
get('users-data-product.user_roles').match(
    regex_matches('_key', '.*')
)
# lists all 'User Role's, without any effective filtering.

get('users-data-product.user_roles').match(
    regex_matches('_key', '^hello', caseInsensitive=True)
)
# lists all ...
```

## Currently Undocumented Keywords

These keywords' semantics are subject to change and/or are for very specific use-cases.

- `to_graph`
- `field`
- `literal`
- `negate/not`
- `any_in_path`
- `all_in_path`
