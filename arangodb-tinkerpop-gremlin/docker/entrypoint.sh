#!/usr/bin/env bash
set -euo pipefail

required_env=(
  GREMLIN_SERVER_PORT
  GREMLIN_TRAVERSAL_SOURCE
  ARANGO_HOST
  ARANGO_PORT
  ARANGO_USER
  ARANGO_PASSWORD
  ARANGO_DATABASE
  ARANGO_GRAPH
  ARANGO_EDGE_DEFINITIONS_YAML
  ARANGO_GRAPH_TYPE
  ARANGO_ENABLE_DATA_DEFINITION
)

for name in "${required_env[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 1
  fi
done

export ARANGO_ORPHAN_COLLECTIONS_YAML="${ARANGO_ORPHAN_COLLECTIONS_YAML:-}"

mkdir -p "${GREMLIN_SERVER_HOME}/runtime-conf"

envsubst < "${GREMLIN_SERVER_HOME}/conf-templates/arangodb.yaml" > "${GREMLIN_SERVER_HOME}/runtime-conf/arangodb.yaml"
envsubst < "${GREMLIN_SERVER_HOME}/conf-templates/gremlin-server-arangodb.yaml" > "${GREMLIN_SERVER_HOME}/runtime-conf/gremlin-server-arangodb.yaml"
envsubst < "${GREMLIN_SERVER_HOME}/conf-templates/init.groovy" > "${GREMLIN_SERVER_HOME}/runtime-conf/init.groovy"

exec "${GREMLIN_SERVER_HOME}/bin/gremlin-server.sh" "${GREMLIN_SERVER_HOME}/runtime-conf/gremlin-server-arangodb.yaml"
