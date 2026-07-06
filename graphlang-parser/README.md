# Opium Parser

`opium-parser` parses the documented Opium query expression subset into a typed
Pydantic AST. It can also compile the supported AST subset into typed Gremlin
Groovy query strings.

## Usage

```python
from opium_parser import parse_opium

query = parse_opium("get('users-data-product.user_roles').limit(100)")
print(query)
```

Example output shape:

```python
Query(
    root=MethodCallExpr(
        receiver=CallExpr(
            function="get",
            args=[StringExpr("users-data-product.user_roles")],
            kwargs={},
        ),
        method="limit",
        args=[NumberExpr(100)],
        kwargs={},
    )
)
```

## Gremlin Compilation

```python
from opium_parser import compile_opium_to_gremlin

query = compile_opium_to_gremlin("get('users-data-product.user_roles').limit(100)")
print(query)
```

Output:

```groovy
g.V().hasLabel('users-data-product___user_roles').limit(100).map{...}
```

Opium keeps dotted logical resource names. The compiler replaces each `.` with
`___` when targeting Arango vertex and edge collections:

```python
get('users-data-product.user_roles')
```

compiles to:

```groovy
g.V().hasLabel('users-data-product___user_roles').map{...}
```

The sequence `___` is reserved and rejected in logical resource names. Projected
`_id`, `_from`, and `_to` values are translated back to dotted logical prefixes.
Unprojected terminal vertex results are materialized as plain maps containing
`_key`, `_id`, and all normal document properties. Unprojected terminal edge
results are materialized as plain maps containing `_key`, `_id`, `_from`, `_to`,
and all normal edge properties.

## Supported Opium Subset

The parser supports documented expression forms such as:

```python
get('users-data-product.user_roles')
get('users-data-product.user_roles', _key='admin')
get('users-data-product.user_roles').traverse().into().limit(100)
get('users-data-product.user_roles').assign(traverse().into(), 'neighborhood')
get('users-data-product.user_roles')['_key']
var('neighborhood')['_key']
get('users-data-product.user_roles').match(gt('age', 48), lte('age', 85))
```

Supported syntax includes:

- function calls and chained method calls
- positional and keyword arguments
- nested function calls and subqueries
- string, integer, float, boolean, and null literals
- list literals and simple dict literals
- string or identifier subscripts
- comparison operators: `==`, `!=`, `<`, `>`, `<=`, `>=`

Allowed call and method names are:

```text
get, traverse, traverse_any, traverse_out, traverse_in, into, skip, limit,
count, array, flatten, as_var, var, assign, select, unique, match, match_all,
match_any, eq, lt, gt, lte, gte, ne, value_in, nin, is_null, regex_matches
```

## Known Limitations

This is an Opium parser, not a Python evaluator. Unsupported syntax includes:

- arithmetic expressions
- lambdas
- comprehensions
- imports
- assignments outside Opium's `assign(...)` call
- arbitrary Python statements or multiline blocks
- undocumented Opium keywords such as `to_graph`, `field`, `literal`, `negate`,
  `not`, `any_in_path`, and `all_in_path`

Unknown function or method names raise `UnsupportedOpiumSyntaxError`. Duplicate
keyword arguments raise `InvalidOpiumExpressionError`.

## Structured Errors

Parser and compiler exceptions expose a structured `.detail` payload:

```python
from opium_parser import parse_opium
from opium_parser.errors import OpiumParserError

try:
    parse_opium("get('x').limit(1 + 2)")
except OpiumParserError as exc:
    print(exc.detail.code)
    print(exc.detail.stage)
    print(exc.detail.span)
```

The old exception classes are still used, but callers can now inspect stable
error codes, stage, expected/actual values, optional source span, and context.

## Logging

The library emits structured standard-library logging records from:

```text
opium_parser.parser
opium_parser.compiler
```

