from __future__ import annotations

from pvc_migrator.errors import PlanValidationError
from pvc_migrator.models import (
    LiveClusterState,
    MappingOverrides,
    PvcPair,
    WorkloadInfo,
    WorkloadPair,
)


def pair_workloads(
    source_workloads: tuple[WorkloadInfo, ...],
    destination_workloads: tuple[WorkloadInfo, ...],
    overrides: MappingOverrides | None = None,
) -> tuple[WorkloadPair, ...]:
    pairs: list[WorkloadPair] = []
    remaining_destination = list(destination_workloads)
    override_map = {
        rule.source_workload: rule.destination_workload for rule in (overrides.workloads if overrides else ())
    }
    for source in source_workloads:
        match = _find_destination(source, remaining_destination, override_map)
        if match is None:
            raise PlanValidationError(f"no destination workload matches source workload {source.name}")
        remaining_destination.remove(match)
        pairs.append(WorkloadPair(source=source, destination=match))
    return tuple(pairs)


def build_pvc_pairs(
    pair: WorkloadPair,
    source_live: LiveClusterState,
    destination_live: LiveClusterState,
    overrides: MappingOverrides | None = None,
) -> tuple[PvcPair, ...]:
    if not pair.source.expected_pvc_names:
        return ()
    if len(pair.source.expected_pvc_names) != len(pair.destination.expected_pvc_names):
        raise PlanValidationError(
            "source and destination StatefulSets produce different PVC counts"
        )
    destination_names = {pvc.name for pvc in destination_live.pvcs}
    source_names = {pvc.name for pvc in source_live.pvcs}
    override_map = {
        rule.source_pvc: rule.destination_pvc for rule in (overrides.pvcs if overrides else ())
    }
    pvc_pairs: list[PvcPair] = []
    for source_name, destination_name in zip(
        pair.source.expected_pvc_names, pair.destination.expected_pvc_names, strict=True
    ):
        destination_name = override_map.get(source_name, destination_name)
        if source_name not in source_names:
            raise PlanValidationError(f"source PVC not found: {source_name}")
        if destination_name not in destination_names:
            raise PlanValidationError(f"destination PVC not found: {destination_name}")
        pvc_pairs.append(
            PvcPair(
                source_name=source_name,
                destination_name=destination_name,
                source_namespace=next(pvc.namespace for pvc in source_live.pvcs if pvc.name == source_name),
                destination_namespace=next(
                    pvc.namespace for pvc in destination_live.pvcs if pvc.name == destination_name
                ),
            )
        )
    return tuple(pvc_pairs)


def _find_destination(
    source: WorkloadInfo,
    destination_workloads: list[WorkloadInfo],
    override_map: dict[str, str],
) -> WorkloadInfo | None:
    forced_name = override_map.get(source.name)
    if forced_name is not None:
        forced_candidates = [workload for workload in destination_workloads if workload.name == forced_name]
        if len(forced_candidates) != 1:
            raise PlanValidationError(
                f"mapping override for workload {source.name} points to missing or ambiguous destination {forced_name}"
            )
        return forced_candidates[0]
    normalized_source = _normalize_name(source.name)
    candidates = [
        workload
        for workload in destination_workloads
        if workload.category == source.category and _normalize_name(workload.name) == normalized_source
    ]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise PlanValidationError(f"ambiguous destination mapping for workload {source.name}")
    return None


def _normalize_name(name: str) -> str:
    tokens = [
        token
        for token in name.lower().split("-")
        if token not in {"src", "dst", "source", "dest", "release", "prod", "dev", "staging"}
    ]
    return "-".join(tokens[-2:] if len(tokens) >= 2 else tokens)
