# pvc-migrator

`pvc-migrator` plans and optionally executes Kubernetes PVC migrations across namespaces and clusters.

It is workload-aware:

- generic StatefulSet and standalone PVC migration via `pv-migrate`
- VictoriaMetrics `vmstorage` migration via `vmbackupmanager` planning
- VictoriaMetrics `vmagent` and `vmalert` detection with skip/redeploy guidance
- ArangoDB single-server detection with native migration guidance
- Grafana plugin migration detection with declarative-first guidance

## Status

This project is structured as a production-oriented planner with guarded execution:

- renders source and destination Helm charts
- derives PVC mappings from rendered StatefulSets plus live PVC discovery
- selects a migration engine per workload
- emits a plan in table, JSON, or YAML form
- supports guarded `execute` for command-based engines
- persists resumable run logs under `.pvc-migrator-runs/`
- supports explicit workload and PVC mapping overrides
- performs binary and RBAC preflight checks

Full docs are under [`docs/`](C:/Users/Ron/Documents/repos/tools/pvc-migrator/docs) and can be served with MkDocs.

## Usage

```powershell
pvc-migrator plan `
  --source-chart .\charts\app `
  --source-values .\values-source.yaml `
  --dest-chart .\charts\app `
  --dest-values .\values-dest.yaml `
  --source-namespace source `
  --dest-namespace dest `
  --source-context src-cluster `
  --dest-context dst-cluster
```

Optional extras:

```powershell
--extra-pvc-selector app=my-extra-pvc
--output json
--include-workload vmstorage
--allow-aux-pvc-copy
--mapping-file .\mapping.yaml
```

Execute a validated plan:

```powershell
pvc-migrator execute ...same flags... --approve
```

## External dependencies

The CLI expects these tools on the operator machine:

- `helm`
- `kubectl`
- `pv-migrate` for generic PVC copy

Workload-native commands are only required when their engine is selected.

## Development

Run tests:

```powershell
pytest
pytest -m integration
pytest -m e2e
mypy src
mkdocs build --strict
```
