from __future__ import annotations

from mongodb_migrator.copy_service import MongoCopyService
from mongodb_migrator.models import CopyRequest, ExecutionOptions, MongoEndpointConfig, VerificationOptions
from tests.factories import FakeCollection, FakeConnector, FakeDatabase


def test_copy_service_copies_multiple_collections_across_fake_databases() -> None:
    source_db = FakeDatabase(
        "source",
        {
            "users": FakeCollection(
                "users",
                documents=[{"_id": 1, "name": "Ada"}, {"_id": 2, "name": "Grace"}],
                indexes={"_id_": {"key": [("_id", 1)]}, "name_1": {"key": [("name", 1)]}},
            ),
            "orders": FakeCollection(
                "orders",
                documents=[{"_id": 11, "total": 99}, {"_id": 12, "total": 120}],
            ),
        },
    )
    target_db = FakeDatabase("target", {})
    service = MongoCopyService(
        connector=FakeConnector(
            {
                ("mongodb://src", "source"): source_db,
                ("mongodb://dst", "target"): target_db,
            }
        )
    )

    report = service.copy(
        CopyRequest(
            source=MongoEndpointConfig(uri="mongodb://src", database="source"),
            target=MongoEndpointConfig(uri="mongodb://dst", database="target"),
            execution=ExecutionOptions(batch_size=1),
            verification=VerificationOptions(enabled=True, sample_size=1),
        )
    )

    assert [item.target_collection for item in report.results] == ["orders", "users"]
    assert target_db["users"].count_documents({}) == 2
    assert target_db["orders"].count_documents({}) == 2
    assert report.verification is not None
    assert report.verification.success is True
