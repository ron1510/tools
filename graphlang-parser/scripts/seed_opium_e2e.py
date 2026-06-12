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

from opium_parser.resource_names import normalize_resource_name
from opium_parser.types import ResourceName

JsonValue = dict[str, Any] | list[Any]

LOGICAL_COLLECTIONS = {
    "roles": "users-data-product.user_roles",
    "users": "users-data-product.users",
    "abilities": "permissions-data-product.abilities",
    "teams": "org-data-product.teams",
    "departments": "org-data-product.departments",
    "projects": "delivery-data-product.projects",
    "services": "platform-data-product.services",
    "incidents": "ops-data-product.incidents",
    "regions": "infra-data-product.regions",
    "environments": "infra-data-product.environments",
    "documents": "knowledge-data-product.documents",
    "subscriptions": "users-data-product.user_role_subscriptions",
    "role_abilities": "permissions-data-product.role_abilities",
    "memberships": "org-data-product.user_memberships",
    "team_hierarchy": "org-data-product.team_hierarchy",
    "user_role_assignments": "users-data-product.user_role_assignments",
    "department_memberships": "org-data-product.department_memberships",
    "department_projects": "delivery-data-product.department_projects",
    "project_services": "platform-data-product.project_services",
    "service_dependencies": "platform-data-product.service_dependencies",
    "incident_impacts": "ops-data-product.incident_impacts",
    "service_regions": "infra-data-product.service_regions",
    "service_environments": "infra-data-product.service_environments",
    "document_links": "knowledge-data-product.document_links",
}
COLLECTIONS = {
    key: str(normalize_resource_name(ResourceName(name)))
    for key, name in LOGICAL_COLLECTIONS.items()
}

VERTEX_KEYS = (
    "roles",
    "users",
    "abilities",
    "teams",
    "departments",
    "projects",
    "services",
    "incidents",
    "regions",
    "environments",
    "documents",
)

EDGE_RELATIONS = {
    "subscriptions": ("roles", "roles"),
    "role_abilities": ("roles", "abilities"),
    "memberships": ("users", "teams"),
    "team_hierarchy": ("teams", "teams"),
    "user_role_assignments": ("users", "roles"),
    "department_memberships": ("users", "departments"),
    "department_projects": ("departments", "projects"),
    "project_services": ("projects", "services"),
    "service_dependencies": ("services", "services"),
    "incident_impacts": ("incidents", "services"),
    "service_regions": ("services", "regions"),
    "service_environments": ("services", "environments"),
    "document_links": ("documents", "documents"),
}


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
    parser = argparse.ArgumentParser(description="Seed the Opium e2e graph.")
    parser.add_argument("--url", default="http://127.0.0.1:8529")
    parser.add_argument("--username", default="root")
    parser.add_argument("--password", default="change-me")
    parser.add_argument("--database", default="my_db")
    parser.add_argument("--graph", default="my_graph")
    return parser.parse_args()


def vertex(collection: str, key: str) -> str:
    return f"{COLLECTIONS[collection]}/{key}"


def edge(
    key: str,
    from_collection: str,
    from_key: str,
    to_collection: str,
    to_key: str,
    **properties: Any,
) -> dict[str, Any]:
    return {
        "_key": key,
        "_from": vertex(from_collection, from_key),
        "_to": vertex(to_collection, to_key),
        **properties,
    }


