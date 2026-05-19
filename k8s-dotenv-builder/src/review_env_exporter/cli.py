from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Final, Sequence

from review_env_exporter.errors import ReviewEnvExporterError
from review_env_exporter.models import ClusterAccessConfig, ResourceSelectionConfig
from review_env_exporter.providers import KubernetesApiResourceProvider
from review_env_exporter.service import ReviewEnvExporterService

SUCCESS_EXIT_CODE: Final[int] = 0
FAILURE_EXIT_CODE: Final[int] = 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level))

    try:
        resource_kinds = frozenset(args.kind or ("Route", "Service"))
        access_config = ClusterAccessConfig(
            auth_mode=args.auth_mode,
            kubeconfig_path=args.kubeconfig,
            kube_context=args.context,
        )
        selection_config = ResourceSelectionConfig(
            namespace=args.namespace,
            helm_release_name=args.helm_release,
            label_selector=args.label_selector,
            resource_kinds=resource_kinds,
        )

        provider = KubernetesApiResourceProvider(access_config=access_config)
        service = ReviewEnvExporterService(provider=provider, config=selection_config)
        rendered = service.generate_env()
        _emit_output(rendered, output_path=args.output)
    except (ReviewEnvExporterError, ValueError) as exc:
        print(f"review-env-exporter: error: {exc}", file=sys.stderr)
        return FAILURE_EXIT_CODE

    return SUCCESS_EXIT_CODE


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a .env file from Kubernetes/OpenShift metadata."
    )
    parser.add_argument("--namespace", required=True, help="Namespace to inspect.")
    parser.add_argument(
        "--kind",
        action="append",
        dest="kind",
        choices=("Route", "Service"),
        default=None,
        help="Resource kind to fetch. May be provided multiple times.",
    )
    parser.add_argument(
        "--helm-release",
        default=None,
        help="Optional Helm release name. Translates to label selector app.kubernetes.io/instance=<release>.",
    )
    parser.add_argument(
        "--label-selector", default=None, help="Optional Kubernetes label selector."
    )
    parser.add_argument(
        "--auth-mode",
        choices=("auto", "kubeconfig", "in-cluster"),
        default="auto",
        help="How to configure Kubernetes client authentication.",
    )
    parser.add_argument("--kubeconfig", default=None, help="Optional kubeconfig path.")
    parser.add_argument("--context", default=None, help="Optional kubeconfig context.")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write the generated .env content.",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="WARNING",
        help="Python logging level.",
    )
    return parser


def _emit_output(rendered: str, output_path: str | None) -> None:
    if output_path is None:
        print(rendered, end="")
        return

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
