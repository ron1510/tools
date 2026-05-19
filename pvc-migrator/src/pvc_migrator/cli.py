from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from pvc_migrator.errors import PvcMigratorError
from pvc_migrator.formatting import render_plan
from pvc_migrator.models import ChartInput, ClusterRef, PlanRequest
from pvc_migrator.service import MigrationPlannerService


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    request = PlanRequest(
        source=ChartInput(
            chart=args.source_chart,
            values_file=args.source_values,
            release_name=args.source_release,
        ),
        destination=ChartInput(
            chart=args.dest_chart,
            values_file=args.dest_values,
            release_name=args.dest_release,
        ),
        source_cluster=ClusterRef(namespace=args.source_namespace, context=args.source_context),
        destination_cluster=ClusterRef(namespace=args.dest_namespace, context=args.dest_context),
        extra_pvc_selector=args.extra_pvc_selector,
        include_workloads=tuple(args.include_workload or ()),
        exclude_workloads=tuple(args.exclude_workload or ()),
        output_format=args.output,
        engine_override=args.engine,
        allow_aux_pvc_copy=args.allow_aux_pvc_copy,
        mapping_file=args.mapping_file,
    )

    service = MigrationPlannerService()
    try:
        plan = service.build_plan(request)
        if args.command == "execute":
            service.execute_plan(
                plan,
                approved=args.approve,
                selected_workloads=tuple(args.workload or ()),
                resume_run_id=args.resume_run_id,
            )
        rendered = render_plan(plan, args.output)
        _emit_output(rendered, args.output_file)
    except PvcMigratorError as exc:
        print(f"pvc-migrator: error: {exc}", file=sys.stderr)
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan and execute workload-aware PVC migrations.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command_name in ("plan", "execute"):
        subparser = subparsers.add_parser(command_name)
        _add_common_arguments(subparser)
    return parser


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-chart", required=True)
    parser.add_argument("--source-values")
    parser.add_argument("--source-release")
    parser.add_argument("--dest-chart", required=True)
    parser.add_argument("--dest-values")
    parser.add_argument("--dest-release")
    parser.add_argument("--source-namespace", required=True)
    parser.add_argument("--dest-namespace", required=True)
    parser.add_argument("--source-context")
    parser.add_argument("--dest-context")
    parser.add_argument("--extra-pvc-selector")
    parser.add_argument("--include-workload", action="append")
    parser.add_argument("--exclude-workload", action="append")
    parser.add_argument("--engine", default="auto")
    parser.add_argument("--allow-aux-pvc-copy", action="store_true")
    parser.add_argument("--mapping-file")
    parser.add_argument("--output", choices=("table", "json", "yaml"), default="table")
    parser.add_argument("--output-file")
    parser.add_argument("--workload", action="append")
    parser.add_argument("--resume-run-id")
    parser.add_argument("--approve", action="store_true")


def _emit_output(rendered: str, output_file: str | None) -> None:
    if output_file is None:
        print(rendered, end="")
        return
    target = Path(output_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
