# Architecture

## Modules

- `rendering.py`: Helm rendering and values summary loading
- `discovery.py`: rendered workload discovery and live PVC inspection
- `mapping.py`: workload and PVC mapping
- `engines.py`: engine selection and command generation
- `service.py`: end-to-end planning and guarded execution
- `formatting.py`: table/JSON/YAML output rendering
- `cli.py`: user-facing command-line interface

## Data flow

1. Render both charts.
2. Load values summaries.
3. Discover workloads from rendered resources.
4. Inspect live PVCs in source and destination namespaces.
5. Pair source and destination workloads.
6. Generate workload-specific execution steps.
7. Render or execute the resulting plan.
