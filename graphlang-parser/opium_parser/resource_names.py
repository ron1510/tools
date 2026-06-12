"""Translate logical Opium resource names to ArangoDB collection names."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from opium_parser.errors import InvalidOpiumSemanticError
from opium_parser.types import ArangoCollectionName, ResourceName

RESOURCE_SEPARATOR: Final = "."
COLLECTION_SEPARATOR: Final = "___"


def normalize_resource_name(name: ResourceName) -> ArangoCollectionName:
    """Return the physical collection name used by ArangoDB and Gremlin."""

    if COLLECTION_SEPARATOR in name:
        msg = (
            f"Resource name {name!r} contains reserved sequence "
            f"{COLLECTION_SEPARATOR!r}"
        )
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.ambiguous_resource_name",
            hint=(
                f"Use {RESOURCE_SEPARATOR!r} between logical resource segments; "
                f"{COLLECTION_SEPARATOR!r} is reserved for ArangoDB collections."
            ),
            actual=str(name),
            context={"resource": str(name)},
        )
    return ArangoCollectionName(
        str(name).replace(RESOURCE_SEPARATOR, COLLECTION_SEPARATOR)
    )


def normalize_resource_names(
    names: Sequence[ResourceName],
) -> list[ArangoCollectionName]:
    return [normalize_resource_name(name) for name in names]


def denormalize_collection_name(name: ArangoCollectionName) -> ResourceName:
    """Return the logical Opium resource name for a physical collection."""

    return ResourceName(str(name).replace(COLLECTION_SEPARATOR, RESOURCE_SEPARATOR))


def denormalize_element_id(element_id: str) -> str:
    """Translate only the collection prefix of an Arango element id."""

    collection, separator, key = element_id.partition("/")
    logical_collection = denormalize_collection_name(ArangoCollectionName(collection))
    return f"{logical_collection}{separator}{key}"
