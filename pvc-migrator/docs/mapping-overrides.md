# Mapping Overrides

Use a mapping file when rendered workload names do not line up cleanly between source and destination.

## Example

```yaml
workloads:
  - source_workload: source-db
    destination_workload: target-db
pvcs:
  - source_pvc: data-source-db-0
    destination_pvc: data-target-db-0
```

Pass it with:

```powershell
--mapping-file .\mapping.yaml
```

## When to use it

- Release names changed significantly.
- Two destination workloads would otherwise look equivalent.
- PVC names differ beyond normal StatefulSet ordinal naming.
