# Execution Safety

`pvc-migrator` is intentionally conservative.

## Safety controls

- `execute` requires `--approve`
- plans with blockers cannot execute
- preflight runs before plan construction is finalized
- run logs are written under `.pvc-migrator-runs/`
- `--resume-run-id` skips commands already marked completed
- `--workload` scopes execution to named workloads

## Recommended operator flow

1. Run `plan` in `table` or `json` mode.
2. Review preflight checks and blockers.
3. Fix missing PVCs, RBAC, or mapping issues.
4. Execute only the intended workloads.
5. Resume with the prior run id if interrupted.
