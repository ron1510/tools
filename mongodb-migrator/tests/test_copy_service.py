from __future__ import annotations

import pytest

from mongodb_migrator.copy_service import MongoCopyService
from mongodb_migrator.errors import ConfigurationError, CopySafetyError
from mongodb_migrator.models import CopyRequest, ExecutionOptions, MongoEndpointConfig, VerificationOptions
from tests.factories import FakeCollection, FakeConnector, FakeDatabase


def test_copy_service_copies_documents_and_verifies() -> None:
    source_collection = FakeCollection(
        "users",
        documents=[{"_id": 1, "name": "Ada"}, {"_id": 2, "name": "Grace"}],
        options={"validator": {"name": {"$exists": True}}},
        indexes={"_id_": {"key": [("_id", 1)]}, "name_1": {"key": [("name", 1)]}},
    )
    source_db = FakeDatabase("source", {"users": source_collection})
    target_db = FakeDatabase("target", {})
    connector = FakeConnector(
        {
            ("mongodb://src", "source"): source_db,
            ("mongodb://dst", "target"): target_db,
        }
    )
    service = MongoCopyService(connector=connector)

    request = CopyRequest(
        source=MongoEndpointConfig(uri="mongodb://src", database="source"),
        target=MongoEndpointConfig(uri="mongodb://dst", database="target"),
        execution=ExecutionOptions(),
        verification=VerificationOptions(enabled=True, sample_size=2),
    )

    report = service.copy(request)

    assert report.results[0].copied_documents == 2
    assert "users" in target_db.list_collection_names()
    assert target_db["users"].count_documents({}) == 2
    assert report.verification is not None
    assert report.verification.success is True


def test_copy_service_refuses_non_empty_target_without_replace() -> None:
    source_db = FakeDatabase("source", {"users": FakeCollection("users", documents=[{"_id": 1}])})
    target_db = FakeDatabase("target", {"users": FakeCollection("users", documents=[{"_id": 9}])})
    connector = FakeConnector(
        {
            ("mongodb://src", "source"): source_db,
            ("mongodb://dst", "target"): target_db,
        }
    )
    service = MongoCopyService(connector=connector)
    request = CopyRequest(
        source=MongoEndpointConfig(uri="mongodb://src", database="source"),
        target=MongoEndpointConfig(uri="mongodb://dst", database="target"),
    )

    with pytest.raises(CopySafetyError):
        service.copy(request)


def test_copy_service_replaces_target_when_enabled() -> None:
    source_db = FakeDatabase("source", {"users": FakeCollection("users", documents=[{"_id": 1}])})
    target_collection = FakeCollection("users", documents=[{"_id": 9}])
    target_db = FakeDatabase("target", {"users": target_collection})
    connector = FakeConnector(
        {
            ("mongodb://src", "source"): source_db,
            ("mongodb://dst", "target"): target_db,
        }
    )
    service = MongoCopyService(connector=connector)
    request = CopyRequest(
        source=MongoEndpointConfig(uri="mongodb://src", database="source"),
        target=MongoEndpointConfig(uri="mongodb://dst", database="target"),
        execution=ExecutionOptions(replace_target=True),
    )

    report = service.copy(request)

    assert report.verification is None
    assert target_collection.dropped is True
    assert report.results[0].copied_documents == 1


def test_copy_service_rejects_verify_with_dry_run() -> None:
    source_db = FakeDatabase("source", {"users": FakeCollection("users", documents=[{"_id": 1}])})
    target_db = FakeDatabase("target", {"users": FakeCollection("users", documents=[{"_id": 2}])})
    connector = FakeConnector(
        {
            ("mongodb://src", "source"): source_db,
            ("mongodb://dst", "target"): target_db,
        }
    )
    service = MongoCopyService(connector=connector)
    request = CopyRequest(
        source=MongoEndpointConfig(uri="mongodb://src", database="source"),
        target=MongoEndpointConfig(uri="mongodb://dst", database="target"),
        include_collections=("users",),
        execution=ExecutionOptions(dry_run=True, replace_target=True),
        verification=VerificationOptions(enabled=True, sample_size=1),
    )

    with pytest.raises(ConfigurationError):
        service.copy(request)
