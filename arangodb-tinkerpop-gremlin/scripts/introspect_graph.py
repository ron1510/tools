#!/usr/bin/env python
import argparse
import asyncio
import os
import sys

from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import __


if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect an existing graph through Gremlin without mutating it.")
    parser.add_argument("--uri", default=os.getenv("GREMLIN_URI", "ws://localhost:8182/gremlin"))
    parser.add_argument("--traversal-source", default=os.getenv("GREMLIN_TRAVERSAL_SOURCE", "g"))
    parser.add_argument("--vertex-id", default=None)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--full-count", action="store_true", help="Run full V/E counts. Avoid on large graphs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    connection = None
    try:
        connection = DriverRemoteConnection(args.uri, args.traversal_source)
        g = traversal().with_remote(connection)

        sample_vertices = g.V().limit(args.limit).element_map().to_list()
        sample_vertex_labels = g.V().limit(args.limit).label().dedup().to_list()
        sample_edge_labels = g.E().limit(args.limit).label().dedup().to_list()

        vertex_id = args.vertex_id
        if vertex_id is None:
            vertex_ids = g.V().limit(1).id_().to_list()
            vertex_id = vertex_ids[0] if vertex_ids else None

        print(f"Connected to {args.uri} using traversal source '{args.traversal_source}'.")
        print("Sample vertices:")
        for item in sample_vertices:
            print(f"  - {item}")

        print("Sample vertex labels:")
        for label in sample_vertex_labels:
            print(f"  - {label}")

        print("Sample edge labels:")
        for label in sample_edge_labels:
            print(f"  - {label}")

        if args.full_count:
            print(f"Full vertex count: {g.V().count().next()}")
            print(f"Full edge count: {g.E().count().next()}")

        if vertex_id is None:
            print("No vertices were found, so adjacency introspection was skipped.")
            return 0

        print(f"Inspecting adjacency for vertex id: {vertex_id}")
        vertex_details = g.V(vertex_id).element_map().next()
        outgoing = (
            g.V(vertex_id)
            .out_e()
            .limit(args.limit)
            .project("edgeId", "label", "inV")
            .by(__.id_())
            .by(__.label())
            .by(__.in_v().id_())
            .to_list()
        )
        incoming = (
            g.V(vertex_id)
            .in_e()
            .limit(args.limit)
            .project("edgeId", "label", "outV")
            .by(__.id_())
            .by(__.label())
            .by(__.out_v().id_())
            .to_list()
        )

        print(f"Vertex: {vertex_details}")
        print("Outgoing edges:")
        for item in outgoing:
            print(f"  - {item}")

        print("Incoming edges:")
        for item in incoming:
            print(f"  - {item}")

        return 0
    except Exception as exc:  # pragma: no cover - transport/provider failure path
        print("Graph introspection failed.", file=sys.stderr)
        print(f"Reason: {exc}", file=sys.stderr)
        print("Check the selected vertex id, provider configuration, and Gremlin Server logs.", file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    sys.exit(main())
