#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("topology-sync")
DOCUMENT_COLLECTION: Final = 2
EDGE_COLLECTION: Final = 3


@dataclass(frozen=True)
class Topology:
    vertex_collections: tuple[str, ...]
    edge_collections: tuple[str, ...]

    @property
    def edge_definitions(self) -> list[dict[str, Any]]:
        vertices = list(self.vertex_collections)
        return [
            {"collection": edge, "from": vertices, "to": vertices}
            for edge in self.edge_collections
            if vertices
        ]

    @property
    def orphan_collections(self) -> list[str]:
        return [] if self.edge_definitions else list(self.vertex_collections)

    def digest(self) -> str:
        payload = {
            "edgeDefinitions": self.edge_definitions,
            "orphanCollections": self.orphan_collections,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class HttpClient:
    def __init__(
        self,
        base_url: str,
        headers: dict[str, str],
        context: ssl.SSLContext | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = headers
        self._context = context

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        missing_ok: bool = False,
    ) -> dict[str, Any] | None:
        body = None if payload is None else json.dumps(payload).encode()
        request = Request(
            f"{self._base_url}{path}",
            data=body,
            headers=self._headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=30, context=self._context) as response:
                response_body = response.read()
        except HTTPError as exc:
            if missing_ok and exc.code == 404:
                return None
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"{method} {path} failed: {exc.code} {detail}") from exc
        return None if not response_body else json.loads(response_body)


