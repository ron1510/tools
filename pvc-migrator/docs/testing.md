# Testing

## Test layers

### Unit tests

Cover:

- model validation
- workload classification
- PVC mapping
- engine selection
- plan formatting
- CLI behavior

### Integration tests

Cover:

- real `helm template` rendering against a fixture chart

### E2E smoke tests

Cover:

- end-to-end planning against a real Kubernetes context using fixture namespaces and PVCs
- resumable setup against a disposable `kind` cluster
- real ArangoDB single-server dump/restore execution between live source and destination workloads
- real VictoriaMetrics workload detection against live `vmstorage`, `vmagent`, and `vmalert` pods

## Commands

```powershell
pytest
pytest -m integration
pytest -m e2e
```

The e2e smoke test runs when `kind`, `helm`, and `kubectl` are available and a current cluster context exists.
