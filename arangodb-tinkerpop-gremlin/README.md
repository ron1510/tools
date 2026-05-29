# ArangoDB TinkerPop Gremlin Lab POC

This repository is a small lab environment for evaluating Apache TinkerPop Gremlin as a replacement candidate for an internal custom query language that currently lowers into ArangoDB AQL.

The goal is not to build another translator. The goal is to run direct Gremlin traversals against an existing ArangoDB graph, keep the setup observable, and keep native AQL available as an escape hatch where Gremlin is not the right fit.

The primary deployment target is Kubernetes via Helm. A `docker-compose.yml` file is also included as an optional fallback for quick local image validation.

## What This POC Includes

- A simple `charts/arangodb-lab` Helm chart for spinning up a single-server ArangoDB instance locally without CRDs or operators.
- A Gremlin Server image with the ArangoDB TinkerPop provider installed at image build time.
- A Helm chart that deploys only Gremlin Server.
- Environment-rendered Gremlin and ArangoDB config templates.
- Read-only Python smoke and introspection scripts using `gremlin-python`.
- A repeatable `scripts/seed_arangodb.js` seed script that creates a tiny named graph for end-to-end validation.
- Pinned default versions with explicit compatibility notes.

## Version Compatibility

- Apache TinkerPop / Gremlin Server default: `3.8.1`
- ArangoDB TinkerPop provider default: `4.0.0`

ArangoDB documents that provider `4.*` matches Apache TinkerPop `3.8.*`. This repository uses that mapping, but you should still re-check provider release notes before moving beyond a lab POC.

References:

- ArangoDB TinkerPop provider docs: <https://docs.arango.ai/ecosystem/integrations/arangodb-tinkerpop-provider/>
- Apache TinkerPop downloads: <https://tinkerpop.apache.org/download.html>
- Maven artifact: <https://central.sonatype.com/artifact/com.arangodb/arangodb-tinkerpop-provider>

## Architecture

```text
Python client
  -> WebSocket ws://localhost:8182/gremlin
  -> Gremlin Server
  -> ArangoDB TinkerPop provider
  -> Existing ArangoDB graph
```

## Why `COMPLEX` Mode

This POC defaults to `COMPLEX` because that is the better fit when vertex and edge labels already map to real ArangoDB collections. If your existing graph shape or edge definitions do not line up with the provider's expectations, you will need to adjust `ARANGO_GRAPH_TYPE` and possibly the graph configuration itself.

## Why `enableDataDefinition=false`

This repository assumes your ArangoDB database, graph, and collections already exist. `enableDataDefinition=false` is the safe default because it prevents Gremlin-side schema or graph-definition changes in a live existing database.

Nothing destructive or mutating runs by default in the image startup path or in the Python scripts.

## Repository Layout

```text
.
|-- Dockerfile
|-- docker-compose.yml
|-- .env.example
|-- Makefile
|-- README.md
|-- conf/
|   |-- arangodb.yaml
|   |-- gremlin-server-arangodb.yaml
|   `-- init.groovy
|-- docker/
|   `-- entrypoint.sh
|-- charts/
|   |-- arangodb-lab/
|   `-- gremlin-arangodb-poc/
`-- scripts/
    |-- smoke_test.py
    |-- introspect_graph.py
    `-- seed_arangodb.js
```

## Quick Start

### 1. Build the Gremlin image

```bash
docker build \
  --build-arg TINKERPOP_VERSION=3.8.1 \
  --build-arg ARANGO_TINKERPOP_PROVIDER_VERSION=4.0.0 \
  -t gremlin-arangodb-poc:local .
```

Equivalent:

```bash
make image-build
```

### 2. If using `kind`, load the image

```bash
kind load docker-image gremlin-arangodb-poc:local --name review-env-smoke
```

### 3. Install the local ArangoDB lab chart

```bash
helm upgrade --install arangodb-lab charts/arangodb-lab \
  --namespace gremlin-lab \
  --create-namespace
```

### 4. Seed the disposable lab graph

```bash
kubectl cp scripts/seed_arangodb.js gremlin-lab/arangodb-lab-0:/tmp/seed_arangodb.js
kubectl exec -n gremlin-lab arangodb-lab-0 -- \
  arangosh --server.endpoint tcp://127.0.0.1:8529 \
  --server.username root \
  --server.password change-me \
  --javascript.execute /tmp/seed_arangodb.js
```

Seeded test objects:

- database: `my_db`
- graph: `my_graph`
- vertex collection: `services`
- edge collection: `depends_on`

### 5. Install the Gremlin chart

```bash
helm upgrade --install gremlin-arangodb-poc charts/gremlin-arangodb-poc \
  --namespace gremlin-lab \
  --create-namespace \
  --set image.repository=gremlin-arangodb-poc \
  --set image.tag=local \
  --set arangodb.host=arangodb-lab.gremlin-lab.svc.cluster.local \
  --set arangodb.port=8529 \
  --set arangodb.database=my_db \
  --set arangodb.graph=my_graph \
  --set arangodb.auth.username=root \
  --set arangodb.auth.password=change-me
```

### 6. Inspect the running environment

```bash
kubectl get pods,svc -n gremlin-lab
kubectl logs -n gremlin-lab deployment/gremlin-arangodb-poc -f
kubectl logs -n gremlin-lab statefulset/arangodb-lab -f
```

### 7. Port-forward for local access

ArangoDB UI:

```bash
kubectl port-forward -n gremlin-lab service/arangodb-lab 8529:8529
```

Gremlin endpoint:

```bash
kubectl port-forward -n gremlin-lab service/gremlin-arangodb-poc 8182:8182
```

Local endpoints:

- ArangoDB UI: `http://localhost:8529`
- Gremlin endpoint: `ws://localhost:8182/gremlin`

