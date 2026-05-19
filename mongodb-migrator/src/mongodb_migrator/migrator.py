from __future__ import annotations

from typing import Any

from mongodb_migrator.checkpoint import CheckpointStore
from mongodb_migrator.connectors import CollectionHandle
from mongodb_migrator.models import (
    CheckpointState,
    CollectionCheckpoint,
    CollectionCopyResult,
    CollectionPlan,
    ExecutionOptions,
)


class BatchMigrator:
    def __init__(self, checkpoint_store: CheckpointStore | None = None) -> None:
        self._checkpoint_store = checkpoint_store or CheckpointStore()

    def copy_collection(
        self,
        source_collection: CollectionHandle,
        target_collection: CollectionHandle,
        plan: CollectionPlan,
        execution: ExecutionOptions,
    ) -> CollectionCopyResult:
        state = self._checkpoint_store.load(execution.checkpoint_path)
        collection_state = state.collections.get(plan.source_collection, CollectionCheckpoint())
        if collection_state.completed:
            return CollectionCopyResult(
                source_collection=plan.source_collection,
                target_collection=plan.target_collection,
                copied_documents=collection_state.copied_documents,
                recreated_indexes=0,
                skipped=True,
            )

        projection = None
        if plan.projection is not None:
            projection = {field: 1 for field in plan.projection}

        copied = collection_state.copied_documents
        if execution.dry_run:
            total = source_collection.count_documents(dict(plan.filter_query))
            return CollectionCopyResult(
                source_collection=plan.source_collection,
                target_collection=plan.target_collection,
                copied_documents=total,
                recreated_indexes=0,
                skipped=True,
            )

        while True:
            batch = list(
                source_collection.find(
                    filter=dict(plan.filter_query),
                    projection=projection,
                    sort=[("_id", 1)],
                    skip=copied,
                    limit=execution.batch_size,
                )
            )
            if not batch:
                break
            for document in batch:
                target_collection.replace_one({"_id": document["_id"]}, document, upsert=True)
            copied += len(batch)
            self._save_state(
                execution.checkpoint_path,
                state,
                plan.source_collection,
                CollectionCheckpoint(copied_documents=copied, completed=False),
            )

        self._save_state(
            execution.checkpoint_path,
            state,
            plan.source_collection,
            CollectionCheckpoint(copied_documents=copied, completed=True),
        )
        return CollectionCopyResult(
            source_collection=plan.source_collection,
            target_collection=plan.target_collection,
            copied_documents=copied,
            recreated_indexes=0,
            skipped=False,
        )

    def _save_state(
        self,
        path: str | None,
        state: CheckpointState,
        collection_name: str,
        checkpoint: CollectionCheckpoint,
    ) -> None:
        collections = dict(state.collections)
        collections[collection_name] = checkpoint
        updated = CheckpointState(collections=collections)
        self._checkpoint_store.save(path, updated)
