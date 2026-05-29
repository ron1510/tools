# Learning Roadmap

This roadmap is for becoming comfortable enough to review and direct this
project with confidence. It is ordered from "understand the parser" to
"understand whether generated Gremlin is correct for ArangoDB".

## 1. Language Parsing Basics

Learn these ideas first:

- tokenization / lexing
- grammar rules
- parse trees
- abstract syntax trees
- transformers / visitors
- syntax errors vs semantic errors

Why it matters here:

- `grammar.lark` defines what Opium text is allowed.
- `transformer.py` turns Lark parse trees into typed Python objects.
- `ast_nodes.py` defines the AST shape used by later compiler code.

Read:

- Lark documentation: grammar reference
- Lark documentation: transformers and visitors
- A short intro to context-free grammars

Repo files to study:

- `opium_parser/grammar.lark`
- `opium_parser/transformer.py`
- `opium_parser/ast_nodes.py`
- `tests/parser`

Key question to answer after reading:

Can I explain why `get('x').limit(10)['_key']` becomes nested AST nodes instead
of being executed like Python?

## 2. Typed AST Design

Learn these ideas:

- concrete syntax vs abstract syntax
- immutable syntax trees
- expression nodes
- call expressions vs method-call expressions
- preserving user intent without compiling too early

Why it matters here:

- `CallExpr`, `MethodCallExpr`, `SubscriptExpr`, and friends are the stable
  language representation.
- The AST should not contain Gremlin assumptions.

Read:

- Articles about ASTs in compilers/interpreters
- Python `dataclasses` documentation
- Python typing basics, especially unions and literals

Repo files to study:

- `opium_parser/ast_nodes.py`
- `docs/IMPLEMENTATION_DECISIONS.md`

Key question:

Can I tell whether a behavior belongs in the parser, the AST, or the compiler?

## 3. Lark Specifically

Learn these Lark concepts:

- terminals vs rules
- aliases with `->`
- ignored whitespace/comments
- left-to-right chains
- LALR parsing
- transformer method names
- `VisitError`

Why it matters here:

- The parser is deliberately Opium-only, not Python.
- The grammar recognizes syntax, but the transformer validates supported Opium
  function names and duplicate keyword arguments.

Read:

- Lark "How To Use" guide
- Lark grammar reference
- Lark examples for calculators or small languages

Repo files to study:

- `opium_parser/grammar.lark`
- `opium_parser/parser.py`
- `opium_parser/transformer.py`
- `tests/parser/test_parser_invalid.py`

Exercise:

Add a new harmless syntax form to the grammar in a branch, write one parser test,
then remove it. The point is to understand the workflow without committing to a
real feature.

## 4. Compiler Architecture

Learn these ideas:

- source language vs target language
- semantic validation
- intermediate representation
- code generation
- unsupported syntax vs unsupported compilation
- unit tests for generated output

Why it matters here:

- `compile_opium_to_gremlin(...)` is not part of parsing.
- The compiler converts known AST shapes into Gremlin Groovy strings.
- Some ASTs are valid Opium syntax but not compiled yet.

Read:

- Introductory compiler architecture material
- Articles on building small DSL compilers
- Python exception design for library APIs

Repo files to study:

- `opium_parser/compiler.py`
- `opium_parser/gremlin_ir.py`
- `opium_parser/gremlin_renderer.py`
- `tests/compiler`

Key question:

Can I point to the exact code that decides `get('roles')` means
`g.V().hasLabel('roles')`?

## 5. Gremlin And Apache TinkerPop

Learn these Gremlin concepts:

- graph traversal source: `g`
- vertices and edges
- labels
- properties
- ids
- `V()`, `E()`
- `hasLabel`, `has`, `hasId`
- `outE`, `inE`, `bothE`
- `otherV`, `outV`, `inV`
- `project`, `by`, `values`, `coalesce`, `constant`
- `repeat`, `emit`, `times`, `loops`
- anonymous traversals with `__`
- predicates: `P.gt`, `P.within`, `TextP.regex`

Why it matters here:

- Every compiler decision eventually becomes one or more Gremlin steps.
- Misunderstanding edge direction or labels will produce valid Gremlin that
  returns wrong data.

Read:

- Apache TinkerPop reference documentation
- TinkerPop "The Gremlin Console" tutorial
- TinkerPop traversal step reference
- TinkerPop predicate documentation

Repo files to study:

- `opium_parser/compiler.py`
- `tests/compiler/test_compiler_traversal.py`
- `tests/e2e/test_gremlin_arangodb.py`

Practice queries:

```groovy
g.V().label().dedup()
g.E().label().dedup()
g.V().hasLabel('users-data-product.user_roles').count()
g.V().hasLabel('users-data-product.user_roles').outE().otherV()
g.E().project('_id','_from','_to').by(id()).by(outV().id()).by(inV().id())
```

Key question:

