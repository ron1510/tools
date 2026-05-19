from __future__ import annotations

import logging

from mongodb_migrator.connectors import MongoConnector, PyMongoConnector
from mongodb_migrator.errors import ConfigurationError, CopySafetyError, VerificationError
from mongodb_migrator.metadata import ensure_collection, extract_metadata, recreate_indexes
from mongodb_migrator.migrator import BatchMigrator
from mongodb_migrator.models import (
    CopyRunReport,
    CollectionCopyResult,
    CollectionPlan,
    CopyRequest,
    VerificationReport,
)
from mongodb_migrator.verifier import verify_collections


class MongoCopyService:
    def __init__(
        self,
        connector: MongoConnector | None = None,
        migrator: BatchMigrator | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._connector = connector or PyMongoConnector()
        self._migrator = migrator or BatchMigrator()
        self._logger = logger or logging.getLogger(__name__)

    def copy(self, request: CopyRequest) -> CopyRunReport:
        if request.execution.dry_run and request.verification.enabled:
            raise ConfigurationError("verification cannot run together with dry-run mode")

        source_db = self._connector.get_database(request.source)
        target_db = self._connector.get_database(request.target)

        source_names = tuple(sorted(source_db.list_collection_names()))
        collection_names = _filter_collection_names(
            source_names,
            request.include_collections,
            request.exclude_collections,
        )
        if not collection_names:
            return CopyRunReport(results=tuple(), verification=None)
        target_names = set(target_db.list_collection_names())
        if not request.execution.replace_target:
            collisions = [
                name
                for name in collection_names
                if name in target_names
                and target_db[name].count_documents({}, limit=1) > 0
            ]
            if collisions:
                raise CopySafetyError(
                    "target already contains data for collections: "
                    + ", ".join(collisions)
                    + "; rerun with --replace-target to allow replacement"
                )

        results: list[CollectionCopyResult] = []
        source_handles = {}
        target_handles = {}
        for name in collection_names:
            self._logger.info("Copying collection", extra={"collection": name})
            source_collection = source_db[name]
            metadata = extract_metadata(source_collection)
            if request.execution.replace_target and name in target_names:
                target_db[name].drop()
            target_collection = ensure_collection(target_db, name, metadata)
            copy_result = self._migrator.copy_collection(
                source_collection=source_collection,
                target_collection=target_collection,
                plan=CollectionPlan(source_collection=name, target_collection=name),
                execution=request.execution,
            )
            recreated_indexes = 0
            if not request.execution.dry_run:
                recreated_indexes = recreate_indexes(target_collection, metadata)
            results.append(copy_result.model_copy(update={"recreated_indexes": recreated_indexes}))
            source_handles[name] = source_collection
            target_handles[name] = target_collection

        report = None
        if request.verification.enabled:
            plans = tuple(
                CollectionPlan(source_collection=name, target_collection=name)
                for name in collection_names
            )
            report = verify_collections(plans, source_handles, target_handles, request.verification)
            if not report.success:
                raise VerificationError("verification failed: counts or sample hashes do not match")
        return CopyRunReport(results=tuple(results), verification=report)


def _filter_collection_names(
    collection_names: tuple[str, ...],
    include_collections: tuple[str, ...],
    exclude_collections: tuple[str, ...],
) -> tuple[str, ...]:
    names = set(collection_names)
    if include_collections:
        names = names.intersection(include_collections)
    if exclude_collections:
        names = names.difference(exclude_collections)
    return tuple(sorted(names))
