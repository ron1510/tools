from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).parents[1]
    / "charts"
    / "gremlin-arangodb-poc"
    / "scripts"
    / "topology_sync.py"
)
SPEC = importlib.util.spec_from_file_location("topology_sync", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
topology_sync = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = topology_sync
SPEC.loader.exec_module(topology_sync)


class TopologyTests(unittest.TestCase):
    def test_discovers_non_system_document_and_edge_collections(self) -> None:
        topology = topology_sync.discover_topology(
            [
                {"name": "users", "type": 2, "isSystem": False},
                {"name": "memberships", "type": 3, "isSystem": False},
                {"name": "_graphs", "type": 2, "isSystem": True},
            ]
        )

        self.assertEqual(topology.vertex_collections, ("users",))
        self.assertEqual(topology.edge_collections, ("memberships",))

    def test_edges_connect_every_vertex_collection(self) -> None:
        topology = topology_sync.Topology(("projects", "users"), ("memberships",))

        self.assertEqual(
            topology.edge_definitions,
            [
                {
                    "collection": "memberships",
                    "from": ["projects", "users"],
                    "to": ["projects", "users"],
                }
            ],
        )
        self.assertEqual(topology.orphan_collections, [])

    def test_document_collections_are_orphans_without_edges(self) -> None:
        topology = topology_sync.Topology(("projects", "users"), ())

        self.assertEqual(topology.edge_definitions, [])
        self.assertEqual(topology.orphan_collections, ["projects", "users"])

    def test_digest_is_stable(self) -> None:
        first = topology_sync.Topology(("projects", "users"), ("memberships",))
        second = topology_sync.Topology(("projects", "users"), ("memberships",))

        self.assertEqual(first.digest(), second.digest())

    def test_provider_config_uses_provider_edge_syntax(self) -> None:
        config = topology_sync.render_provider_config(
            database="my_db",
            graph="my_graph",
            graph_type="COMPLEX",
            host="arangodb",
            port=8529,
            topology=topology_sync.Topology(
                ("projects", "users"),
                ("memberships",),
            ),
        )

        self.assertIn(
            '"memberships:[projects,users]->[projects,users]"',
            config,
        )
        self.assertIn("enableDataDefinition: false", config)


class FakeArangoClient:
    def __init__(self, graph: dict[str, object] | None) -> None:
        self.current_graph = graph
        self.calls: list[tuple[str, str]] = []

    def graph(
        self,
        graph: str,
        *,
        missing_ok: bool = False,
    ) -> dict[str, object] | None:
        return self.current_graph

    def create_graph(self, graph: str, topology: object) -> None:
        self.calls.append(("create_graph", graph))

    def add_edge_definition(self, graph: str, definition: dict[str, object]) -> None:
        self.calls.append(("add_edge", str(definition["collection"])))

    def update_edge_definition(
        self,
        graph: str,
        definition: dict[str, object],
    ) -> None:
        self.calls.append(("update_edge", str(definition["collection"])))

    def remove_edge_definition(self, graph: str, collection: str) -> None:
        self.calls.append(("remove_edge", collection))

    def add_orphan_collection(self, graph: str, collection: str) -> None:
        self.calls.append(("add_orphan", collection))

    def remove_orphan_collection(self, graph: str, collection: str) -> None:
        self.calls.append(("remove_orphan", collection))


class ReconciliationTests(unittest.TestCase):
    def test_creates_missing_graph(self) -> None:
        client = FakeArangoClient(None)

        changed = topology_sync.reconcile_graph(
            client,
            "my_graph",
            topology_sync.Topology(("users",), ()),
            prune=True,
        )

        self.assertTrue(changed)
        self.assertEqual(client.calls, [("create_graph", "my_graph")])

    def test_updates_edges_and_prunes_stale_metadata(self) -> None:
        client = FakeArangoClient(
            {
                "edgeDefinitions": [
                    {"collection": "stale", "from": ["users"], "to": ["users"]},
                    {"collection": "memberships", "from": ["users"], "to": ["users"]},
                ],
                "orphanCollections": ["legacy"],
            }
        )

        changed = topology_sync.reconcile_graph(
            client,
            "my_graph",
            topology_sync.Topology(("projects", "users"), ("memberships",)),
            prune=True,
        )

        self.assertTrue(changed)
        self.assertEqual(
            client.calls,
            [
                ("remove_edge", "stale"),
                ("remove_orphan", "legacy"),
                ("update_edge", "memberships"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
