# review-env-exporter

`review-env-exporter` generates deterministic `.env` files from Kubernetes or OpenShift resource metadata.

This project is intentionally focused on the pure core of a review-environment endpoint exporter:

- fetch Kubernetes-style resources
- select the resources explicitly marked for export
- validate the metadata contract
- derive runtime values from resource fields
- render a stable `.env` file

It currently supports:

- OpenShift `Route` -> URL export
- Kubernetes `Service` of type `NodePort` -> `host:port` export

It does not try to manage deployment, CI/CD, shared file publishing, or application lifecycle. Those concerns belong in the consuming codebase.

## What It Does

The tool reads Kubernetes/OpenShift resources and looks for a label that marks them as exportable:

```yaml
review.my-company.io/export-env: "true"
```

Exportable resources must also define annotations that describe the output variable name and export strategy:

```yaml
review.my-company.io/env-name: API_URL
review.my-company.io/export-type: route-url
```

The result is a deterministic `.env` file sorted by env var name, with source comments for traceability.

Example output:

```env
# Generated review environment file
# Do not edit manually; regenerate from cluster resource metadata.

# from Route/api
API_URL=https://acme-feature-x.apps.cluster.example.com/api

# from Service/kafka-external
KAFKA_BOOTSTRAP_SERVERS=nodeport-gw.review.example.com:32110
```

## Metadata Contract

### Selection label

Only resources with this label are considered exportable:

```yaml
review.my-company.io/export-env: "true"
```

Resources without this label are ignored.

### Required annotations

Every exportable resource must define:

```yaml
review.my-company.io/env-name: API_URL
review.my-company.io/export-type: route-url
```

If an exportable resource is malformed, the tool does not silently skip it. It raises explicit contract errors, and when multiple resources are invalid, those errors are aggregated and reported together.

## Supported Export Types

### `route-url`

Expected resource kind:

```yaml
kind: Route
```

Value derivation rules:

- reads `spec.host`
- uses `https` if `spec.tls` exists
- otherwise uses `http`
- `review.my-company.io/scheme` overrides the inferred scheme
- path resolution order:
  - `review.my-company.io/path`
  - `spec.path`
  - no path

Example:

```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: api
  labels:
    review.my-company.io/export-env: "true"
  annotations:
    review.my-company.io/env-name: API_URL
    review.my-company.io/export-type: route-url
    review.my-company.io/path: /api
spec:
  host: api.review.example.com
  tls:
    termination: edge
```

Output:

```env
API_URL=https://api.review.example.com/api
```

### `nodeport-hostport`

Expected resource kind:

```yaml
kind: Service
```

Required service shape:

- `spec.type == "NodePort"`
- annotation `review.my-company.io/public-host`

Port resolution rules:

- reads `spec.ports[].nodePort`
- if there is exactly one `nodePort`, it is used
- if there are multiple `nodePort` values, `review.my-company.io/port-name` is required
- when `port-name` is set, the matching port is selected by `spec.ports[].name`

Example:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: kafka-external
  labels:
    review.my-company.io/export-env: "true"
  annotations:
    review.my-company.io/env-name: KAFKA_BOOTSTRAP_SERVERS
    review.my-company.io/export-type: nodeport-hostport
    review.my-company.io/public-host: nodeport-gw.review.example.com
spec:
  type: NodePort
  ports:
    - name: tcp-kafka
      port: 9092
      targetPort: 9092
      nodePort: 32110