def graph_documents() -> dict[str, list[dict[str, Any]]]:
    regions = ["us-east", "us-west", "eu-central", "ap-south", "global"]
    documents: dict[str, list[dict[str, Any]]] = {
        "roles": [
            {
                "_key": "admin",
                "name": "Admin",
                "age": 64,
                "score": 98.5,
                "priority": 10,
                "category": "internal",
                "active": True,
                "nullable_field": None,
            },
            {
                "_key": "editor",
                "name": "Editor",
                "age": 42,
                "score": 77.25,
                "priority": 5,
                "category": "internal",
                "active": True,
            },
            {
                "_key": "viewer",
                "name": "Viewer",
                "age": 21,
                "score": 12.5,
                "priority": 1,
                "category": "external",
                "active": False,
            },
            {
                "_key": "auditor",
                "name": "Auditor",
                "age": 85,
                "score": 64.75,
                "priority": 7,
                "category": "external",
                "active": True,
            },
            {
                "_key": "owner",
                "name": "Owner",
                "age": 91,
                "score": 100.0,
                "priority": 11,
                "category": "internal",
                "active": True,
            },
        ],
        "users": [
            {
                "_key": "alice",
                "name": "Alice Admin",
                "email": "alice@example.test",
                "active": True,
            },
            {
                "_key": "bob",
                "name": "Bob Editor",
                "email": "bob@example.test",
                "active": True,
            },
            {
                "_key": "carol",
                "name": "Carol Viewer",
                "email": "carol@example.test",
                "active": False,
            },
            {
                "_key": "dave",
                "name": "Dave Auditor",
                "email": "dave@example.test",
                "active": True,
            },
            {
                "_key": "erin",
                "name": "Erin Owner",
                "email": "erin@example.test",
                "active": True,
            },
        ],
        "abilities": [
            {"_key": "read", "name": "Read", "severity": 1},
            {"_key": "write", "name": "Write", "severity": 5},
            {"_key": "delete", "name": "Delete", "severity": 9},
            {"_key": "approve", "name": "Approve", "severity": 7},
        ],
        "teams": [
            {"_key": "platform", "name": "Platform", "tier": 2, "active": True},
            {"_key": "security", "name": "Security", "tier": 2, "active": True},
            {"_key": "executive", "name": "Executive", "tier": 1, "active": True},
            {"_key": "qa", "name": "QA", "tier": 3, "active": False},
        ],
        "departments": [
            {"_key": "eng", "name": "Engineering", "region": "global", "active": True},
            {
                "_key": "security",
                "name": "Security",
                "region": "global",
                "active": True,
            },
            {"_key": "product", "name": "Product", "region": "us", "active": True},
            {"_key": "data", "name": "Data", "region": "eu", "active": True},
            {"_key": "ops", "name": "Operations", "region": "global", "active": True},
            {"_key": "support", "name": "Support", "region": "apac", "active": False},
        ],
        "projects": [
            {
                "_key": f"project-{index}",
                "name": f"Project {index}",
                "tier": (index % 3) + 1,
                "active": index != 7,
            }
            for index in range(8)
        ],
        "services": [
            {
                "_key": f"service-{index}",
                "name": f"Service {index}",
                "priority": index + 1,
                "active": index % 3 != 0,
                "category": "core" if index % 2 == 0 else "edge",
            }
            for index in range(12)
        ],
        "incidents": [
            {
                "_key": f"incident-{index}",
                "name": f"Incident {index}",
                "severity": (index % 5) + 1,
                "open": index % 2 == 0,
            }
            for index in range(9)
        ],
        "regions": [
            {"_key": key, "name": key, "tier": index + 1}
            for index, key in enumerate(regions)
        ],
        "environments": [
            {
                "_key": key,
                "name": key,
                "production": key in {"prod", "dr"},
                "rank": index + 1,
            }
            for index, key in enumerate(("dev", "stage", "prod", "dr"))
        ],
        "documents": [
            {
                "_key": f"doc-{index}",
                "title": f"Document {index}",
                "public": index % 2 == 0,
            }
            for index in range(15)
        ],
    }
    documents.update(edge_documents(regions))
    return documents