Can I predict whether a traversal is currently on vertices, edges, maps, or
lists after each step?

## 6. ArangoDB Graph Model

Learn these ArangoDB concepts:

- databases
- document collections
- edge collections
- `_key`
- `_id`
- `_from`
- `_to`
- named graphs
- edge definitions
- collection-level key uniqueness
- full document id uniqueness

Why it matters here:

- Opium resource names are Arango collection names.
- `_key` is unique per collection.
- `_id` is globally unique as `collection/key`.
- Edges are documents in edge collections and must have `_from` / `_to`.

Read:

- ArangoDB documents documentation
- ArangoDB graph documentation
- ArangoDB edge collection documentation
- ArangoDB `_key`, `_id`, `_from`, `_to` field documentation

Repo files to study:

- `scripts/seed_opium_e2e.js`
- `docs/OPIUM_SEMANTICS.md`
- `docs/E2E_LAB.md`

Key question:

Can I explain the difference between `_key`, `_id`, `_from`, and `_to` without
mentioning Gremlin?

## 7. ArangoDB TinkerPop Provider

Learn these provider-specific ideas:

- TinkerPop provider
- ArangoDB provider `COMPLEX` mode
- how Arango collections appear as Gremlin labels
- how Arango ids appear in Gremlin
- which properties are exposed normally and which need reconstruction

Why it matters here:

- The compiler assumes COMPLEX mode.
- `hasLabel(collection_name)` works only because the provider exposes
  collections as labels.
- `_from` and `_to` are reconstructed through adjacent vertices in current code.

Read:

- The ArangoDB TinkerPop Provider documentation from the provider repository
- The local Helm chart/config in the sibling lab repository
- Rendered Gremlin Server configuration from the chart

Repo files to study:

- `e2e/gremlin-opium-values.yaml`
- `docs/E2E_LAB.md`
- `docs/IMPLEMENTATION_DECISIONS.md`
- `tests/e2e/test_gremlin_arangodb.py`

Key question:

Can I prove from a live query that collection names are labels in this setup?

## 8. Testing Strategy

Learn these testing ideas:

- unit tests
- integration tests
- e2e tests
- fixtures
- skipped tests as explicit known gaps
- testing generated code by exact string comparison
- testing behavior against a real backend

Why it matters here:

- Parser tests prove AST shape.
- Compiler tests prove generated Gremlin text.
- E2E tests prove generated Gremlin works against ArangoDB via the provider.

Read:

- pytest documentation: fixtures, markers, skips
- pytest documentation: assertion introspection
- Basic testing pyramid material

Repo files to study:

- `docs/TESTING_STRATEGY.md`
- `tests/parser`
- `tests/compiler`
- `tests/e2e`
- `tests/fixtures/e2e_graph.py`

Key question:

If a query returns wrong results, can I decide whether to add a parser test,
compiler test, e2e test, or all three?

## 9. Current Project Semantics

Read these project docs carefully:

- `docs/OPIUM_SEMANTICS.md`
- `docs/IMPLEMENTATION_DECISIONS.md`
- `docs/COMPILER_COVERAGE.md`
- `docs/QUESTIONS_FOR_COMPILER_COMPLETION.md`
- `docs/E2E_LAB.md`
- `docs/TESTING_STRATEGY.md`

Recommended order:

1. `OPIUM_SEMANTICS.md`
2. `IMPLEMENTATION_DECISIONS.md`
3. `COMPILER_COVERAGE.md`
4. `TESTING_STRATEGY.md`
5. `E2E_LAB.md`
6. `QUESTIONS_FOR_COMPILER_COMPLETION.md`

Key question:

Can I separate what is already decided from what is still intentionally open?

## 10. Practical Review Checklist

When reviewing this project, ask:

1. Is this syntax documented Opium or accidental Python?
2. Does the AST preserve the syntax without embedding Gremlin assumptions?
3. Does the compiler decision belong to Opium semantics or provider behavior?
4. Is the generated Gremlin on vertices, edges, maps, or lists at this point?
5. Does the test prove parsing, string generation, or live backend behavior?
6. Is a skipped test marking a real unresolved decision?
7. Would this behavior still work if we moved from Groovy strings to bytecode?

## 11. Minimum Expert Path

If you want the fastest path, do this:

1. Read `grammar.lark` and all files in `tests/parser`.
2. Read `ast_nodes.py`.
3. Read `compiler.py` alongside `tests/compiler`.
4. Run manual Gremlin queries from `docs/E2E_LAB.md`.
5. Read `scripts/seed_opium_e2e.js` and draw the graph on paper.
6. Read `tests/e2e/test_gremlin_arangodb.py` and predict each result before
   running it.
7. Read `IMPLEMENTATION_DECISIONS.md` and mark every decision you agree or
   disagree with.

At that point, your feedback will be precise enough to drive the next compiler
stage.
