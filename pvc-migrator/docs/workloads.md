# Workload Guides

## Generic StatefulSets

The tool derives PVC names from `volumeClaimTemplates` and pod ordinals, then generates `pv-migrate` commands.

## VictoriaMetrics

### `vmstorage`

The planner treats `vmstorage` as a native-migration workload and emits `vmbackupmanager`-based steps.

This path is covered by live e2e detection tests against real `vmstorage` StatefulSets. The current automated live validation covers planner selection and command generation, not a full backup/restore execution lab.

### `vmagent` and `vmalert`

These are usually better redeployed than PVC-migrated. The planner warns and skips them by default unless PVC copying is explicitly enabled.

## ArangoDB

The planner assumes single-server ArangoDB in v1 and generates native dump/restore commands.

This path is covered by a live kind-based e2e test using real `arangodb` containers and an actual dump/restore round-trip between source and destination workloads.

## Grafana plugins

If plugins are declared in Helm values, the planner recommends redeploying Grafana with those plugin declarations instead of copying files from disk.