ArangoDB login:

- user: `root`
- password: `change-me`

## Running the Python Clients

Create a virtual environment and install a gremlin-python version aligned with the server:

```bash
python -m venv .venv
. .venv/bin/activate
pip install gremlinpython==3.8.1
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install gremlinpython==3.8.1
```

Run the smoke test:

```bash
python scripts/smoke_test.py --uri ws://localhost:8182/gremlin
```

Run the graph introspection script:

```bash
python scripts/introspect_graph.py --uri ws://localhost:8182/gremlin --limit 10
python scripts/introspect_graph.py --uri ws://localhost:8182/gremlin --vertex-id services/api --limit 10
```

Use `--full-count` only if full graph scans are acceptable:

```bash
python scripts/smoke_test.py --uri ws://localhost:8182/gremlin --full-count
python scripts/introspect_graph.py --uri ws://localhost:8182/gremlin --full-count
```

## Optional Docker Compose Run

This is not the primary path, but it is useful for image validation outside Kubernetes.

```bash
cp .env.example .env
docker compose build
docker compose up -d
docker compose logs -f gremlin-server
```

## Configuration for an Existing ArangoDB

For the optional Docker flow, copy `.env.example` to `.env` and update:

- `ARANGO_HOST`
- `ARANGO_PORT`
- `ARANGO_USER`
- `ARANGO_PASSWORD`
- `ARANGO_DATABASE`
- `ARANGO_GRAPH`
- `ARANGO_EDGE_DEFINITIONS_YAML`

For the Helm flow, edit [charts/gremlin-arangodb-poc/values.yaml](/abs/path/C:/Users/Ron/Documents/repos/arangodb-tinkerpop-gremlin/charts/gremlin-arangodb-poc/values.yaml) or override values on the command line:

- `arangodb.host`
- `arangodb.port`
- `arangodb.database`
- `arangodb.graph`
- `arangodb.graphType`
- `arangodb.enableDataDefinition`
- `arangodb.edgeDefinitions`
- `arangodb.orphanCollections`

Default local-lab DNS for the included ArangoDB chart:

`arangodb-lab.gremlin-lab.svc.cluster.local`

Credentials come from a Kubernetes Secret by default. For a lab POC this repo allows a generated secret, but real credentials should not be committed.

## Current Validated Lab State

This repository was validated end to end against:

- `kind` cluster `review-env-smoke`
- namespace `gremlin-lab`
- Helm releases `arangodb-lab` and `gremlin-arangodb-poc`
- ArangoDB seeded with:
  - vertices: `services/api`, `services/worker`
  - edge: `depends_on/api-depends-on-worker`

Validated client behavior:

- `scripts/smoke_test.py` connected successfully and returned sampled vertices and edges
- `scripts/introspect_graph.py` connected successfully and traversed outgoing adjacency from `services/api`

## Common Failures

### Cannot connect to ArangoDB

- The Gremlin pod cannot resolve or reach `arangodb.host`.
- The Kubernetes namespace or Service DNS name is wrong.
- Local cluster networking is blocking traffic.

### Wrong graph name

- `arangodb.graph` must match an existing named ArangoDB graph exactly.
- If the graph exists but has different edge definitions than expected, traversals may fail or return incomplete results.

### Wrong database

- `arangodb.database` must point at the database that contains the named graph.

### Wrong graph type

- `COMPLEX` is the default here.
- If the existing graph does not map cleanly between labels and collections, verify whether `SIMPLE` or a different config shape is actually required.

### Auth failure

- Check the secret values used for `ARANGO_USER` and `ARANGO_PASSWORD`.
- Confirm the user has permission to the selected database and graph collections.

### Provider or plugin not loaded

- Rebuild the image if provider installation failed during `docker build`.
- Check Gremlin Server startup logs for plugin load failures.
- Confirm the provider version still matches your selected TinkerPop version.

### Traversal source `g` not found

- The server config and init script must expose traversal source `g`.
- If you change it, also change `GREMLIN_TRAVERSAL_SOURCE` or `--traversal-source`.

### Serializer mismatch

- `gremlin-python` should align with the Gremlin Server major/minor version.
- This image enables GraphBinary and GraphSON, but GraphBinary is the preferred path.

### Docker cannot reach host ArangoDB

- For the optional compose flow, `host.docker.internal` is the default.
- On some Linux Docker setups you may need a real host IP or DNS name instead.

## Air-Gapped Build Notes

This image build requires access to:

- the Apache TinkerPop distribution artifact
- Maven repositories for `gremlin-server.sh install`

For restricted environments:

- pre-bake the Gremlin Server distribution into your build context or internal image base
- mirror Maven artifacts through Artifactory, Nexus, or another internal repository
- pin the exact Gremlin Server and provider versions
- do not move dependency installation to container or pod startup

## Engineering Guidance

- Keep the POC small and observable.
- Do not build a translator from the old custom QL into Gremlin.
- Prefer direct Gremlin traversal examples.
- Prefer bytecode traversals from `gremlin-python`, not raw script strings.
- Avoid Gremlin lambdas.
- Keep native AQL as an escape hatch for cases where Gremlin is awkward or slower.

## Next Steps

See [docs/FUTURE_IDEAS.md](/abs/path/C:/Users/Ron/Documents/repos/arangodb-tinkerpop-gremlin/docs/FUTURE_IDEAS.md) for concrete follow-on directions after this POC.

## Installed Skill

I installed the curated `security-best-practices` skill because it is the only additional skill that is directly useful for this project's container, secret, and Kubernetes defaults.

Restart Codex to pick up new skills.
