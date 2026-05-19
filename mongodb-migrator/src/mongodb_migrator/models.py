from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator


class MongoEndpointConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    uri: str
    database: str

    @model_validator(mode="after")
    def validate_fields(self) -> "MongoEndpointConfig":
        if not self.uri.strip():
            raise ValueError("uri must not be empty")
        if not self.database.strip():
            raise ValueError("database must not be empty")
        return self


class ExecutionOptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_size: PositiveInt = 1000
    checkpoint_path: str | None = None
    dry_run: bool = False
    replace_target: bool = False


class VerificationOptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    sample_size: int = 25
    sample_seed: int = 17

    @model_validator(mode="after")
    def validate_sample_size(self) -> "VerificationOptions":
        if self.sample_size < 0:
            raise ValueError("sample_size must be greater than or equal to zero")
        return self


class CollectionPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_collection: str
    target_collection: str
    filter_query: Mapping[str, Any] = Field(default_factory=dict)
    projection: tuple[str, ...] | None = None
    transform: str | None = None


class CopyRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: MongoEndpointConfig
    target: MongoEndpointConfig
    include_collections: tuple[str, ...] = ()
    exclude_collections: tuple[str, ...] = ()
    execution: ExecutionOptions = Field(default_factory=ExecutionOptions)
    verification: VerificationOptions = Field(default_factory=VerificationOptions)

    @model_validator(mode="after")
    def validate_filters(self) -> "CopyRequest":
        overlap = set(self.include_collections).intersection(self.exclude_collections)
        if overlap:
            names = ", ".join(sorted(overlap))
            raise ValueError(f"collections cannot be both included and excluded: {names}")
        return self


class SelectionOptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    include_collections: tuple[str, ...] = ()
    exclude_collections: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_filters(self) -> "SelectionOptions":
        overlap = set(self.include_collections).intersection(self.exclude_collections)
        if overlap:
            names = ", ".join(sorted(overlap))
            raise ValueError(f"collections cannot be both included and excluded: {names}")
        return self


class MigrationJob(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: MongoEndpointConfig
    target: MongoEndpointConfig
    selection: SelectionOptions = Field(default_factory=SelectionOptions)
    execution: ExecutionOptions = Field(default_factory=ExecutionOptions)
    verification: VerificationOptions = Field(default_factory=VerificationOptions)
    collections: tuple[CollectionPlan, ...] = ()


class CollectionOptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    validator: Mapping[str, Any] | None = None
    validation_level: str | None = None
    validation_action: str | None = None
    timeseries: Mapping[str, Any] | None = None
    expire_after_seconds: int | None = None


class IndexDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    keys: tuple[tuple[str, int], ...]
    unique: bool = False
    sparse: bool = False
    expire_after_seconds: int | None = None
    partial_filter_expression: Mapping[str, Any] | None = None


class CollectionMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    options: CollectionOptions = Field(default_factory=CollectionOptions)
    indexes: tuple[IndexDefinition, ...] = ()


class CollectionCheckpoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    copied_documents: int = 0
    completed: bool = False


class CheckpointState(BaseModel):
    model_config = ConfigDict(frozen=True)

    collections: dict[str, CollectionCheckpoint] = Field(default_factory=dict)


class CopyRunReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    results: tuple["CollectionCopyResult", ...]
    verification: "VerificationReport | None" = None


class CollectionCopyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_collection: str
    target_collection: str
    copied_documents: int
    recreated_indexes: int
    skipped: bool = False


class VerificationCollectionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    collection: str
    source_count: int
    target_count: int
    hashes_match: bool


class VerificationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    collections: tuple[VerificationCollectionResult, ...]

    @property
    def success(self) -> bool:
        return all(
            item.source_count == item.target_count and item.hashes_match
            for item in self.collections
        )


class CommandOutputFormat(BaseModel):
    model_config = ConfigDict(frozen=True)

    format: Literal["text", "json"] = "text"
