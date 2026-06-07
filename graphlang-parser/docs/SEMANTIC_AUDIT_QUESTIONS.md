# Semantic Audit Questions

This file contains only questions that are still ambiguous after reading
`opium_keywords_transcript.md` and the current project semantics.

Answered decisions belong in `docs/OPIUM_SEMANTICS.md`.

## 1. Default Full-Document Materialization

The transcript says unprojected queries return full documents/entities, but it
does not define the exact Python object shape.

Questions:

- Should unprojected vertex rows include `_key` and `_id` in addition to stored
  user fields?
- Should unprojected edge rows include `_key`, `_id`, `_from`, and `_to` in
  addition to stored edge fields?
- Should provider-internal fields be filtered out?
- Should rows contain only fields physically present on that row, or should the
  result normalize to a union schema with missing fields set to `None`?

## 2. `assign(...)` Value Shape

The transcript shows `assign(subquery, name)` preserving the current row and
making the named value available later through `var(name)`.

What is still not fully specified:

- If the subquery returns zero rows, is the variable value `[]`, `None`, or is
  the current row dropped?
- If the subquery returns exactly one row, is the variable value the single item
  or a one-item array?
- Are all `assign(...)` subqueries folded into arrays, or only subqueries that
  naturally return multiple rows such as traversals?

## 3. Projection Over Array Variables

The transcript supports:

```python
select('_key', neighbors=var('neighborhood')['_key'])
```

The expected intent appears to be mapping `_key` over the assigned neighborhood,
but the transcript does not state every edge case.

Questions:

- If `var('neighborhood')` is an array, should `var('neighborhood')['_key']`
  always preserve array shape?
- If the array is empty, should the projected value be `[]`?
- If an item is missing the projected field, should the projected item be
  `None`, should it be omitted, or should compilation fail?

## 4. Variable Lifetime And Shadowing

The transcript explains marks/variables, but not full lifetime rules.

Questions:

- Do variables survive through later `traverse`, `into`, `match`, `array`, and
  `flatten` operations?
- Does `select(...)` end the variable scope or can later chain operations still
  use earlier variables?
- Should rebinding an existing variable name with `as_var(...)` or `assign(...)`
  be rejected?

## 5. Traversal Predicate Negation

Traversal field predicates are currently treated as existential conditions.

Example:

```python
match(eq(traverse().into()['_key'], 'admin'))
```

means: keep the current row if at least one reached entity has `_key == "admin"`.

Question:

- Should `ne(traverse().into()['_key'], 'admin')` mean "at least one reached
  entity is not admin", or "no reached entity is admin"?

## 6. `unique()` Equality

The transcript says `unique()` removes duplicate results, but does not define
the equality basis for every result type.

Questions:

- For graph elements, should `unique()` deduplicate by element id?
- For maps from `select(...)`, should it deduplicate by full map equality?
- For scalar projection, should it deduplicate by scalar value?

## 7. Method Ordering And Type Transitions

The parser accepts documented expression syntax, but the transcript does not
define every invalid chain.

Examples:

```python
get('x').count().limit(1)
get('x').select('_key').traverse()
get('x')['_key'].traverse()
```

Questions:

- Should the compiler track current result type and reject invalid transitions?
- Which transitions should be invalid versus delegated to the backend?

## 8. Dict Literals

The parser accepts simple dict literals for syntax completeness, but the
transcript examples do not use them.

Questions:

- Are dict literals actually part of Opium values?
- If yes, which functions/methods can receive them?
- If no, should the parser stop accepting them until a documented feature needs
  them?
