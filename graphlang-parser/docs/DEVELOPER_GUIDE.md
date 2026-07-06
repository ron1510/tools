# Developer Guide

This guide is for engineers who need to move this repository into an
organization environment, review it, change it, and know which tests prove what.

## Project Purpose

The project has two jobs:

1. Parse documented Opium expressions into a typed Pydantic AST.
2. Compile the supported AST subset into `GremlinGroovyString` values for
   ArangoDB TinkerPop Provider in `COMPLEX` mode.

The package does not execute Opium expressions. It does not evaluate Python. It
does not connect to ArangoDB or Gremlin Server during normal library use.

Execution happens only in optional e2e tests under `tests/e2e`.

## Repository Layout

```text
opium_parser/
  __init__.py
  grammar.lark
  ast_nodes.py
  parser.py
  transformer.py
  compiler.py
  gremlin_ir.py
  gremlin_renderer.py
  errors.py

tests/
  parser/
  compiler/
  e2e/
  fixtures/

scripts/
  seed_opium_e2e.py

e2e/
  gremlin-opium-values.yaml

docs/
  *.md
```

## Main Runtime APIs

Parser:

```python
from opium_parser import parse_opium

query = parse_opium("get('users-data-product.user_roles').limit(100)")
```

Compiler:

```python
from opium_parser import compile_opium_to_gremlin

gremlin = compile_opium_to_gremlin(
    "get('users-data-product.user_roles').limit(100)"
)
```

Compile from an already parsed AST:

```python
from opium_parser import compile_ast_to_gremlin, parse_opium

query = parse_opium("get('users-data-product.user_roles')")
gremlin = compile_ast_to_gremlin(query)
```

## Dependency Setup

Python:

```powershell
python --version
```

The project requires Python 3.11 or newer.

Recommended local setup:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

For live e2e tests:

```powershell
python -m pip install -e ".[dev,e2e]"
```

## Normal Verification Commands

```powershell
python -m ruff check .
python -m mypy
python -m pytest -q
```

Expected current local status:

```text
262+ passed, skipped tests vary by whether live e2e is enabled
```

The skipped tests are not ignored work. They are deliberate markers for
compiler/language gaps that are still under review.

## Live E2E Verification

The e2e suite requires:

- Kubernetes access
- ArangoDB lab pod
- Gremlin Server lab deployment
- local port-forward to Gremlin Server
- `gremlinpython==3.8.1`

Seed ArangoDB:

```powershell
kubectl port-forward -n gremlin-lab service/arangodb-lab 8529:8529
python scripts/seed_opium_e2e.py --url http://127.0.0.1:8529
```

Deploy Gremlin Server config:

```powershell
helm upgrade --install gremlin-arangodb-poc ..\arangodb-tinkerpop-gremlin\charts\gremlin-arangodb-poc --namespace gremlin-lab -f e2e\gremlin-opium-values.yaml
kubectl rollout status deployment/gremlin-arangodb-poc -n gremlin-lab --timeout=120s
kubectl port-forward -n gremlin-lab service/gremlin-arangodb-poc 8182:8182
```

Run live e2e tests:

```powershell
$env:OPIUM_RUN_E2E='1'
$env:GREMLIN_URI='ws://localhost:8182/gremlin'
python -m pytest tests\e2e -q -rs
```

Expected current live status:

```text
70 passed, 2 skipped
```

## How To Add A New Opium Keyword

A new keyword usually requires changes in this order:

1. Add syntax support if the grammar cannot already parse it.
2. Add the function/method name to `ALLOWED_CALL_NAMES` in `transformer.py`.
3. Add AST tests under `tests/parser`.
4. Decide semantics in `docs/OPIUM_SEMANTICS.md`.
5. Add compiler behavior in `compiler.py`.
6. Add exact Gremlin string tests under `tests/compiler`.
7. Add live behavior tests under `tests/e2e` if the feature reaches the backend.
8. Update `docs/COMPILER_COVERAGE.md`.

