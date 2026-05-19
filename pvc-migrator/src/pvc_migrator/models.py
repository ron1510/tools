from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

EngineName = Literal[
    "pv-migrate",
    "victoriametrics-vmstorage",
    "victoriametrics-aux-skip",
    "arangodb-native",
    "grafana-plugins",
]
CommandStatus = Literal["pending", "completed", "failed", "skipped"]
WorkloadKind = Literal["StatefulSet", "Deployment", "PVC", "VMCluster", "Unknown"]
WorkloadCategory = Literal[
    "generic",
    "victoriametrics-vmstorage",
    "victoriametrics-aux",
    "arangodb-single",
    "grafana",
]
OutputFormat = Literal["table", "json", "yaml"]


class ClusterRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    namespace: str
    context: str | None = None

    @model_validator(mode="after")
    def validate_namespace(self) -> "ClusterRef":
        if not self.namespace.strip():
            raise ValueError("namespace must not be empty")
        return self


class ChartInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    chart: str
    values_file: str | None = None
    release_name: str | None = None

    @model_validator(mode="after")
    def validate_chart(self) -> "ChartInput":
        if not self.chart.strip():
            raise ValueError("chart must not be empty")
        return self


class PlanRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: ChartInput
    destination: ChartInput
    source_cluster: ClusterRef
    destination_cluster: ClusterRef
    extra_pvc_selector: str | None = None
    include_workloads: tuple[str, ...] = ()
    exclude_workloads: tuple[str, ...] = ()
    output_format: OutputFormat = "table"
    engine_override: str | None = None
    allow_aux_pvc_copy: bool = False
    mapping_file: str | None = None

    @model_validator(mode="after")
    def validate_filters(self) -> "PlanRequest":
        overlap = set(self.include_workloads).intersection(self.exclude_workloads)
        if overlap:
            names = ", ".join(sorted(overlap))
            raise ValueError(f"workloads cannot be both included and excluded: {names}")
        return self


class Metadata(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    name: str = "<unknown>"
    namespace: str | None = None
    labels: Mapping[str, str] = Field(default_factory=dict)
    annotations: Mapping[str, str] = Field(default_factory=dict)


class RenderedResource(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    apiVersion: str | None = None
    kind: str
    metadata: Metadata = Field(default_factory=Metadata)
    spec: Mapping[str, Any] = Field(default_factory=dict)


class PersistentVolumeClaimInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    namespace: str
    storage_class_name: str | None = None
    access_modes: tuple[str, ...] = ()
    labels: Mapping[str, str] = Field(default_factory=dict)
    annotations: Mapping[str, str] = Field(default_factory=dict)


class WorkloadInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    kind: WorkloadKind
    category: WorkloadCategory
    replicas: int = 1
    claim_templates: tuple[str, ...] = ()
    expected_pvc_names: tuple[str, ...] = ()
    plugin_declarations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class WorkloadPair(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: WorkloadInfo
    destination: WorkloadInfo


class PvcPair(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_name: str
    destination_name: str
    source_namespace: str
    destination_namespace: str


class MigrationCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    description: str
    command: str


class WorkloadPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    workload_name: str
    destination_workload_name: str | None = None
    category: WorkloadCategory
    engine: EngineName
    pvc_pairs: tuple[PvcPair, ...] = ()
    commands: tuple[MigrationCommand, ...] = ()
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @property
    def executable(self) -> bool:
        return not self.blockers and bool(self.commands)


class MigrationPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    source_cluster: ClusterRef
    destination_cluster: ClusterRef
    workload_plans: tuple[WorkloadPlan, ...]
    preflight_checks: tuple["PreflightCheck", ...] = ()
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @property
    def executable(self) -> bool:
        return (
            bool(self.workload_plans)
            and not self.blockers
            and all(not wp.blockers for wp in self.workload_plans)
        )


class LiveClusterState(BaseModel):
    model_config = ConfigDict(frozen=True)

    pvcs: tuple[PersistentVolumeClaimInfo, ...] = ()


class ExecuteResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    commands_run: tuple[str, ...]
    skipped_workloads: tuple[str, ...] = ()


class PreflightCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["ok", "warning", "blocked"]
    detail: str


class WorkloadMappingRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_workload: str
    destination_workload: str


class PvcMappingRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_pvc: str
    destination_pvc: str


class MappingOverrides(BaseModel):
    model_config = ConfigDict(frozen=True)

    workloads: tuple[WorkloadMappingRule, ...] = ()
    pvcs: tuple[PvcMappingRule, ...] = ()


class CommandExecutionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    workload_name: str
    command: str
    description: str
    status: CommandStatus
    error: str | None = None


class RunLog(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    plan_summary: str
    records: tuple[CommandExecutionRecord, ...] = ()


class ValuesSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    plugins: tuple[str, ...] = ()


def parse_rendered_resources(documents: list[dict[str, Any]]) -> tuple[RenderedResource, ...]:
    resources: list[RenderedResource] = []
    for document in documents:
        if not document:
            continue
        resources.append(RenderedResource.model_validate(document))
    return tuple(resources)


def as_workload_kind(kind: str) -> WorkloadKind:
    allowed = {"StatefulSet", "Deployment", "PVC", "VMCluster", "Unknown"}
    normalized = kind if kind in allowed else "Unknown"
    return cast(WorkloadKind, normalized)


def as_engine_name(name: str) -> EngineName:
    allowed = {
        "pv-migrate",
        "victoriametrics-vmstorage",
        "victoriametrics-aux-skip",
        "arangodb-native",
        "grafana-plugins",
    }
    if name not in allowed:
        raise ValueError(f"unsupported engine: {name}")
    return cast(EngineName, name)
