# pvc-migrator

`pvc-migrator` is a workload-aware tool for planning and executing Kubernetes PVC migrations across namespaces and clusters.

It is designed for operators who are not cluster-admins and need a safer path than raw manual PVC copying.

## What it does

- Renders source and destination Helm charts.
- Detects StatefulSets, Deployments, VM workloads, and declared Grafana plugins.
- Discovers live PVCs in source and destination namespaces.
- Maps source PVCs to destination PVCs.
- Selects a migration engine per workload.
- Emits a human-readable or machine-readable migration plan.

## Engine policy

- Generic workloads: `pv-migrate`
- VictoriaMetrics `vmstorage`: `vmbackupmanager` plan
- VictoriaMetrics `vmagent` / `vmalert`: redeploy/skip by default
- ArangoDB single-server: native dump/restore plan
- Grafana plugins: declarative plugin rehydrate when possible
