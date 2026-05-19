from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

from mongodb_migrator.errors import MongoMigratorError
from mongodb_migrator.models import CopyRequest, ExecutionOptions, MongoEndpointConfig, VerificationOptions
from mongodb_migrator.service import MongoMigrationService


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level))
    service = MongoMigrationService()

    try:
        if args.command == "copy":
            request = CopyRequest(
                source=MongoEndpointConfig(uri=args.source_uri, database=args.source_database),
                target=MongoEndpointConfig(uri=args.target_uri, database=args.target_database),
                include_collections=tuple(args.include_collection or ()),
                exclude_collections=tuple(args.exclude_collection or ()),
                execution=ExecutionOptions(
                    batch_size=args.batch_size,
                    checkpoint_path=args.checkpoint_path,
                    dry_run=args.dry_run,
                    replace_target=args.replace_target,
                ),
                verification=VerificationOptions(enabled=args.verify, sample_size=args.verify_sample_size),
            )
            rendered = service.run_copy(request)
            _emit_output(rendered, args.output_file)
            return 0

        job = service.load_job(args.config)
        if args.command == "inspect":
            _emit_output(service.inspect_job(job), args.output_file)
            return 0
        rendered = service.run_job(job)
        _emit_output(rendered, args.output_file)
        return 0
    except (MongoMigratorError, ValueError) as exc:
        print(f"mongodb-migrator: error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Copy and migrate MongoDB environments.")
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="WARNING",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    copy_parser = subparsers.add_parser("copy", help="Copy one MongoDB database environment into another.")
    copy_parser.add_argument("--source-uri", required=True)
    copy_parser.add_argument("--source-database", required=True)
    copy_parser.add_argument("--target-uri", required=True)
    copy_parser.add_argument("--target-database", required=True)
    copy_parser.add_argument("--include-collection", action="append")
    copy_parser.add_argument("--exclude-collection", action="append")
    copy_parser.add_argument("--replace-target", action="store_true")
    copy_parser.add_argument("--verify", action="store_true")
    copy_parser.add_argument("--verify-sample-size", type=int, default=25)
    copy_parser.add_argument("--dry-run", action="store_true")
    copy_parser.add_argument("--batch-size", type=int, default=1000)
    copy_parser.add_argument("--checkpoint-path")
    copy_parser.add_argument("--output-file")

    run_parser = subparsers.add_parser("run", help="Execute an advanced YAML-defined migration job.")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("--output-file")

    inspect_parser = subparsers.add_parser("inspect", help="Render a migration job summary without writing.")
    inspect_parser.add_argument("--config", required=True)
    inspect_parser.add_argument("--output-file")
    return parser


def _emit_output(rendered: str, output_file: str | None) -> None:
    if output_file is None:
        print(rendered, end="")
        return
    target = Path(output_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