def edge_documents(regions: list[str]) -> dict[str, list[dict[str, Any]]]:
    department_projects = [
        ("eng", "project-0"),
        ("eng", "project-1"),
        ("security", "project-2"),
        ("product", "project-3"),
        ("product", "project-4"),
        ("data", "project-5"),
        ("ops", "project-6"),
        ("support", "project-7"),
    ]
    return {
        "subscriptions": [
            edge(
                "editor-to-admin",
                "roles",
                "editor",
                "roles",
                "admin",
                relationship="reports_to",
                weight=1,
            ),
            edge(
                "viewer-to-editor",
                "roles",
                "viewer",
                "roles",
                "editor",
                relationship="reports_to",
                weight=2,
            ),
            edge(
                "auditor-to-admin",
                "roles",
                "auditor",
                "roles",
                "admin",
                relationship="reports_to",
                weight=3,
            ),
            edge(
                "admin-to-owner",
                "roles",
                "admin",
                "roles",
                "owner",
                relationship="reports_to",
                weight=4,
            ),
        ],
        "role_abilities": [
            edge("admin-delete", "roles", "admin", "abilities", "delete"),
            edge("admin-write", "roles", "admin", "abilities", "write"),
            edge("admin-approve", "roles", "admin", "abilities", "approve"),
            edge("editor-write", "roles", "editor", "abilities", "write"),
            edge("viewer-read", "roles", "viewer", "abilities", "read"),
        ],
        "memberships": [
            edge(
                "alice-platform",
                "users",
                "alice",
                "teams",
                "platform",
                role="lead",
                allocation=1.0,
            ),
            edge(
                "bob-platform",
                "users",
                "bob",
                "teams",
                "platform",
                role="member",
                allocation=0.75,
            ),
            edge(
                "carol-security",
                "users",
                "carol",
                "teams",
                "security",
                role="member",
                allocation=0.5,
            ),
            edge(
                "dave-security",
                "users",
                "dave",
                "teams",
                "security",
                role="lead",
                allocation=1.0,
            ),
            edge(
                "erin-executive",
                "users",
                "erin",
                "teams",
                "executive",
                role="owner",
                allocation=1.0,
            ),
        ],
        "team_hierarchy": [
            edge(
                "platform-to-executive",
                "teams",
                "platform",
                "teams",
                "executive",
                relationship="rolls_up_to",
                depth_hint=1,
            ),
            edge(
                "security-to-executive",
                "teams",
                "security",
                "teams",
                "executive",
                relationship="rolls_up_to",
                depth_hint=1,
            ),
            edge(
                "qa-to-platform",
                "teams",
                "qa",
                "teams",
                "platform",
                relationship="rolls_up_to",
                depth_hint=2,
            ),
        ],
        "user_role_assignments": [
            edge("alice-admin", "users", "alice", "roles", "admin"),
            edge("bob-editor", "users", "bob", "roles", "editor"),
            edge("carol-viewer", "users", "carol", "roles", "viewer"),
            edge("dave-auditor", "users", "dave", "roles", "auditor"),
            edge("erin-owner", "users", "erin", "roles", "owner"),
            edge("alice-owner", "users", "alice", "roles", "owner"),
            edge("bob-viewer", "users", "bob", "roles", "viewer"),
        ],
        "department_memberships": [
            edge("alice-eng", "users", "alice", "departments", "eng"),
            edge("bob-eng", "users", "bob", "departments", "eng"),
            edge("carol-security", "users", "carol", "departments", "security"),
            edge("dave-ops", "users", "dave", "departments", "ops"),
            edge("erin-product", "users", "erin", "departments", "product"),
            edge("alice-data", "users", "alice", "departments", "data"),
            edge("bob-support", "users", "bob", "departments", "support"),
        ],
        "department_projects": [
            edge(
                f"{department}-{project}",
                "departments",
                department,
                "projects",
                project,
            )
            for department, project in department_projects
        ],
        "project_services": [
            item
            for index in range(8)
            for item in (
                edge(
                    f"project-{index}-service-{index}",
                    "projects",
                    f"project-{index}",
                    "services",
                    f"service-{index}",
                ),
                edge(
                    f"project-{index}-service-{(index + 4) % 12}",
                    "projects",
                    f"project-{index}",
                    "services",
                    f"service-{(index + 4) % 12}",
                ),
            )
        ],
        "service_dependencies": [
            *[
                edge(
                    f"service-{index}-service-{index + 1}",
                    "services",
                    f"service-{index}",
                    "services",
                    f"service-{index + 1}",
                )
                for index in range(11)
            ],
            edge(
                "service-0-service-5", "services", "service-0", "services", "service-5"
            ),
            edge(
                "service-2-service-7", "services", "service-2", "services", "service-7"
            ),
            edge(
                "service-5-service-11",
                "services",
                "service-5",
                "services",
                "service-11",
            ),
        ],
        "incident_impacts": [
            edge(
                f"incident-{index}-service-{index % 12}",
                "incidents",
                f"incident-{index}",
                "services",
                f"service-{index % 12}",
                impact="high" if index % 3 == 0 else "medium",
            )
            for index in range(9)
        ],
        "service_regions": [
            edge(
                f"service-{index}-region-{index % 5}",
                "services",
                f"service-{index}",
                "regions",
                regions[index % 5],
            )
            for index in range(12)
        ],
        "service_environments": [
            *[
                edge(
                    f"service-{index}-{'prod' if index % 2 == 0 else 'stage'}",
                    "services",
                    f"service-{index}",
                    "environments",
                    "prod" if index % 2 == 0 else "stage",
                )
                for index in range(12)
            ],
            edge("service-0-dev", "services", "service-0", "environments", "dev"),
            edge("service-0-dr", "services", "service-0", "environments", "dr"),
        ],
        "document_links": [
            edge(
                f"doc-{index}-doc-{index + 1}",
                "documents",
                f"doc-{index}",
                "documents",
                f"doc-{index + 1}",
            )
            for index in range(14)
        ],
    }


def ensure_database(client: ArangoClient, database: str) -> None:
    databases = client.request("GET", "/_api/database")["result"]
    if database not in databases:
        client.request("POST", "/_api/database", payload={"name": database})


def recreate_collection(
    client: ArangoClient, database: str, name: str, *, edge_collection: bool
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
        payload={"name": name, "type": 3 if edge_collection else 2},
    )


def insert_documents(
    client: ArangoClient,
    database: str,
    collection: str,
    documents: list[dict[str, Any]],
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
    documents = graph_documents()

    try:
        ensure_database(client, args.database)
        client.request(
            "DELETE",
            f"/_api/gharial/{quote(args.graph, safe='')}?dropCollections=true",
            database=args.database,
            missing_ok=True,
        )
        for key in VERTEX_KEYS:
            recreate_collection(
                client, args.database, COLLECTIONS[key], edge_collection=False
            )
        for key in EDGE_RELATIONS:
            recreate_collection(
                client, args.database, COLLECTIONS[key], edge_collection=True
            )
        for key, collection_documents in documents.items():
            insert_documents(
                client,
                args.database,
                COLLECTIONS[key],
                collection_documents,
            )
        client.request(
            "POST",
            "/_api/gharial",
            database=args.database,
            payload={
                "name": args.graph,
                "edgeDefinitions": [
                    {
                        "collection": COLLECTIONS[edge_key],
                        "from": [COLLECTIONS[from_key]],
                        "to": [COLLECTIONS[to_key]],
                    }
                    for edge_key, (from_key, to_key) in EDGE_RELATIONS.items()
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
                "vertexCollections": [COLLECTIONS[key] for key in VERTEX_KEYS],
                "edgeCollections": [COLLECTIONS[key] for key in EDGE_RELATIONS],
                "counts": {
                    COLLECTIONS[key]: len(collection_documents)
                    for key, collection_documents in documents.items()
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
