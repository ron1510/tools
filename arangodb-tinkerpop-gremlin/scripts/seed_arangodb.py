#!/usr/bin/env python
from __future__ import annotations

import argparse
import base64
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

JsonValue = dict[str, Any] | list[Any]


class ArangoClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self._base_url = base_url.rstrip("/")
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        database: str = "_system",
        payload: JsonValue | None = None,
        missing_ok: bool = False,
    ) -> Any:
        url = f"{self._base_url}/_db/{quote(database, safe='')}{path}"
        data = None if payload is None else json.dumps(payload).encode()
        request = Request(url, data=data, headers=self._headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read()
        except HTTPError as exc:
            if missing_ok and exc.code == 404:
                return None
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc
        if not body:
            return None
        return json.loads(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the baseline ArangoDB graph.")
    parser.add_argument("--url", default="http://127.0.0.1:8529")
    parser.add_argument("--username", default="root")
    parser.add_argument("--password", default="change-me")
    parser.add_argument("--database", default="my_db")
    parser.add_argument("--graph", default="my_graph")
    return parser.parse_args()


def ensure_database(client: ArangoClient, database: str) -> None:
    databases = client.request("GET", "/_api/database")["result"]
    if database not in databases:
        client.request("POST", "/_api/database", payload={"name": database})


def recreate_collection(
    client: ArangoClient, database: str, name: str, *, edge: bool
) -> None:
    client.request(
        "DELETE",
        f"/_api/collection/{quote(name, safe='')}",
        database=database,
        missing_ok=True,
    )
    client.request(
        "POST",
        "/_api/collection",
        database=database,
        payload={"name": name, "type": 3 if edge else 2},
    )


def insert_documents(
    client: ArangoClient, database: str, collection: str, documents: JsonValue
) -> None:
    client.request(
        "POST",
        f"/_api/document/{quote(collection, safe='')}",
        database=database,
        payload=documents,
    )


def main() -> int:
    args = parse_args()
    client = ArangoClient(args.url, args.username, args.password)
    vertex_collection = "services"
    edge_collection = "depends_on"

    try:
        ensure_database(client, args.database)
        client.request(
            "DELETE",
            f"/_api/gharial/{quote(args.graph, safe='')}?dropCollections=true",
            database=args.database,
            missing_ok=True,
        )
        recreate_collection(client, args.database, vertex_collection, edge=False)
        recreate_collection(client, args.database, edge_collection, edge=True)

        vertices = [
            {"_key": "api", "name": "api", "kind": "service"},
            {"_key": "worker", "name": "worker", "kind": "service"},
        ]
        edges = [
            {
                "_key": "api-depends-on-worker",
                "_from": "services/api",
                "_to": "services/worker",
                "relationship": "depends_on",
            }
        ]
        insert_documents(client, args.database, vertex_collection, vertices)
        insert_documents(client, args.database, edge_collection, edges)
        client.request(
            "POST",
            "/_api/gharial",
            database=args.database,
            payload={
                "name": args.graph,
                "edgeDefinitions": [
                    {
                        "collection": edge_collection,
                        "from": [vertex_collection],
                        "to": [vertex_collection],
                    }
                ],
                "orphanCollections": [],
            },
        )
    except (RuntimeError, URLError) as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "database": args.database,
                "graph": args.graph,
                "vertexCollection": vertex_collection,
                "edgeCollection": edge_collection,
                "vertices": len(vertices),
                "edges": len(edges),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
