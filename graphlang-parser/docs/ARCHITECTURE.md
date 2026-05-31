# Opium Parser And Compiler Architecture

For hands-on setup and review workflow, start with `docs/DEVELOPER_GUIDE.md`.
For a line-by-line explanation of compiler behavior, read
`docs/COMPILER_WALKTHROUGH.md`.

This project has two separate responsibilities:

1. Parse documented Opium query expressions into a typed Python AST.
2. Compile the supported AST subset into Gremlin Groovy strings for ArangoDB
   TinkerPop Provider in `COMPLEX` mode.

The package never evaluates Opium as Python and never executes generated
Gremlin. Execution only happens in optional e2e tests through a live Gremlin
Server.

## Pipeline

```text
Opium source text
  -> Lark parser
  -> syntax-first Pydantic Opium AST
  -> semantic compiler
  -> Gremlin traversal string
  -> optional external Gremlin Server execution
```

The parser and compiler are intentionally separate. The parser accepts the
documented expression syntax and produces a faithful syntax tree. The compiler
then decides whether that parsed expression has supported Gremlin semantics.

That means an expression can parse successfully but still fail compilation with
`UnsupportedOpiumCompilationError` or `InvalidOpiumSemanticError`.

## Parser Layer

Main files:

- `opium_parser/grammar.lark`
- `opium_parser/transformer.py`
- `opium_parser/ast_nodes.py`
- `opium_parser/parser.py`

Public API:

```python
from opium_parser import parse_opium

query = parse_opium("get('users-data-product.user_roles').limit(100)")
```

The parser returns:

```python
Query(root=...)
```

The AST nodes are frozen Pydantic models. They support `model_dump()`,
`model_dump_json()`, and `model_validate(...)`, so query ASTs can be serialized
without custom ad hoc conversion code.

Important AST node types:

- `CallExpr`: regular function call, for example `get(...)`, `eq(...)`,
  `var(...)`.
- `MethodCallExpr`: chained method call, for example `.limit(100)`.
- `SubscriptExpr`: projection syntax, for example `['_key']`.
- literal nodes: `StringExpr`, `NumberExpr`, `BooleanExpr`, `NullExpr`,
  `ListExpr`, `DictExpr`.
- `BinaryOpExpr`: comparison syntax, for example `age > 48`.

The parser rejects unsupported Python syntax such as imports, lambdas,
comprehensions, assignments, arithmetic, and arbitrary statements.

## Compiler Layer

Main files:

- `opium_parser/compiler.py`
- `opium_parser/gremlin_ir.py`
- `opium_parser/gremlin_renderer.py`
- `opium_parser/errors.py`

Public APIs:

```python
from opium_parser import compile_opium_to_gremlin, compile_ast_to_gremlin

compile_opium_to_gremlin("get('users-data-product.user_roles').limit(100)")
```

Output:

```groovy
g.V().hasLabel('users-data-product.user_roles').limit(100)
```

The compiler currently returns `GremlinGroovyString`, a domain-specific
`NewType` over `str`. It does not return Gremlin Python bytecode.

## ArangoDB Provider Assumptions

The compiler assumes ArangoDB TinkerPop Provider is configured with:

```yaml
graph:
  type: COMPLEX
```

In this mode, the provider exposes ArangoDB collection names as Gremlin labels.
So:

```python
get('users-data-product.user_roles')
```

compiles to:

```groovy
g.V().hasLabel('users-data-product.user_roles')
```

and edge collections compile as edge labels:

```python
traverse_out('users-data-product.user_role_subscriptions')
```

compiles to:

```groovy
.outE('users-data-product.user_role_subscriptions')
```

## `_key` Handling

An important e2e discovery: Arango `_key` is not exposed as a normal Gremlin
property by the tested provider setup.

The provider exposes element ids as:

```text
collection/key
```

For example:

```text
users-data-product.user_roles/admin
```

Therefore the compiler treats Opium `_key` specially:

```python
get('users-data-product.user_roles', _key='admin')
```

compiles to:

```groovy
g.V()
 .hasLabel('users-data-product.user_roles')
 .hasId(TextP.endingWith('/admin'))
```

Projection:

```python
get('users-data-product.user_roles')['_key']
```

compiles to an `id()` transformation that strips the collection prefix:

```groovy
g.V()
 .hasLabel('users-data-product.user_roles')
 .id()
 .map{it.get().substring(it.get().lastIndexOf('/') + 1)}
```

This uses a Gremlin Groovy closure. That works in the current e2e lab, but it is
a portability concern if the target server disables script lambdas/closures.

## Error Model

Parser errors:

- `UnsupportedOpiumSyntaxError`
- `InvalidOpiumExpressionError`

Compiler errors:

- `UnsupportedOpiumCompilationError`
- `InvalidOpiumSemanticError`

Use parser errors for invalid syntax and compiler errors for valid syntax with
unsupported or invalid semantics.

## Related Documents

- `docs/DEVELOPER_GUIDE.md`: setup, development workflow, and extension process
- `docs/COMPILER_WALKTHROUGH.md`: detailed compiler behavior
- `docs/IMPLEMENTATION_DECISIONS.md`: why key tradeoffs were made
- `docs/E2E_GRAPH_REFERENCE.md`: synthetic graph shape used in live tests
- `docs/REVIEW_CHECKLIST.md`: code review checklist