```

Output:

```env
KAFKA_BOOTSTRAP_SERVERS=nodeport-gw.review.example.com:32110
```

## Architecture

The code is split into a few small layers with explicit responsibilities.

### 1. Models

Implemented in [models.py](C:/Users/Ron/Documents/repos/k8s-dotenv-builder/src/review_env_exporter/models.py).

This layer defines:

- normalized resource models
- metadata and spec models
- selection and cluster access configuration
- parsing from raw resource dictionaries into validated internal models

The important point is that everything past this layer works with a consistent internal representation, regardless of where the data originally came from.

### 2. Provider layer

Implemented in [providers](C:/Users/Ron/Documents/repos/k8s-dotenv-builder/src/review_env_exporter/providers).

Providers fetch raw resources and normalize them into validated internal models.

Current providers:

- `StaticResourceProvider`
  - for tests and in-memory use
- `KubernetesApiResourceProvider`
  - for real cluster access through the Kubernetes Python client

This is the main abstraction boundary in the project.

Because the exporter only consumes normalized models, the export logic does not care whether resources came from:

- real Kubernetes API calls
- OpenShift route API calls
- fixtures
- tests
- another adapter added later

### 3. Exporter core

Implemented in [exporter.py](C:/Users/Ron/Documents/repos/k8s-dotenv-builder/src/review_env_exporter/exporter.py).

This layer is pure.

It is responsible for:

- filtering exportable resources
- validating export annotations
- dispatching by export type
- detecting duplicate env var names
- rendering deterministic dotenv output

Key public functions:

- `generate_env(resources) -> str`
- `collect_env_entries(resources) -> list[EnvEntry]`
- `render_dotenv(entries) -> str`
- `export_route_url(resource) -> str`
- `export_nodeport_hostport(resource) -> str`

### 4. Service layer

Implemented in [service.py](C:/Users/Ron/Documents/repos/k8s-dotenv-builder/src/review_env_exporter/service.py).

The service coordinates:

- resource fetching
- basic operational logging
- env generation

It does not own export rules. It just orchestrates provider -> exporter.

### 5. CLI

Implemented in [cli.py](C:/Users/Ron/Documents/repos/k8s-dotenv-builder/src/review_env_exporter/cli.py).

The CLI turns command-line arguments into:

- `ClusterAccessConfig`
- `ResourceSelectionConfig`
- a `KubernetesApiResourceProvider`
- a `ReviewEnvExporterService`

Then it writes the result to either:

- `stdout`
- or a file path passed through `--output`

## Data Flow

At runtime, the flow is:

1. CLI or calling code creates a provider and configuration.
2. The provider fetches resources from the source system.
3. Raw resources are normalized into internal Pydantic models.
4. Exportable resources are selected by label.
5. Export type handlers derive env values from resource fields.
6. Entries are sorted by env var name.
7. The final `.env` text is rendered.

That is the key design decision in the project: fetch and normalization are separate from export rules.

## Validation and Error Handling

The tool is intentionally strict for exportable resources.

If a resource is marked with `review.my-company.io/export-env: "true"`, then malformed metadata is treated as an error, not a warning.

Explicit contract errors include:

- missing annotation
- unsupported export type
- wrong resource kind
- duplicate env var name
- multiple `NodePort` ports with no `port-name`

When more than one exportable resource is invalid, the tool raises a `ResourceContractErrorGroup` so the caller sees the full set of problems in one run.

The CLI formats those failures as readable `stderr` output and exits with status code `1`.

## Dotenv Rendering Rules

The rendered output is deterministic.

Current rendering behavior:

- entries are sorted by env var name
- every variable is preceded by a source comment
- values like URLs and `host:port` remain unquoted when safe
- values are quoted only when needed
- quotes, backslashes, and newlines are escaped when quoting

This is implemented in `render_dotenv()` and `format_dotenv_value()`.

## Installation

Base install:

```powershell
pip install -e .
```

Development install:

```powershell
pip install -e .[dev]
```

Kubernetes integration install:

```powershell
pip install -e .[kubernetes]
```

Development plus Kubernetes integration:

```powershell
pip install -e .[dev,kubernetes]
```

## CLI Usage

Basic usage:

```powershell
review-env-exporter --namespace review
```

When multiple review environments share one namespace, prefer filtering by Helm release:

```powershell
review-env-exporter --namespace review --helm-release feature-123
```

Write directly to a file:

```powershell
review-env-exporter --namespace review --output .env.review
```

Filter resources at fetch time:

```powershell
review-env-exporter --namespace review --label-selector review.my-company.io/export-env=true
```

Filter by Helm release and export label together:

```powershell
review-env-exporter --namespace review --helm-release feature-123 --label-selector review.my-company.io/export-env=true
```

This resolves to the effective Kubernetes selector:

```text
app.kubernetes.io/instance=feature-123,review.my-company.io/export-env=true
```

Restrict fetched kinds:

```powershell
review-env-exporter --namespace review --kind Route --kind Service
```

Authentication modes:

```powershell
review-env-exporter --namespace review --auth-mode auto
review-env-exporter --namespace review --auth-mode kubeconfig --kubeconfig C:\Users\Ron\.kube\config
review-env-exporter --namespace review --auth-mode kubeconfig --context my-context
review-env-exporter --namespace review --auth-mode in-cluster
```

The Helm release filter relies on the standard Helm label:

```yaml
app.kubernetes.io/instance: <release-name>
```

If your charts do not apply that label consistently, Helm release filtering will not work reliably.

Equivalent module invocation:

```powershell
python -m review_env_exporter --namespace review
```

## Python Usage

### Pure core usage

```python
from review_env_exporter import generate_env

