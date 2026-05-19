from __future__ import annotations

from typing import Any

import pytest

from mongodb_migrator.copy_service import MongoCopyService
from mongodb_migrator.models import CopyRequest, ExecutionOptions, MongoEndpointConfig, VerificationOptions


@pytest.mark.integration
@pytest.mark.real_mongo
def test_copy_service_copies_documents_indexes_and_validator_with_real_mongo(
    real_mongo_endpoints: tuple[str, str],
) -> None:
    from pymongo import ASCENDING, MongoClient

    source_uri, target_uri = real_mongo_endpoints
    source_client: Any = MongoClient(source_uri)
    target_client: Any = MongoClient(target_uri)

    source_db = source_client["app_source"]
    target_db = target_client["app_target"]
    source_db.drop_collection("users")
    target_db.drop_collection("users")

    source_db.create_collection(
        "users",
        validator={"name": {"$type": "string"}},
        validationLevel="strict",
        validationAction="error",
    )
    source_db["users"].create_index([("email", ASCENDING)], name="email_1", unique=True)
    source_db["users"].insert_many(
        [
            {"_id": 1, "name": "Ada", "email": "ada@example.test"},
            {"_id": 2, "name": "Grace", "email": "grace@example.test"},
        ]
    )

    service = MongoCopyService()
    report = service.copy(
        CopyRequest(
            source=MongoEndpointConfig(uri=source_uri, database="app_source"),
            target=MongoEndpointConfig(uri=target_uri, database="app_target"),
            execution=ExecutionOptions(replace_target=True, batch_size=1),
            verification=VerificationOptions(enabled=True, sample_size=2),
        )
    )

    target_docs = list(target_db["users"].find(sort=[("_id", 1)]))
    assert [doc["name"] for doc in target_docs] == ["Ada", "Grace"]
    assert report.results[0].copied_documents == 2
    assert report.verification is not None
    assert report.verification.success is True

    target_collection_info = list(target_db.list_collections(filter={"name": "users"}))[0]
    assert target_collection_info["options"]["validator"] == {"name": {"$type": "string"}}
    target_indexes = target_db["users"].index_information()
    assert "email_1" in target_indexes
    assert target_indexes["email_1"]["unique"] is True

    source_client.close()
    target_client.close()
