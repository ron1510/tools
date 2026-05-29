# Implementation Decisions

This document explains the main design choices in the Opium parser/compiler
project. It is written for review: each section states what the code does, why
it does it, and what should be revisited later.

## 1. Parser And Compiler Are Separate

The parser builds a typed AST that represents the expression the user wrote. It
does not know how Gremlin works and does not execute anything.

Reason:

- Opium syntax can be stable before all Gremlin semantics are finished.
- Unsupported compiler features can fail with `UnsupportedOpiumCompilationError`
  instead of forcing the parser to reject valid documented syntax.
- Tests can separately prove "this parses" and "this compiles correctly".

Tradeoff:

- Some expressions may parse successfully and fail during compilation. This is
  intentional while Opium semantics are still being completed.

## 2. The AST Models Syntax, Not Meaning

Examples:

```python
CallExpr(function="get", args=[StringExpr("users")], kwargs={})
MethodCallExpr(receiver=..., method="limit", args=[NumberExpr(10)], kwargs={})
SubscriptExpr(receiver=..., field="_key")
```

These nodes do not say whether `get` becomes `g.V()` or whether `_key` is a
property. They only preserve the Opium expression structure.

Reason:

- The same AST could later compile to Gremlin Groovy, Gremlin Python bytecode, or
  another IR.
- Provider-specific decisions stay out of the parser.

## 3. Lark Grammar Is Opium-Like, Not Python

The grammar accepts a deliberately small Python-like expression subset:

- calls
- chained method calls
- positional and keyword arguments
- lists and simple dictionaries
- literals
- comparisons
- projection/subscript syntax

It rejects Python statements, imports, lambdas, comprehensions, assignment
statements, and arithmetic.

Reason:

- User input must never be evaluated as Python.
- The supported language should match documented Opium, not arbitrary Python.

## 4. Call Names Are Allow-Listed In The Transformer

The grammar can recognize any `NAME(...)`, but the transformer checks the name
against the documented Opium allow-list.

Reason:

- It keeps the grammar simple.
- It rejects unknown functions early with `UnsupportedOpiumSyntaxError`.
- It prevents accidental support for Python-looking calls that Opium does not
  define.

Tradeoff:

- Adding a new Opium keyword requires updating the allow-list.

## 5. Gremlin Target Is Currently Groovy Strings

The compiler emits strings such as:

```groovy
g.V().hasLabel('users-data-product.user_roles').limit(100)
```

Reason:

- The current Gremlin Server lab accepts Groovy scripts.
- String output is easy to inspect in unit tests.
- It lets us validate semantics before committing to Gremlin Python bytecode
  structure.

Tradeoff:

- Some expressions use Groovy closures, especially `_key` projection.
- Bytecode would eventually be safer and more structured, but it should come
  after the semantics are settled.

## 6. Resources Compile To Gremlin Labels

Opium:

```python
get('users-data-product.user_roles')
```

Gremlin:

```groovy
g.V().hasLabel('users-data-product.user_roles')
```

Reason:

- In the agreed ArangoDB TinkerPop Provider `COMPLEX` setup, Arango collections
  are exposed as Gremlin labels.
- This was verified in the live e2e lab with `g.V().label().dedup()` and
  `g.E().label().dedup()`.

Review point:

- This is provider/configuration-specific. If the provider mode changes, this
  mapping may need to change.

## 7. `get(...)` Starts From Vertices

The compiler treats `get(resource)` as a vertex lookup:

```groovy
g.V().hasLabel(resource)
```

Reason:

- Documented examples use `get` for entity collections.
- Edge documents are normally reached through `traverse(...)`, not root `get`.

Review point:

- If Opium should support root edge collections through `get(edge_collection)`,
  we need an explicit way to know whether a resource is a vertex collection or an
  edge collection.

## 8. `_key` Is Derived From Element Id

In the live provider, Arango ids appear as:

```text
collection/key
```

The compiler uses:

```groovy
hasId(TextP.endingWith('/admin'))
```

for `_key='admin'`, and strips the suffix for `_key` projection.

Reason:

- `_key` is not exposed as a normal property in the tested provider.
- `_key` is unique per collection, while the full id is unique across
  collections.

Review point:

- Suffix matching assumes ids are always `collection/key` and keys do not create
  ambiguous suffixes.

## 9. Projection Returns Maps, Not Raw Scalars

Opium:

```python
get('roles')['_key']
```

Current result shape:

```python
[{"_key": "admin"}]
```

Reason:

- You said the Python object should be returned as a key/value pair.
- It aligns projection syntax with `select(...)`, which naturally returns maps.
- Missing fields can be represented as explicit `None` values.

Tradeoff:

- This differs from a raw scalar projection model such as `["admin"]`.

## 10. Missing Properties Project As Null

Normal fields compile with:

```groovy
coalesce(values('field'), constant(null))
```

Reason:

- Gremlin `values('field')` drops traversers when the property is missing.
- Opium projection should preserve one output row per input element.
- Returning `null` makes result maps stable.

## 11. Edge `_from` And `_to` Are Reconstructed

