#!/usr/bin/env python

import argparse
import asyncio
import os
import pprint
import sys

from gremlin_python.driver.client import Client

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit a Gremlin script.")
    parser.add_argument("query")
    parser.add_argument(
        "--uri", default=os.getenv("GREMLIN_URI", "ws://localhost:8182/gremlin")
    )
    parser.add_argument(
        "--traversal-source", default=os.getenv("GREMLIN_TRAVERSAL_SOURCE", "g")
    )
    args = parser.parse_args()

    client = Client(args.uri, args.traversal_source)
    try:
        pprint.pp(client.submit(args.query).all().result())
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
