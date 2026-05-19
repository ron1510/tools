from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

from mongodb_migrator.errors import ConnectionError
from mongodb_migrator.models import MongoEndpointConfig

if TYPE_CHECKING:
    from pymongo import IndexModel


class CollectionHandle(Protocol):
    name: str
    database: Any

    def count_documents(self, query: dict[str, Any], limit: int = 0) -> int: ...

    def find(
        self,
        filter: dict[str, Any] | None = None,
        projection: dict[str, int] | None = None,
        sort: list[tuple[str, int]] | None = None,
        skip: int = 0,
        limit: int = 0,
    ) -> Any: ...

    def insert_many(self, documents: list[dict[str, Any]], ordered: bool = False) -> Any: ...

    def replace_one(self, filter: dict[str, Any], replacement: dict[str, Any], upsert: bool = False) -> Any: ...

    def drop(self) -> None: ...

    def options(self) -> dict[str, Any]: ...

    def index_information(self) -> dict[str, dict[str, Any]]: ...

    def create_indexes(self, indexes: list["IndexModel"]) -> list[str]: ...


class DatabaseHandle(Protocol):
    name: str

    def list_collection_names(self) -> list[str]: ...

    def __getitem__(self, collection_name: str) -> CollectionHandle: ...

    def create_collection(self, name: str, **kwargs: Any) -> CollectionHandle: ...


class MongoConnector(Protocol):
    def get_database(self, endpoint: MongoEndpointConfig) -> DatabaseHandle: ...


class PyMongoConnector:
    def get_database(self, endpoint: MongoEndpointConfig) -> DatabaseHandle:
        try:
            from pymongo import MongoClient
        except ImportError as exc:
            raise ConnectionError(
                "pymongo is required at runtime; install with `pip install -e .[mongo]`"
            ) from exc

        try:
            client: Any = MongoClient(endpoint.uri)
            client.admin.command("ping")
        except Exception as exc:  # pragma: no cover - depends on external runtime
            raise ConnectionError(f"failed to connect to {endpoint.uri}: {exc}") from exc
        return cast(DatabaseHandle, client[endpoint.database])
