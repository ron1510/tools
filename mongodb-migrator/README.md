# mongodb-migrator

`mongodb-migrator` is a production-oriented MongoDB copy and migration CLI for moving application data between clusters, `mongos` routers, and databases.

It supports two operator workflows:

- `copy`: clone one database environment into another with safe defaults
- `run`: execute an advanced YAML-defined migration job

## What It Optimizes For

- cross-cluster copies through standard MongoDB URIs
- safe target handling with explicit destructive opt-in
- collection metadata recreation
- resumable batched execution
- post-run verification
- Python package structure that is easy to extend and test

## Default Copy Behavior

The `copy` command is intended for the common case: copy an environment for testing.

By default it copies:

- documents
- collection indexes
- collection validators
- collection options where safe to recreate

It does not copy:

- users or roles
- cluster/server settings
- sharding topology administration

If the target already contains data, the command fails unless `--replace-target` is set.

## Usage

Simple environment copy:

```powershell
mongodb-migrator copy `
  --source-uri "mongodb://source-router:27017" `
  --source-database app_source `
  --target-uri "mongodb://target-router:27017" `
  --target-database app_test `
  --verify
```

Replace existing target collections explicitly:

```powershell
mongodb-migrator copy `
  --source-uri "mongodb://source-router:27017" `
  --source-database app_source `
  --target-uri "mongodb://target-router:27017" `
  --target-database app_test `
  --replace-target
```

Advanced migration from YAML:

```powershell
mongodb-migrator run --config .\migration-job.yaml
```

Inspect a plan without writing:

```powershell
mongodb-migrator inspect --config .\migration-job.yaml
```

## YAML Job Example

```yaml
source:
  uri: mongodb://source-router:27017
  database: app_source
target:
  uri: mongodb://target-router:27017
  database: app_target
selection:
  include_collections:
    - users
    - orders
execution:
  batch_size: 1000
  checkpoint_path: .state/mongo-migration.json
verification:
  enabled: true
  sample_size: 25
```

## Installation

Base install:

```powershell
pip install -e .
```

With development tools:

```powershell
pip install -e .[dev]
```

`pymongo` is installed as a normal runtime dependency because the CLI requires it.

## Testing

Fast test suite:

```powershell
pytest
python -m mypy src tests
```

Real MongoDB integration and e2e tests:

```powershell
$env:MONGODB_MIGRATOR_RUN_REAL_TESTS="1"
pytest
```

The real-runtime suite uses Docker Compose to start two MongoDB instances, then exercises:

- direct service-layer copy against real MongoDB
- real CLI execution through `python -m mongodb_migrator`
