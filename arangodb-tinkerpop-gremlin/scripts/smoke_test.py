#!/usr/bin/env python
import argparse
import asyncio
import os
import sys

from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal


if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Gremlin smoke test for an existing ArangoDB graph.")
    parser.add_argument("--uri", default=os.getenv("GREMLIN_URI", "ws://localhost:8182/gremlin"))
    parser.add_argument("--traversal-source", default=os.getenv("GREMLIN_TRAVERSAL_SOURCE", "g"))
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--full-count", action="store_true", help="Run full V/E counts. Avoid on large graphs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    connection = None
    try:
        connection = DriverRemoteConnection(args.uri, args.traversal_source)
        g = traversal().with_remote(connection)

        print(f"Connected to {args.uri} using traversal source '{args.traversal_source}'.")

        vertex_probe = g.V().limit(1).count().next()
        edge_probe = g.E().limit(1).count().next()
        sample_vertices = g.V().limit(args.sample_limit).value_map(True).to_list()
        sample_vertex_labels = g.V().limit(args.sample_limit).label().dedup().to_list()
        sample_edge_labels = g.E().limit(args.sample_limit).label().dedup().to_list()

        print(f"Vertex probe (0 or 1): {vertex_probe}")
        print(f"Edge probe (0 or 1): {edge_probe}")
        print("Sample vertex labels:")
        for label in sample_vertex_labels:
            print(f"  - {label}")

        print("Sample edge labels:")
        for label in sample_edge_labels:
            print(f"  - {label}")

        print("Sample vertices:")
        for item in sample_vertices:
            print(f"  - {item}")

        if args.full_count:
            vertex_count = g.V().count().next()
            edge_count = g.E().count().next()
            print(f"Full vertex count: {vertex_count}")
            print(f"Full edge count: {edge_count}")

        return 0
    except Exception as exc:  # pragma: no cover - transport/provider failure path
        print("Smoke test failed.", file=sys.stderr)
        print(f"Reason: {exc}", file=sys.stderr)
        print("Check Gremlin Server logs, the traversal source name, and ArangoDB connectivity.", file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    sys.exit(main())