Do not add compiler behavior before documenting the intended semantics. The
project's main risk is silently generating plausible but wrong Gremlin.

## How To Add A Parser Feature

Parser features are syntax-only. They should not know about Gremlin.

Typical steps:

1. Update `grammar.lark`.
2. Update `transformer.py` if a new parse tree shape needs conversion.
3. Add or update Pydantic models in `ast_nodes.py` only if the current AST
   cannot represent the syntax cleanly.
4. Add AST shape tests under `tests/parser`.
5. Add invalid syntax tests if the feature introduces new rejection paths.

Parser tests should assert typed AST shape, not only that parsing succeeds.

## How To Add A Compiler Feature

Compiler features should start from a concrete AST shape and a documented
semantic decision.

Typical steps:

1. Add a compiler unit test with the exact Gremlin string you expect.
2. Implement the compiler behavior.
3. Add invalid semantic tests when needed.
4. Add e2e tests when the feature changes backend behavior.
5. Update coverage docs.

Compiler unit tests are intentionally string-based. That makes generated
Gremlin easy to review. It also makes provider-specific decisions visible.

The compiler APIs return `GremlinGroovyString`, a `NewType` over `str`. Runtime
behavior remains string-like, but strict mypy can distinguish generated Gremlin
Groovy from arbitrary text.

## Static Typing Policy

The package is checked with strict mypy:

```powershell
python -m mypy
```

The mypy config currently checks `opium_parser` in strict mode. Tests are not
strict-typed yet because many tests intentionally exercise runtime shapes and
external e2e behavior.

## Error Handling Rules

Use parser errors when source text is not valid supported Opium syntax:

- `UnsupportedOpiumSyntaxError`
- `InvalidOpiumExpressionError`

Use compiler errors when source text is valid Opium syntax but cannot or should
not compile:

- `UnsupportedOpiumCompilationError`
- `InvalidOpiumSemanticError`

Examples:

```python
get('x').unknown()
```

Parser-level unsupported syntax, because `unknown` is not an allowed Opium name.

```python
get('x').limit('ten')
```

Compiler-level semantic error, because `limit` exists but requires an integer.

## Important Provider Assumptions

The compiler assumes:

- ArangoDB TinkerPop Provider runs in `COMPLEX` mode.
- Arango collection names are Gremlin labels.
- Vertex resources use `g.V().hasLabel(...)`.
- Edge resources are reached through edge traversal steps such as `outE(...)`.
- Gremlin ids look like `collection/key`.
- Opium `_key` is derived from the suffix after the final `/`.
- Unprojected terminal vertices and edges are materialized as plain result maps
  at the final compiler boundary, not while composing intermediate traversal
  steps.
- `_from` and `_to` on edge traversers are parsed from the provider edge string
  because adjacent-vertex steps fail on dangling endpoints.

These assumptions are live-tested. They are still provider-specific.

## Known Incomplete Areas

The remaining high-value incomplete areas are:

- exact complex `assign(...)` semantics
- exact `array(...)` row scope and replacement/attachment behavior
- eventual Gremlin Python bytecode output
- broader performance testing against real data volume

Do not treat a passing local test suite as proof of complete Opium compatibility.
It proves only the supported subset documented in `COMPILER_COVERAGE.md`.

## Recommended Review Order

For a code review, read in this order:

1. `docs/OPIUM_SEMANTICS.md`
2. `docs/IMPLEMENTATION_DECISIONS.md`
3. `docs/COMPILER_WALKTHROUGH.md`
4. `opium_parser/grammar.lark`
5. `opium_parser/ast_nodes.py`
6. `opium_parser/transformer.py`
7. `opium_parser/compiler.py`
8. `tests/parser`
9. `tests/compiler`
10. `tests/e2e/test_gremlin_arangodb.py`
11. `scripts/seed_opium_e2e.py`

That order makes the code easier to criticize because you first understand the
language contract, then the implementation choices, then the tests.
