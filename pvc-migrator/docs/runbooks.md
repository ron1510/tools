# Operations Runbooks

## Generic StatefulSet migration

1. Deploy the destination chart so controller-created PVCs exist.
2. Run `pvc-migrator plan`.
3. Review `pv-migrate` commands and warnings.
4. Execute with `--approve`.
5. Validate the destination workload before cutover.

## VictoriaMetrics `vmstorage`

1. Ensure source and destination topology are compatible.
2. Run `plan` and inspect generated `vmbackupmanager` steps.
3. Prepare backup storage and restore marks.
4. Restart destination storage pods only after restore marks are in place.

## ArangoDB single-server

1. Review generated `arangodump` / `arangorestore` commands.
2. Validate source and destination versions.
3. Perform restore into the destination instance.
4. Run application-level validation after restore.

## Grafana plugins

1. Prefer redeploy from declared `plugins:` values.
2. Only use plugin-directory PVC copy when disk state is the source of truth.
3. Validate plugin compatibility against the destination Grafana version.
