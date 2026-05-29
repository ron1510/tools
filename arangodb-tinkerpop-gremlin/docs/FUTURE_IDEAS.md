# Future Ideas

This POC proves that Gremlin Server can sit in front of ArangoDB and run read-only traversals through the ArangoDB TinkerPop provider. If the team wants to take it further, these are the highest-value next steps.

## 1. Query Evaluation Track

- Translate 5-10 representative existing custom-QL queries into direct Gremlin traversals.
- Compare result correctness against the current AQL path.
- Record where Gremlin is clearer, where it is more awkward, and where native AQL still wins.
- Identify which traversals are naturally graph-shaped versus which are really document or aggregation queries.

## 2. API Shape Track

- Do not expose arbitrary Gremlin strings as a public API.
- Keep Gremlin Server internal.
- Build a thin service layer that exposes approved operations only.
- Model traversals as typed helper functions or a small SDK, not as free-form remote scripts.

## 3. Performance Track

- Benchmark representative traversals against the current AQL implementation.
- Measure latency, payload size, and server-side resource usage.
- Evaluate whether traversal shape changes can improve performance before concluding Gremlin is slower.
- Maintain native AQL as the escape hatch for performance-critical or non-graph-native workloads.

## 4. Operational Hardening Track

- Move chart credentials to existing secrets rather than generated lab defaults.
- Add TLS and auth posture appropriate for the target environment.
- Replace the single local ArangoDB chart with the actual target topology.
- Add readiness checks that verify graph/provider initialization more explicitly.
- Add CI checks for image build, Helm lint, and Python script syntax.

## 5. Developer Experience Track

- Add a small interactive REPL helper around `gremlin-python`.
- Add a curated query runner UI if non-Python users need easier exploration.
- Add example traversals for common team use cases such as dependency exploration, neighborhood lookup, ownership traversal, and blast-radius queries.
- Add a short "Gremlin for AQL users" guide with examples of equivalent patterns.

## 6. Decision Criteria

Use this POC to answer these questions clearly:

- Does Gremlin make common graph traversals easier to express than the current custom language?
- Does it remove enough custom compiler/translator maintenance burden?
- Can the team keep the public API disciplined without exposing raw Gremlin?
- Which query classes should remain native AQL even if Gremlin is adopted?

If those answers are mostly positive, the next implementation step should be a thin internal query service built on typed Gremlin traversal helpers, not a new text-based query language.
