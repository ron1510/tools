from __future__ import annotations

import pytest

from pvc_migrator.errors import PlanValidationError
from pvc_migrator.mapping import build_pvc_pairs, pair_workloads
from pvc_migrator.models import LiveClusterState, PersistentVolumeClaimInfo, WorkloadInfo, WorkloadPair


def make_workload(name: str, *, category: str = "generic", pvcs: tuple[str, ...] = ()) -> WorkloadInfo:
    return WorkloadInfo(
        name=name,
        kind="StatefulSet",
        category=category,  # type: ignore[arg-type]
        replicas=len(pvcs) or 1,
        expected_pvc_names=pvcs,
    )


def test_pair_workloads_matches_normalized_names() -> None:
    pairs = pair_workloads(
        (make_workload("source-app-db"),),
        (make_workload("dest-app-db"),),
    )
    assert pairs[0].destination.name == "dest-app-db"


def test_pair_workloads_rejects_ambiguous_matches() -> None:
    with pytest.raises(PlanValidationError, match="ambiguous"):
        pair_workloads(
            (make_workload("source-app-db"),),
            (make_workload("dest-app-db"), make_workload("dst-app-db")),
        )


def test_build_pvc_pairs_rejects_mismatched_counts() -> None:
    pair = WorkloadPair(
        source=make_workload("src-db", pvcs=("data-src-db-0", "data-src-db-1")),
        destination=make_workload("dst-db", pvcs=("data-dst-db-0",)),
    )
    with pytest.raises(PlanValidationError, match="different PVC counts"):
        build_pvc_pairs(pair, LiveClusterState(), LiveClusterState())


def test_build_pvc_pairs_maps_live_namespaces() -> None:
    pair = WorkloadPair(
        source=make_workload("src-db", pvcs=("data-src-db-0",)),
        destination=make_workload("dst-db", pvcs=("data-dst-db-0",)),
    )
    source_live = LiveClusterState(
        pvcs=(PersistentVolumeClaimInfo(name="data-src-db-0", namespace="src"),)
    )
    destination_live = LiveClusterState(
        pvcs=(PersistentVolumeClaimInfo(name="data-dst-db-0", namespace="dst"),)
    )
    pvc_pairs = build_pvc_pairs(pair, source_live, destination_live)
    assert pvc_pairs[0].source_namespace == "src"
    assert pvc_pairs[0].destination_namespace == "dst"
