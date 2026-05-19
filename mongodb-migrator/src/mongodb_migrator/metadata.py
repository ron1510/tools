from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mongodb_migrator.connectors import CollectionHandle, DatabaseHandle
from mongodb_migrator.models import CollectionMetadata, CollectionOptions, IndexDefinition


def extract_metadata(collection: CollectionHandle) -> CollectionMetadata:
    raw_options = _extract_collection_options(collection)
    options = CollectionOptions(
        validator=_mapping_or_none(raw_options.get("validator")),
        validation_level=_string_or_none(raw_options.get("validationLevel")),
        validation_action=_string_or_none(raw_options.get("validationAction")),
        timeseries=_mapping_or_none(raw_options.get("timeseries")),
        expire_after_seconds=_int_or_none(raw_options.get("expireAfterSeconds")),
    )

    indexes: list[IndexDefinition] = []
    for name, info in collection.index_information().items():
        if name == "_id_":
            continue
        keys = tuple((field, direction) for field, direction in info.get("key", []))
        indexes.append(
            IndexDefinition(
                name=name,
                keys=keys,
                unique=bool(info.get("unique", False)),
                sparse=bool(info.get("sparse", False)),
                expire_after_seconds=_int_or_none(info.get("expireAfterSeconds")),
                partial_filter_expression=_mapping_or_none(
                    info.get("partialFilterExpression")
                ),
            )
        )
    return CollectionMetadata(options=options, indexes=tuple(indexes))


def ensure_collection(
    database: DatabaseHandle,
    collection_name: str,
    metadata: CollectionMetadata,
) -> CollectionHandle:
    names = set(database.list_collection_names())
    if collection_name in names:
        return database[collection_name]

    create_kwargs: dict[str, Any] = {}
    if metadata.options.validator is not None:
        create_kwargs["validator"] = dict(metadata.options.validator)
    if metadata.options.validation_level is not None:
        create_kwargs["validationLevel"] = metadata.options.validation_level
    if metadata.options.validation_action is not None:
        create_kwargs["validationAction"] = metadata.options.validation_action
    if metadata.options.timeseries is not None:
        create_kwargs["timeseries"] = dict(metadata.options.timeseries)
    if metadata.options.expire_after_seconds is not None:
        create_kwargs["expireAfterSeconds"] = metadata.options.expire_after_seconds
    return database.create_collection(collection_name, **create_kwargs)


def recreate_indexes(collection: CollectionHandle, metadata: CollectionMetadata) -> int:
    if not metadata.indexes:
        return 0
    try:
        from pymongo import IndexModel
    except ImportError:  # pragma: no cover - runtime integration only
        return len(metadata.indexes)

    models: list[IndexModel] = []
    for index in metadata.indexes:
        kwargs: dict[str, Any] = {"name": index.name}
        if index.unique:
            kwargs["unique"] = True
        if index.sparse:
            kwargs["sparse"] = True
        if index.expire_after_seconds is not None:
            kwargs["expireAfterSeconds"] = index.expire_after_seconds
        if index.partial_filter_expression is not None:
            kwargs["partialFilterExpression"] = dict(index.partial_filter_expression)
        models.append(IndexModel(list(index.keys), **kwargs))
    collection.create_indexes(models)
    return len(models)


def _mapping_or_none(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    return None


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _extract_collection_options(collection: CollectionHandle) -> dict[str, Any]:
    if hasattr(collection, "options"):
        options_method = getattr(collection, "options")
        if callable(options_method):
            raw_options = options_method()
            if isinstance(raw_options, dict):
                return raw_options

    database = getattr(collection, "database", None)
    if database is None or not hasattr(database, "list_collections"):
        return {}
    list_collections = getattr(database, "list_collections")
    if not callable(list_collections):
        return {}
    cursor = list_collections(filter={"name": collection.name})
    documents = list(cursor)
    if not documents:
        return {}
    raw_options = documents[0].get("options", {})
    return raw_options if isinstance(raw_options, dict) else {}
