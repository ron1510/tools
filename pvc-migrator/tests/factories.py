from __future__ import annotations


def make_statefulset(
    name: str,
    claim_name: str,
    *,
    replicas: int = 1,
    image: str = "busybox:1.0",
    labels: dict[str, str] | None = None,
) -> dict:
    return {
        "apiVersion": "apps/v1",
        "kind": "StatefulSet",
        "metadata": {"name": name, "labels": labels or {}},
        "spec": {
            "replicas": replicas,
            "template": {
                "spec": {
                    "containers": [
                        {"name": name, "image": image},
                    ]
                }
            },
            "volumeClaimTemplates": [
                {
                    "metadata": {"name": claim_name},
                    "spec": {"accessModes": ["ReadWriteOnce"]},
                }
            ],
        },
    }


def make_deployment(name: str, *, image: str = "busybox:1.0") -> dict:
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name},
        "spec": {
            "replicas": 1,
            "template": {
                "spec": {
                    "containers": [{"name": name, "image": image}],
                }
            },
        },
    }


def make_pvc(name: str, namespace: str) -> dict:
    return {
        "metadata": {"name": name, "namespace": namespace},
        "spec": {"accessModes": ["ReadWriteOnce"], "storageClassName": "fast"},
    }


def make_vmcluster(name: str) -> dict:
    return {
        "apiVersion": "operator.victoriametrics.com/v1beta1",
        "kind": "VMCluster",
        "metadata": {"name": name},
        "spec": {"replicas": 1},
    }
