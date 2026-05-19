from __future__ import annotations

import hashlib
import json
import random
from typing import Any

from mongodb_migrator.connectors import CollectionHandle
from mongodb_migrator.models import (
    CollectionPlan,
    VerificationCollectionResult,
    VerificationOptions,
    VerificationReport,
)


def verify_collections(
    plans: tuple[CollectionPlan, ...],
    source_collections: dict[str, CollectionHandle],
    target_collections: dict[str, CollectionHandle],
    options: VerificationOptions,
) -> VerificationReport:
    results: list[VerificationCollectionResult] = []
    for plan in plans:
        source_collection = source_collections[plan.source_collection]
        target_collection = target_collections[plan.target_collection]
        source_count = source_collection.count_documents(dict(plan.filter_query))
        target_count = target_collection.count_documents(dict(plan.filter_query))
        hashes_match = True
        if options.sample_size > 0 and source_count > 0 and target_count > 0:
            hashes_match = _sample_hash(source_collection, dict(plan.filter_query), options) == _sample_hash(
                target_collection,
                dict(plan.filter_query),
                options,
            )
        results.append(
            VerificationCollectionResult(
                collection=plan.target_collection,
                source_count=source_count,
                target_count=target_count,
                hashes_match=hashes_match,
            )
        )
    return VerificationReport(collections=tuple(results))


def _sample_hash(
    collection: CollectionHandle,
    filter_query: dict[str, Any],
    options: VerificationOptions,
) -> str:
    docs = list(collection.find(filter=filter_query, sort=[("_id", 1)]))
    if not docs:
        return ""
    sample_size = min(options.sample_size, len(docs))
    rng = random.Random(options.sample_seed)
    chosen = rng.sample(docs, sample_size)
    payload = json.dumps(chosen, sort_keys=True, default=_json_default).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _json_default(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