resources = [
    {
        "kind": "Route",
        "metadata": {
            "name": "api",
            "labels": {"review.my-company.io/export-env": "true"},
            "annotations": {
                "review.my-company.io/env-name": "API_URL",
                "review.my-company.io/export-type": "route-url",
                "review.my-company.io/path": "/api",
            },
        },
        "spec": {
            "host": "acme-feature-x.apps.cluster.example.com",
            "tls": {"termination": "edge"},
        },
    }
]

print(generate_env(resources))
```

### Service-layer usage

```python
from review_env_exporter import ResourceSelectionConfig, ReviewEnvExporterService
from review_env_exporter.providers import StaticResourceProvider

provider = StaticResourceProvider(resources)
service = ReviewEnvExporterService(
    provider=provider,
    config=ResourceSelectionConfig(namespace="review"),
)

print(service.generate_env())
```

### Kubernetes provider usage

```python
from review_env_exporter import ClusterAccessConfig, ResourceSelectionConfig, ReviewEnvExporterService
from review_env_exporter.providers import KubernetesApiResourceProvider

provider = KubernetesApiResourceProvider(
    access_config=ClusterAccessConfig(auth_mode="kubeconfig"),
)
service = ReviewEnvExporterService(
    provider=provider,
    config=ResourceSelectionConfig(
        namespace="review",
        label_selector="review.my-company.io/export-env=true",
    ),
)

print(service.generate_env())
```

## Testing

Run the unit test suite:

```powershell
pytest
```

The test suite is pytest-based and covers:

- happy-path export generation
- invalid metadata contract cases
- dotenv quoting behavior
- provider behavior
- CLI behavior
- cache behavior in the Kubernetes provider

### Optional integration smoke test

There is an opt-in real-cluster smoke test in [tests/test_integration_kind_smoke.py](C:/Users/Ron/Documents/repos/k8s-dotenv-builder/tests/test_integration_kind_smoke.py).

It is skipped unless:

```powershell
$env:REVIEW_ENV_RUN_KIND_SMOKE="1"
pytest -m integration
```

## Disposable kind Smoke Environment

The repo includes a small smoke-test environment under `deploy/kind-smoke`:

- `namespace.yaml`
- `route-crd.yaml`
- `resources.yaml`

It creates:

- a test namespace
- a minimal `Route` CRD so OpenShift-style routes can exist in `kind`
- two exportable `Route` resources
- two exportable `NodePort` services
- one internal non-exported service
- a shared Helm-style instance label: `app.kubernetes.io/instance=review-env-smoke`

Typical flow:

```powershell
kind create cluster --name review-env-smoke
kubectl config use-context kind-review-env-smoke
kubectl apply -f deploy/kind-smoke/namespace.yaml
kubectl apply -f deploy/kind-smoke/route-crd.yaml
kubectl apply -f deploy/kind-smoke/resources.yaml
review-env-exporter --namespace review-smoke --helm-release review-env-smoke --label-selector review.my-company.io/export-env=true --auth-mode kubeconfig
```

## Project Status

This project is intentionally scoped as a high-quality internal MVP.

That means:

- the architecture is ready to extend
- the current export types are implemented and smoke-tested
- the code is suitable to move into a real codebase

What is intentionally not in scope here:

- deployment pipeline integration
- GitLab or CI-specific wiring
- Helm hooks
- shared-directory publishing
- application protocol validation for Kafka or MongoDB

Those concerns should be added where the tool is actually integrated, not in this core package.
