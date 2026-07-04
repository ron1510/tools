# Migration Guide

This guide covers moving this repository into an organization environment.

## What To Copy

Minimum package files:

```text
opium_parser/
pyproject.toml
README.md
```

Recommended full project copy:

```text
opium_parser/
tests/
docs/
scripts/
e2e/
pyproject.toml
README.md
```

For serious review, copy the full project. The tests and docs are part of the
design, not extras.

## Python Packaging

The package is configured with Hatchling in `pyproject.toml`.

Install editable in a local checkout:

```powershell
python -m pip install -e .
```

Install with development tools:

```powershell
python -m pip install -e ".[dev]"
```

Install with e2e dependencies:

```powershell
python -m pip install -e ".[dev,e2e]"
```

The only runtime dependency is:

```text
lark>=1.1.9
```

The e2e-only dependency is:

```text
gremlinpython==3.8.1
```

## Import Check

After installing:

```powershell
python -c "from opium_parser import parse_opium, compile_opium_to_gremlin; print(parse_opium); print(compile_opium_to_gremlin)"
```

## Organization Environment Checklist

Before using the compiler against an org backend, verify:

1. ArangoDB TinkerPop Provider is actually used.
2. Provider graph mode is `COMPLEX`.
3. Collection names are exposed as Gremlin labels.
4. Gremlin element ids are returned as `collection/key`.
5. The provider edge string includes source and target endpoint ids.
6. Gremlin Server allows the Groovy closures used for `_key`, `_from`, `_to`,
   and dangling-safe `into(...)`.
7. `TextP.regex(...)` is available.
8. `P.gte(90.0d)`-style Java double literals work.
9. `has(field, null)` behaves as expected for explicit null properties.

If any of these are false, the compiler may need a provider compatibility layer.

## Running Without The E2E Lab

You can run parser and compiler tests without any backend:

```powershell
python -m pytest tests\parser tests\compiler -q
```

These tests prove syntax and generated Gremlin strings. They do not prove that
the org Gremlin Server accepts the generated strings.

## Running Against An Org-Like Lab

The current lab assumes:

```text
namespace: gremlin-lab
Arango pod: arangodb-lab-0
Gremlin service: gremlin-arangodb-poc
database: my_db
graph: my_graph
```

If your org environment uses different names, update:

- `docs/E2E_LAB.md`
- `e2e/gremlin-opium-values.yaml`
- the shell commands you run

Do not change compiler code just to match a local lab name. Compiler code should
depend on Opium resource names and provider behavior, not Kubernetes names.

## Validating Provider Assumptions Manually

After port-forwarding Gremlin Server:

```powershell
python scripts\gremlin_submit.py "g.V().label().dedup()"
python scripts\gremlin_submit.py "g.E().label().dedup()"
python scripts\gremlin_submit.py "g.V().limit(3).id()"
python scripts\gremlin_submit.py "g.E().limit(3).map{it.get().toString()}"
```

Expected:

- vertex labels are Arango vertex collection names
- edge labels are Arango edge collection names
- ids look like `collection/key`
- edge string values include full source and target Arango ids

## How To Bring In Org-Specific Data

Preferred approach:

1. Keep the synthetic e2e graph.
2. Add a second org-fixture seed script or fixture layer.
3. Add separate e2e tests for org-specific behavior.

Avoid replacing the current synthetic graph entirely. It is carefully shaped to
exercise compiler assumptions in a deterministic way.

## Security Note

The library does not execute user-provided Opium input. It parses and compiles.

However, generated Gremlin Groovy strings are later executable by Gremlin
Server. Treat them as generated code. If this becomes user-facing, add a review
step before exposing arbitrary Opium input to production execution.

## Versioning Recommendation

Before merging into an org repo, tag or record:

- current parser supported syntax
- current compiler supported semantics
- current e2e graph size
- current skipped tests and why

The current repo intentionally separates "parsed", "compiled", and "e2e
proven". Keep that distinction in release notes.
