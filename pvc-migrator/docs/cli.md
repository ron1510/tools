# CLI Reference

## Commands

### `pvc-migrator plan`

Builds a migration plan and prints it.

### `pvc-migrator execute`

Builds the plan and executes it only when the plan is executable.

## Common flags

- `--source-chart`
- `--source-values`
- `--source-release`
- `--dest-chart`
- `--dest-values`
- `--dest-release`
- `--source-namespace`
- `--dest-namespace`
- `--source-context`
- `--dest-context`
- `--extra-pvc-selector`
- `--include-workload`
- `--exclude-workload`
- `--engine`
- `--allow-aux-pvc-copy`
- `--mapping-file`
- `--output`
- `--output-file`
- `--workload`
- `--resume-run-id`
- `--approve`

## Exit behavior

- `0` on success
- `1` on planner or execution error

## Examples

Plan with an override file:

```powershell
pvc-migrator plan `
  --source-chart .\chart `
  --dest-chart .\chart `
  --source-namespace source `
  --dest-namespace dest `
  --mapping-file .\mapping.yaml
```

Execute a single workload and require explicit approval:

```powershell
pvc-migrator execute `
  --source-chart .\chart `
  --dest-chart .\chart `
  --source-namespace source `
  --dest-namespace dest `
  --workload app-db `
  --approve
```
