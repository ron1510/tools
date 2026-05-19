from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable
from typing import Any

from pvc_migrator.errors import ClusterInspectionError
from pvc_migrator.models import (
    ChartInput,
    ClusterRef,
    LiveClusterState,
    PersistentVolumeClaimInfo,
    RenderedResource,
    ValuesSummary,
    WorkloadCategory,
    WorkloadInfo,
    as_workload_kind,
    parse_rendered_resources,
)


class ClusterInspector:
    def list_pvcs(self, cluster: ClusterRef, selector: str | None = None) -> LiveClusterState:
        command = ["kubectl"]
        if cluster.context:
            command.extend(["--context", cluster.context])
        command.extend(["-n", cluster.namespace, "get", "pvc", "-o", "json"])
        if selector:
            command.extend(["-l", selector])
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise ClusterInspectionError(f"kubectl get pvc failed: {exc}") from exc
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ClusterInspectionError(f"kubectl returned invalid JSON: {exc}") from exc
        items = payload.get("items", [])
        pvcs = tuple(_parse_pvc(item, cluster.namespace) for item in items if isinstance(item, dict))
        return LiveClusterState(pvcs=pvcs)


def discover_workloads(
    resources: tuple[RenderedResource, ...],
    values_summary: ValuesSummary,
    chart_input: ChartInput,
) -> tuple[WorkloadInfo, ...]:
    workloads: list[WorkloadInfo] = []
    grafana_workload_found = False
    for resource in resources:
        if resource.kind not in {"StatefulSet", "Deployment", "VMCluster"}:
            continue
        category = classify_workload(resource)
        if category == "grafana":
            grafana_workload_found = True
        replicas = int(resource.spec.get("replicas", 1))
        templates = _extract_claim_templates(resource) if resource.kind == "StatefulSet" else ()
        expected = (
            build_expected_pvc_names(resource.metadata.name, replicas, templates)
            if templates
            else ()
        )
        plugins = values_summary.plugins if category == "grafana" else ()
        notes: list[str] = []
        if category == "grafana" and plugins:
            notes.append("Grafana plugins are declared in values and can be rehydrated declaratively.")
        workloads.append(
            WorkloadInfo(
                name=resource.metadata.name,
                kind=as_workload_kind(resource.kind),
                category=category,
                replicas=replicas,
                claim_templates=templates,
                expected_pvc_names=expected,
                plugin_declarations=plugins,
                notes=tuple(notes),
            )
        )
    if not grafana_workload_found and values_summary.plugins:
        workloads.append(
            WorkloadInfo(
                name=chart_input.release_name or "grafana",
                kind="Unknown",
                category="grafana",
                plugin_declarations=values_summary.plugins,
                notes=("Grafana plugins were found in values even though no workload was detected.",),
            )
        )
    return tuple(workloads)


def classify_workload(resource: RenderedResource) -> WorkloadCategory:
    name_blob = " ".join(
        filter(
            None,
            [
                resource.metadata.name,
                resource.metadata.labels.get("app.kubernetes.io/name"),
                resource.metadata.labels.get("app.kubernetes.io/component"),
                _collect_container_names(resource),
                _collect_container_images(resource),
            ],
        )
    ).lower()
    if "vmstorage" in name_blob or _is_vmcluster_resource(resource):
        return "victoriametrics-vmstorage"
    if "vmagent" in name_blob or "vmalert" in name_blob:
        return "victoriametrics-aux"
    if "arangodb" in name_blob:
        return "arangodb-single"
    if "grafana" in name_blob:
        return "grafana"
    return "generic"


def build_expected_pvc_names(
    workload_name: str,
    replicas: int,
    claim_templates: Iterable[str],
) -> tuple[str, ...]:
    expected: list[str] = []
    for claim in claim_templates:
        for ordinal in range(replicas):
            expected.append(f"{claim}-{workload_name}-{ordinal}")
    return tuple(expected)


def _extract_claim_templates(resource: RenderedResource) -> tuple[str, ...]:
    raw_templates = resource.spec.get("volumeClaimTemplates", [])
    templates: list[str] = []
    if not isinstance(raw_templates, list):
        return ()
    for item in raw_templates:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata", {})
        if isinstance(metadata, dict):
            name = metadata.get("name")
            if isinstance(name, str):
                templates.append(name)
    return tuple(templates)


def _collect_container_names(resource: RenderedResource) -> str:
    return " ".join(_collect_template_values(resource, "name"))


def _collect_container_images(resource: RenderedResource) -> str:
    return " ".join(_collect_template_values(resource, "image"))


def _collect_template_values(resource: RenderedResource, field: str) -> tuple[str, ...]:
    template = resource.spec.get("template", {})
    if not isinstance(template, dict):
        return ()
    template_spec = template.get("spec", {})
    if not isinstance(template_spec, dict):
        return ()
    containers = template_spec.get("containers", [])
    values: list[str] = []
    if not isinstance(containers, list):
        return ()
    for container in containers:
        if isinstance(container, dict) and isinstance(container.get(field), str):
            values.append(container[field])
    return tuple(values)


def _parse_pvc(item: dict[str, Any], namespace: str) -> PersistentVolumeClaimInfo:
    metadata = item.get("metadata", {})
    spec = item.get("spec", {})
    return PersistentVolumeClaimInfo(
        name=str(metadata.get("name", "<unknown>")),
        namespace=str(metadata.get("namespace", namespace)),
        storage_class_name=spec.get("storageClassName"),
        access_modes=tuple(str(mode) for mode in spec.get("accessModes", [])),
        labels=metadata.get("labels", {}) if isinstance(metadata.get("labels"), dict) else {},
        annotations=metadata.get("annotations", {}) if isinstance(metadata.get("annotations"), dict) else {},
    )


def _is_vmcluster_resource(resource: RenderedResource) -> bool:
    return resource.kind == "VMCluster" or (
        resource.apiVersion is not None and "victoriametrics.com/" in resource.apiVersion
    )
