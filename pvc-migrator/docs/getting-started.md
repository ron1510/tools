# Getting Started

## Prerequisites

- Python 3.11+
- `helm`
- `kubectl`
- `pv-migrate` for generic PVC execution

Optional:

- `kind` for local smoke tests
- MkDocs for serving docs locally

## Install for development

```powershell
pip install -e .[dev]
```

## First plan

```powershell
pvc-migrator plan `
  --source-chart .\chart `
  --source-values .\values-source.yaml `
  --dest-chart .\chart `
  --dest-values .\values-dest.yaml `
  --source-namespace source `
  --dest-namespace dest `
  --source-context src-cluster `
  --dest-context dst-cluster
```

## Output formats

- `table`
- `json`
- `yaml`