It installs only a `NullHandler`; applications remain responsible for log
levels, handlers, formatting, destinations, and retention.

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(event)s %(message)s",
)
```

Successful parsing and compilation emit `INFO` records. Expected invalid or
unsupported queries emit `WARNING` records without tracebacks. Unexpected
internal failures emit `ERROR` records with exception information.

Stable event names include:

```text
opium.parse.started
opium.parse.succeeded
opium.parse.failed
opium.parse.internal_error
opium.compile.started
opium.compile.succeeded
opium.compile.failed
opium.compile.internal_error
```

Records provide structured fields such as `opium_source`, `gremlin_query`,
`parse_duration_ms`, `compile_duration_ms`, `total_duration_ms`, `error_code`,
`error_stage`, and `error_context`. Start events use `DEBUG`; successful
completion events use `INFO`.

Opium and generated Gremlin queries are logged in full. They can contain
identifiers and literal values, so consuming applications must choose
appropriate access controls and retention policies.

## Compilation Limitations

The compiler is intentionally conservative. It supports the documented common
forms for `get`, traversal, pagination, aggregation, projections, variables,
`select`, and match predicates. Parsed expressions with unclear Gremlin semantics
raise `UnsupportedOpiumCompilationError` or `InvalidOpiumSemanticError`.

Current assumptions and limitations:

- output is a Gremlin Groovy string, not Gremlin Python bytecode
- the public compiler return type is `GremlinGroovyString`, a domain-specific
  `NewType` over `str`
- resources compile as `hasLabel(...)`
- Arango `_key` is compiled through Gremlin `id()` because the TinkerPop
  provider exposes document ids as `collection/key`, not as a normal `_key`
  property; subscript projection returns scalar values such as `"admin"`, while
  `select('_key')` returns maps such as `{"_key": "admin"}`
- float literals are rendered as Java double literals, for example `90.0d`,
  because this ArangoDB provider rejects Groovy `BigDecimal` predicate values
- `regex_matches(...)` compiles with `TextP.regex(...)`
- traversal depths with `min_depth` / `max_depth` are compiled for the current
  edge-first traversal model
- match operands based on current-row subqueries and row-scoped variables are
  supported for the tested projection/comparison shapes
- complex `assign` and complex `array` still need semantic completion
- Gremlin strings are rendered only; they are never executed by this package

## ArangoDB / Gremlin E2E Tests

The e2e tests expect an ArangoDB TinkerPop provider in `COMPLEX` mode with
collections exposed as Gremlin labels. They are skipped by default.

Port-forward ArangoDB and seed the disposable lab graph:

```powershell
kubectl port-forward -n gremlin-lab service/arangodb-lab 8529:8529
python scripts/seed_opium_e2e.py --url http://127.0.0.1:8529
```

Deploy the Gremlin lab chart with the Opium graph config:

```powershell
helm upgrade --install gremlin-arangodb-poc ..\arangodb-tinkerpop-gremlin\charts\gremlin-arangodb-poc --namespace gremlin-lab -f e2e\gremlin-opium-values.yaml
kubectl rollout status deployment/gremlin-arangodb-poc -n gremlin-lab --timeout=120s
kubectl port-forward -n gremlin-lab service/gremlin-arangodb-poc 8182:8182
```

Run the live tests:

```powershell
python -m pip install -e ".[e2e]"
$env:OPIUM_RUN_E2E='1'
$env:GREMLIN_URI='ws://localhost:8182/gremlin'
python -m pytest tests\e2e -q
```

Run static typing and linting:

```powershell
python -m mypy
python -m ruff check .
```

## Parsing vs Compilation

The AST preserves the syntax of the query. The compiler consumes that AST and
translates the supported Opium semantics into Gremlin Groovy. Parser support and
compiler support are intentionally separate, so newly parsed syntax can remain
blocked at compilation until its Gremlin behavior is explicit.

## Deeper Documentation

- [Developer guide](docs/DEVELOPER_GUIDE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Compiler walkthrough](docs/COMPILER_WALKTHROUGH.md)
- [Compiler coverage and readiness](docs/COMPILER_COVERAGE.md)
- [ArangoDB Gremlin e2e lab](docs/E2E_LAB.md)
- [E2E graph reference](docs/E2E_GRAPH_REFERENCE.md)
- [Opium semantics](docs/OPIUM_SEMANTICS.md)
- [Implementation decisions](docs/IMPLEMENTATION_DECISIONS.md)
- [Migration guide](docs/MIGRATION_GUIDE.md)
- [Review checklist](docs/REVIEW_CHECKLIST.md)
- [Testing strategy](docs/TESTING_STRATEGY.md)
- [Learning roadmap](docs/LEARNING_ROADMAP.md)
- [Questions for compiler completion](docs/QUESTIONS_FOR_COMPILER_COMPLETION.md)
- [Semantic audit questions](docs/SEMANTIC_AUDIT_QUESTIONS.md)