class ArangoClient:
    def __init__(self, url: str, database: str, username: str, password: str) -> None:
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._http = HttpClient(
            f"{url.rstrip('/')}/_db/{quote(database, safe='')}",
            {
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
        )

    def collections(self) -> list[dict[str, Any]]:
        response = self._http.request("GET", "/_api/collection")
        assert response is not None
        return response["result"]

    def graph(self, graph: str, *, missing_ok: bool = False) -> dict[str, Any] | None:
        response = self._http.request(
            "GET",
            f"/_api/gharial/{quote(graph, safe='')}",
            missing_ok=missing_ok,
        )
        return None if response is None else response["graph"]

    def create_graph(self, graph: str, topology: Topology) -> None:
        self._http.request(
            "POST",
            "/_api/gharial",
            payload={
                "name": graph,
                "edgeDefinitions": topology.edge_definitions,
                "orphanCollections": topology.orphan_collections,
            },
        )

    def add_edge_definition(self, graph: str, definition: dict[str, Any]) -> None:
        self._http.request(
            "POST",
            f"/_api/gharial/{quote(graph, safe='')}/edge",
            payload=definition,
        )

    def update_edge_definition(self, graph: str, definition: dict[str, Any]) -> None:
        collection = quote(str(definition["collection"]), safe="")
        self._http.request(
            "PUT",
            f"/_api/gharial/{quote(graph, safe='')}/edge/{collection}",
            payload=definition,
        )

    def remove_edge_definition(self, graph: str, collection: str) -> None:
        self._http.request(
            "DELETE",
            f"/_api/gharial/{quote(graph, safe='')}/edge/"
            f"{quote(collection, safe='')}?dropCollections=false",
        )

    def add_orphan_collection(self, graph: str, collection: str) -> None:
        self._http.request(
            "POST",
            f"/_api/gharial/{quote(graph, safe='')}/vertex",
            payload={"collection": collection},
        )

    def remove_orphan_collection(self, graph: str, collection: str) -> None:
        self._http.request(
            "DELETE",
            f"/_api/gharial/{quote(graph, safe='')}/vertex/"
            f"{quote(collection, safe='')}?dropCollection=false",
        )


def discover_topology(collections: list[dict[str, Any]]) -> Topology:
    visible = [
        item
        for item in collections
        if not item.get("isSystem", False) and not str(item["name"]).startswith("_")
    ]
    vertices = sorted(
        str(item["name"]) for item in visible if item.get("type") == DOCUMENT_COLLECTION
    )
    edges = sorted(
        str(item["name"]) for item in visible if item.get("type") == EDGE_COLLECTION
    )
    return Topology(tuple(vertices), tuple(edges))


def _canonical_definition(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        "collection": str(definition["collection"]),
        "from": sorted(str(item) for item in definition.get("from", [])),
        "to": sorted(str(item) for item in definition.get("to", [])),
    }


def reconcile_graph(
    client: ArangoClient,
    graph_name: str,
    desired: Topology,
    *,
    prune: bool,
) -> bool:
    graph = client.graph(graph_name, missing_ok=True)
    if graph is None:
        client.create_graph(graph_name, desired)
        LOGGER.info("Created graph %s", graph_name)
        return True

    changed = False
    current_definitions = {
        str(item["collection"]): _canonical_definition(item)
        for item in graph.get("edgeDefinitions", [])
    }
    desired_definitions = {
        str(item["collection"]): _canonical_definition(item)
        for item in desired.edge_definitions
    }
    current_orphans = set(str(item) for item in graph.get("orphanCollections", []))
    desired_orphans = set(desired.orphan_collections)

    if prune:
        for collection in sorted(current_definitions.keys() - desired_definitions.keys()):
            client.remove_edge_definition(graph_name, collection)
            LOGGER.info("Removed edge definition %s", collection)
            changed = True
        for collection in sorted(current_orphans - desired_orphans):
            client.remove_orphan_collection(graph_name, collection)
            LOGGER.info("Removed orphan collection %s", collection)
            changed = True

    for collection, definition in desired_definitions.items():
        current = current_definitions.get(collection)
        if current is None:
            client.add_edge_definition(graph_name, definition)
            LOGGER.info("Added edge definition %s", collection)
            changed = True
        elif current != definition:
            client.update_edge_definition(graph_name, definition)
            LOGGER.info("Updated edge definition %s", collection)
            changed = True

    for collection in sorted(desired_orphans - current_orphans):
        client.add_orphan_collection(graph_name, collection)
        LOGGER.info("Added orphan collection %s", collection)
        changed = True

    return changed


def topology_from_graph(graph: dict[str, Any]) -> Topology:
    vertices = set(str(item) for item in graph.get("orphanCollections", []))
    edges: set[str] = set()
    for definition in graph.get("edgeDefinitions", []):
        edges.add(str(definition["collection"]))
        vertices.update(str(item) for item in definition.get("from", []))
        vertices.update(str(item) for item in definition.get("to", []))
    return Topology(tuple(sorted(vertices)), tuple(sorted(edges)))


def render_provider_config(
    *,
    database: str,
    graph: str,
    graph_type: str,
    host: str,
    port: int,
    topology: Topology,
) -> str:
    edge_definitions = [
        f"{item['collection']}:[{','.join(item['from'])}]->[{','.join(item['to'])}]"
        for item in topology.edge_definitions
    ]
    return (
        "gremlin:\n"
        '  graph: "com.arangodb.tinkerpop.gremlin.structure.ArangoDBGraph"\n'
        "  arangodb:\n"
        "    conf:\n"
        "      graph:\n"
        f"        db: {json.dumps(database)}\n"
        f"        name: {json.dumps(graph)}\n"
        f"        type: {graph_type}\n"
        "        enableDataDefinition: false\n"
        f"        orphanCollections: {json.dumps(topology.orphan_collections)}\n"
        f"        edgeDefinitions: {json.dumps(edge_definitions)}\n"
        "      driver:\n"
        '        user: "${env:ARANGO_USER}"\n'
        '        password: "${env:ARANGO_PASSWORD}"\n'
        "        hosts:\n"
        f"          - {json.dumps(f'{host}:{port}')}\n"
    )


def patch_deployment(deployment: str, topology_hash: str) -> bool:
    service_account = Path("/var/run/secrets/kubernetes.io/serviceaccount")
    namespace = os.getenv("POD_NAMESPACE") or (service_account / "namespace").read_text().strip()
    token = (service_account / "token").read_text().strip()
    http = HttpClient(
        "https://kubernetes.default.svc",
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/strategic-merge-patch+json",
        },
        ssl.create_default_context(cafile=str(service_account / "ca.crt")),
    )
    path = (
        f"/apis/apps/v1/namespaces/{quote(namespace, safe='')}/deployments/"
        f"{quote(deployment, safe='')}"
    )
    current = http.request("GET", path)
    assert current is not None
    annotations = (
        current.get("spec", {})
        .get("template", {})
        .get("metadata", {})
        .get("annotations", {})
    )
    if annotations.get("gremlin.arangodb/topology-hash") == topology_hash:
        LOGGER.info("Deployment already has topology hash %s", topology_hash)
        return False
    http.request(
        "PATCH",
        path,
        payload={
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "gremlin.arangodb/topology-hash": topology_hash
                        }
                    }
                }
            }
        },
    )
    LOGGER.info("Triggered rolling restart for deployment %s", deployment)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize ArangoDB collections with Gremlin topology."
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--patch-deployment")
    parser.add_argument("--no-prune", action="store_true")
    return parser.parse_args()


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def main() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    args = parse_args()
    database = required_env("ARANGO_DATABASE")
    graph_name = required_env("ARANGO_GRAPH")
    client = ArangoClient(
        required_env("ARANGO_URL"),
        database,
        required_env("ARANGO_USER"),
        required_env("ARANGO_PASSWORD"),
    )
    desired = discover_topology(client.collections())
    LOGGER.info(
        "Discovered %d vertex collections and %d edge collections",
        len(desired.vertex_collections),
        len(desired.edge_collections),
    )
    changed = reconcile_graph(client, graph_name, desired, prune=not args.no_prune)
    graph = client.graph(graph_name)
    assert graph is not None
    effective = topology_from_graph(graph)

    if args.output is not None:
        args.output.write_text(
            render_provider_config(
                database=database,
                graph=graph_name,
                graph_type=os.getenv("ARANGO_GRAPH_TYPE", "COMPLEX"),
                host=required_env("ARANGO_HOST"),
                port=int(os.getenv("ARANGO_PORT", "8529")),
                topology=effective,
            ),
            encoding="utf-8",
        )
        LOGGER.info("Wrote provider configuration to %s", args.output)

    if args.patch_deployment:
        patch_deployment(args.patch_deployment, effective.digest())
    elif not changed:
        LOGGER.info("Topology is already synchronized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
