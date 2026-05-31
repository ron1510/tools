# Testing Strategy

For exact e2e graph shape, read `docs/E2E_GRAPH_REFERENCE.md`. For setup and
commands, read `docs/DEVELOPER_GUIDE.md` and `docs/E2E_LAB.md`.

The test suite is split by responsibility so failures point at the right layer.

## Parser Tests

Location:

```text
tests/parser
```

These tests assert typed AST shape. They do not care about Gremlin output.

Coverage includes:

- documented `get`, traversal, pagination, aggregation, projection, variable,
  and match syntax
- nested subqueries
- complex chained expressions
- unsupported syntax and custom parser/semantic exceptions

## Compiler Tests

Location:

```text
tests/compiler
```

These tests compile typed Opium expressions into exact Gremlin Groovy strings.
They are fast unit tests and do not require Kubernetes or Gremlin Server.

Coverage includes:

- collection label selection
- `_key` filters and projections
- traversal direction and depth compilation
- `into`, `skip`, `limit`, `count`, `unique`
- simple `array` / `flatten`
- `as_var`, `var`, `assign`, and `select` string generation
- match predicates, including comparisons, containment, null checks, regex, and
  float literal rendering as Java doubles
- complex mixed queries that combine filtering, traversal, projection, and
  aggregation

Compiler tests also include skipped placeholders for semantic areas that are
specified but not implemented yet, or still awaiting a final semantic decision.
This keeps missing work visible without making the normal suite red.

## Property Tests

Location:

```text
tests/property
```

These tests use Hypothesis for bounded parser/compiler invariants. They do not
replace exact example tests. They cover generated valid parser inputs, targeted
invalid syntax, generated compiler-supported inputs, invalid compiler semantics,
and Pydantic AST serialization round trips.

The default Hypothesis profile is intentionally small enough to run in normal
`pytest`. For deeper local or CI runs:

```powershell
$env:OPIUM_HYPOTHESIS_PROFILE='extended'
python -m pytest tests\property -q
```

## E2E Tests

Location:

```text
tests/e2e
```

These tests run generated Gremlin against the local ArangoDB TinkerPop Provider
lab. They are skipped by default and run only when:

```powershell
$env:OPIUM_RUN_E2E='1'
```

The fixture graph is intentionally multi-domain:

- roles
- users
- abilities
- teams
- role subscriptions
- role abilities
- user memberships
- team hierarchy

The live e2e suite proves that the compiler's current assumptions match the
provider in `COMPLEX` mode: collections are labels, document ids are
`collection/key`, edge endpoints can be projected through adjacent vertices, and
the supported Opium subset returns the expected data.

The live suite also includes skipped expected-result tests for specified
semantics that are not implemented yet, such as match operands based on
subqueries or variables.

## Normal Commands

```powershell
python -m ruff check .
python -m mypy
python -m pytest -q
```

Live e2e:

```powershell
$env:OPIUM_RUN_E2E='1'
$env:GREMLIN_URI='ws://localhost:8182/gremlin'
python -m pytest tests\e2e -q -rs
```
