from __future__ import annotations

from copy import deepcopy
from typing import Any

from review_env_exporter import (
    ANNOTATION_ENV_NAME,
    ANNOTATION_EXPORT_TYPE,
    ANNOTATION_PATH,
    ANNOTATION_PORT_NAME,
    ANNOTATION_PUBLIC_HOST,
    EXPORT_LABEL,
)


def make_route(
    *,
    name: str,
    env_name: str | None,
    host: str,
    path: str | None = None,
    tls: bool = True,
    exportable: bool = True,
    scheme: str | None = None,
) -> dict[str, Any]:
    annotations: dict[str, str] = {}
    if env_name is not None:
        annotations[ANNOTATION_ENV_NAME] = env_name
    annotations[ANNOTATION_EXPORT_TYPE] = "route-url"
    if path is not None:
        annotations[ANNOTATION_PATH] = path
    if scheme is not None:
        annotations["review.my-company.io/scheme"] = scheme

    resource: dict[str, Any] = {
        "apiVersion": "route.openshift.io/v1",
        "kind": "Route",
        "metadata": {
            "name": name,
            "namespace": "review",
            "labels": {EXPORT_LABEL: "true"} if exportable else {},
            "annotations": annotations,
        },
        "spec": {
            "host": host,
        },
    }
    if tls:
        resource["spec"]["tls"] = {"termination": "edge"}
    return resource


def make_nodeport_service(
    *,
    name: str,
    env_name: str | None,
    public_host: str | None,
    ports: list[dict[str, Any]],
    exportable: bool = True,
    service_type: str = "NodePort",
    port_name: str | None = None,
) -> dict[str, Any]:
    annotations: dict[str, str] = {}
    if env_name is not None:
        annotations[ANNOTATION_ENV_NAME] = env_name
    annotations[ANNOTATION_EXPORT_TYPE] = "nodeport-hostport"
    if public_host is not None:
        annotations[ANNOTATION_PUBLIC_HOST] = public_host
    if port_name is not None:
        annotations[ANNOTATION_PORT_NAME] = port_name

    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "namespace": "review",
            "labels": {EXPORT_LABEL: "true"} if exportable else {},
            "annotations": annotations,
        },
        "spec": {
            "type": service_type,
            "ports": deepcopy(ports),
        },
    }


def make_internal_service(*, name: str = "internal-api") -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "namespace": "review",
            "labels": {},
            "annotations": {},
        },
        "spec": {
            "type": "ClusterIP",
            "ports": [
                {"name": "http", "port": 8080, "targetPort": 8080},
            ],
        },
    }


def make_happy_path_resources() -> list[dict[str, Any]]:
    return [
        make_route(
            name="api",
            env_name="API_URL",
            host="acme-feature-x.apps.cluster.example.com",
            path="/api",
        ),
        make_route(
            name="ui",
            env_name="UI_URL",
            host="acme-feature-x.apps.cluster.example.com",
        ),
        make_nodeport_service(
            name="kafka-external",
            env_name="KAFKA_BOOTSTRAP_SERVERS",
            public_host="nodeport-gw.review.example.com",
            ports=[
                {
                    "name": "tcp-kafka",
                    "port": 9092,
                    "targetPort": 9092,
                    "nodePort": 32110,
                }
            ],
        ),
        make_nodeport_service(
            name="mongodb-external",
            env_name="MONGODB_HOSTPORT",
            public_host="nodeport-gw.review.example.com",
            ports=[
                {
                    "name": "mongodb",
                    "port": 27017,
                    "targetPort": 27017,
                    "nodePort": 32217,
                }
            ],
        ),
        make_internal_service(),
    ]
