# Review Checklist

Use this checklist during code review or design review.

## Language Semantics

- Is this behavior documented in `OPIUM_SEMANTICS.md`?
- If the behavior is still unclear, is it listed in
  `QUESTIONS_FOR_COMPILER_COMPLETION.md`?
- Does the feature preserve the difference between parsing and compilation?
- Does the AST describe syntax without embedding Gremlin assumptions?
- Does the compiler reject unsupported semantics explicitly?

## Parser Review

- Does the grammar remain Opium-specific instead of becoming arbitrary Python?
- Are new call/method names added to `ALLOWED_CALL_NAMES`?
- Are duplicate keyword arguments rejected?
- Are positional arguments after keyword arguments rejected?
- Are new syntax forms represented by typed AST nodes?
- Do parser tests assert AST shape?
- Are unsupported syntax tests present?

## Compiler Review

- Does each new compiler branch have an exact string unit test?
- Does the generated Gremlin preserve the current traverser type?
- After each step, is the traverser a vertex, edge, map, scalar, or list?
- Are `_key`, `_id`, `_from`, and `_to` handled intentionally?
- Does missing property behavior preserve output rows when projecting?
- Does `match_any` compile as OR and `match`/`match_all` as AND?
- Do child traversals use `__` rather than restarting from `g`?
- Are provider-specific workarounds documented near the code?
- Does the compiler raise a custom error instead of guessing?

## Gremlin / Arango Review

- Are resource names treated consistently as Arango collection names?
- Are collection names exposed as labels in the target provider?
- Are vertex and edge collection labels both verified?
- Are edge directions consistent with `_from` and `_to`?
- Does deep traversal return intermediate depths as required?
- Does traversal without `into()` return edges?
- Does traversal with `into()` return vertices?
- Do unprojected terminal vertices and edges materialize as plain maps?
- Are null and missing fields tested against the live provider?

## E2E Review

- Does the e2e graph include more than one vertex collection?
- Does the e2e graph include more than one edge collection?
- Are same-label and cross-label edges tested?
- Are inbound, outbound, and any-direction traversals tested?
- Are multi-hop traversals tested?
- Are edge projections tested before `into()`?
- Are complex filters tested with aggregation?
- Are variable and subquery match operands tested live?
- Are skipped e2e tests justified by real unresolved work?

## Documentation Review

- Does README point to the deeper docs?
- Does `COMPILER_COVERAGE.md` match the current tests?
- Does `E2E_LAB.md` match the current seed graph?
- Does `IMPLEMENTATION_DECISIONS.md` explain provider-specific choices?
- Does `MIGRATION_GUIDE.md` explain how to validate assumptions in another
  environment?
- Are stale limitations removed when features become implemented?

## Current Known Gaps

The current major gaps are:

- complex `assign(...)`
- complex `array(...)`
- eventual Gremlin Python bytecode output
- performance validation on real production-scale data

If a change claims to close one of these gaps, it should include:

- semantics documentation
- compiler tests
- e2e tests if backend behavior changes
- updated skipped-test list
