from __future__ import annotations

import yaml

from pvc_migrator.models import MigrationPlan


def render_plan(plan: MigrationPlan, output_format: str) -> str:
    if output_format == "json":
        return plan.model_dump_json(indent=2)
    if output_format == "yaml":
        return str(yaml.safe_dump(plan.model_dump(mode="python"), sort_keys=False))
    return _render_table(plan)


def _render_table(plan: MigrationPlan) -> str:
    lines = [
        f"Run ID: {plan.run_id}",
        f"Source: {plan.source_cluster.namespace} ({plan.source_cluster.context or 'current'})",
        f"Destination: {plan.destination_cluster.namespace} ({plan.destination_cluster.context or 'current'})",
        f"Executable: {'yes' if plan.executable else 'no'}",
        "",
    ]
    if plan.preflight_checks:
        lines.append("Preflight:")
        for check in plan.preflight_checks:
            lines.append(f"  {check.status}: {check.name}: {check.detail}")
        lines.append("")
    for workload in plan.workload_plans:
        lines.append(f"[{workload.workload_name}] {workload.engine}")
        if workload.pvc_pairs:
            for pair in workload.pvc_pairs:
                lines.append(f"  PVC {pair.source_name} -> {pair.destination_name}")
        for warning in workload.warnings:
            lines.append(f"  warning: {warning}")
        for blocker in workload.blockers:
            lines.append(f"  blocker: {blocker}")
        for command in workload.commands:
            lines.append(f"  cmd: {command.command}")
        lines.append("")
    if plan.warnings:
        lines.append("Plan warnings:")
        for warning in plan.warnings:
            lines.append(f"  - {warning}")
    if plan.blockers:
        lines.append("Plan blockers:")
        for blocker in plan.blockers:
            lines.append(f"  - {blocker}")
    return "\n".join(lines).rstrip() + "\n"
