from __future__ import annotations

from typing import Any

from mongodb_migrator.models import MongoEndpointConfig


class FakeCollection:
    def __init__(
        self,
        name: str,
        documents: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
        indexes: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.name = name
        self._documents = list(documents or [])
        self._options = dict(options or {})
        self._indexes = dict(indexes or {"_id_": {"key": [("_id", 1)]}})
        self.dropped = False
        self.database: FakeDatabase | None = None

    def count_documents(self, query: dict[str, Any], limit: int = 0) -> int:
        matches = [document for document in self._documents if _matches(document, query)]
        if limit > 0:
            return min(len(matches), limit)
        return len(matches)

    def find(
        self,
        filter: dict[str, Any] | None = None,
        projection: dict[str, int] | None = None,
        sort: list[tuple[str, int]] | None = None,
        skip: int = 0,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        results = [dict(document) for document in self._documents if _matches(document, filter or {})]
        if sort:
            key, direction = sort[0]
            results.sort(key=lambda item: item[key], reverse=direction < 0)
        if projection is not None:
            projected = []
            for document in results:
                projected.append({key: value for key, value in document.items() if key in projection})
            results = projected
        if skip:
            results = results[skip:]
        if limit:
            results = results[:limit]
        return results

    def insert_many(self, documents: list[dict[str, Any]], ordered: bool = False) -> None:
        del ordered
        self._documents.extend(documents)

    def replace_one(self, filter: dict[str, Any], replacement: dict[str, Any], upsert: bool = False) -> None:
        identifier = filter["_id"]
        for index, existing in enumerate(self._documents):
            if existing["_id"] == identifier:
                self._documents[index] = dict(replacement)
                return
        if upsert:
            self._documents.append(dict(replacement))

    def drop(self) -> None:
        self._documents = []
        self.dropped = True

    def options(self) -> dict[str, Any]:
        return dict(self._options)

    def index_information(self) -> dict[str, dict[str, Any]]:
        return dict(self._indexes)

    def create_indexes(self, indexes: list[Any]) -> list[str]:
        names: list[str] = []
        for index in indexes:
            document = getattr(index, "document", {})
            if isinstance(document, dict):
                name = str(document.get("name", "unknown"))
            else:
                name = "unknown"
            names.append(name)
        return names


class FakeDatabase:
    def __init__(self, name: str, collections: dict[str, FakeCollection] | None = None) -> None:
        self.name = name
        self._collections = dict(collections or {})
        for collection in self._collections.values():
            collection.database = self

    def list_collection_names(self) -> list[str]:
        return list(self._collections.keys())

    def list_collections(self, filter: dict[str, str] | None = None) -> list[dict[str, Any]]:
        if filter is None:
            names = self.list_collection_names()
        else:
            target_name = filter.get("name")
            names = [name for name in self.list_collection_names() if name == target_name]
        return [
            {"name": name, "options": self._collections[name].options()}
            for name in names
        ]

    def __getitem__(self, collection_name: str) -> FakeCollection:
        return self._collections[collection_name]

    def create_collection(self, name: str, **kwargs: Any) -> FakeCollection:
        collection = FakeCollection(name=name, options=kwargs)
        collection.database = self
        self._collections[name] = collection
        return collection


class FakeConnector:
    def __init__(self, databases: dict[tuple[str, str], FakeDatabase]) -> None:
        self._databases = databases

    def get_database(self, endpoint: MongoEndpointConfig) -> FakeDatabase:
        return self._databases[(endpoint.uri, endpoint.database)]


def _matches(document: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, value in query.items():
        if document.get(key) != value:
            return False
    return True