The compiler uses:

```groovy
__.outV().id()
__.inV().id()
```

for `_from` and `_to`.

Reason:

- Your system policy guarantees edge documents have `_from` and `_to`.
- The live provider did not expose `_from` and `_to` through `values(...)`.
- Adjacent vertices preserve the same information for edge traversers.

Review point:

- This behavior is only valid when the current traverser is an edge.

## 12. Traversal Is Edge-First

Opium:

```python
get('roles').traverse_out('subscriptions')
```

Gremlin:

```groovy
.outE('subscriptions')
```

Then:

```python
.into('roles')
```

becomes:

```groovy
.otherV().hasLabel('roles')
```

Reason:

- Opium `traverse(...)` returns edge documents.
- `into(...)` is the operation that moves from those edges to vertices.
- This lets queries project edge fields before calling `into`.

## 13. Direction Mapping

Current mapping:

```text
traverse_any / direction='any'       -> bothE
traverse_out / direction='outbound'  -> outE
traverse_in / direction='inbound'    -> inE
```

Reason:

- It matches the natural Gremlin edge steps from the current vertex.
- It is live-tested on subscriptions, role abilities, memberships, and team
  hierarchy.

## 14. Deep Traversal Uses `repeat(...).emit().times(...)`

For depth traversal the compiler repeats an edge step and moves to the next
vertex inside the repeat body.

When `into()` is present, emitted traversers are vertices.

When `into()` is not present, the compiler labels each edge as `opium_edge` and
selects that edge back out after emission.

Reason:

- Opium says traversal returns intermediate depths.
- Opium also distinguishes edge results from vertex results.

Review point:

- The label name `opium_edge` is internal. If user-visible labels eventually
  share the same scope, this should become harder to collide with.

## 15. `match` And `match_all` Are AND

Multiple conditions compile as chained Gremlin filter steps.

Reason:

- Chained `.has(...)` steps naturally mean all conditions must match.
- This matches the documented examples for `match(...)`.

## 16. `match_any` Is OR

The compiler wraps condition traversals in Gremlin `or(...)`.

Reason:

- This directly expresses "any of these conditions".

Limitation:

- Only supported condition forms compile. Subquery and variable operands are
  parsed but still unresolved semantically.

## 17. `is_null` Means Missing Property

Current compilation:

```groovy
not(__.has('field'))
```

Reason:

- Arango documents often omit absent fields.
- The live e2e tests currently validate missing-field behavior.

Review point:

- If Opium needs to distinguish missing from explicitly stored `null`, this
  needs more work.

## 18. Regex Case-Insensitive Uses `(?i)`

Opium:

```python
regex_matches('name', '^a', caseInsensitive=True)
```

Gremlin:

```groovy
TextP.regex('(?i)^a')
```

Reason:

- `TextP.regex` uses Java regex syntax.
- `(?i)` is a standard Java regex inline flag.

## 19. Float Literals Render As Java Doubles

Opium:

```python
score >= 90.0
```

Gremlin:

```groovy
P.gte(90.0d)
```

Reason:

- Plain Groovy `90.0` is `BigDecimal`.
- The live ArangoDB TinkerPop Provider rejected `BigDecimal` predicate values.
- `90.0d` forces a Java double and passed live e2e tests.

## 20. `array` And `flatten` Are Basic Implementations

Current shape:

```groovy
.local(__...).fold()
.unfold()
```

Reason:

- This supports simple local subqueries from the documented examples.

Review point:

- Nested arrays, per-row scoping, and interactions with variables need stronger
  semantics before calling this complete.

## 21. `assign` Is First-Pass Only

Current shape:

```groovy
.sideEffect(__...fold().as('name'))
```

Reason:

- It gives a plausible label-based representation for assigned subquery results.

Review point:

- This is not yet strongly proven e2e.
- Computed `select` columns using assigned variables are intentionally skipped in
  live tests until semantics are finalized.

## 22. Tests Are Split By Layer

Parser tests:

- prove syntax and AST shape

Compiler tests:

- prove exact Gremlin string generation

E2E tests:

- prove generated Gremlin works against the live provider

Reason:

- A parser failure, compiler rendering failure, and provider behavior failure
  are different problems and should be diagnosed separately.

## 23. Skipped Tests Are Deliberate Markers

Skipped tests currently mark:

- default full-document materialization
- complex `assign/select`
- match operands that are subqueries
- match operands that are variables
- unresolved complex array/flatten semantics

Reason:

- These are known gaps, not forgotten tests.
- They keep the todo list executable and close to the test suite.

## 24. Main Open Decisions

Before claiming complete Opium support, these need final decisions:

1. Should root `get(edge_collection)` be supported for edge collections?
2. Should default results materialize full documents, and with which system
   fields?
3. Should `is_null` match missing fields, explicit null fields, or both?
4. What is the exact row/variable scope of `assign`?
5. What should computed `select` support beyond `var(...)` and field projection?
6. How should match conditions compare against subquery results?
7. When should the compiler move from Gremlin Groovy strings to Gremlin Python
   bytecode?
