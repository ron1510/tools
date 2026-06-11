import pytest

from opium_parser import compile_opium_to_gremlin
from opium_parser.errors import InvalidOpiumSemanticError
from opium_parser.resource_names import normalize_resource_name
from opium_parser.types import ResourceName


@pytest.mark.parametrize(
    ("logical", "physical"),
    [
        ("users", "users"),
        ("users-data-product.user_roles", "users-data-product___user_roles"),
        ("one.two.three", "one___two___three"),
    ],
)
def test_normalize_resource_name(logical: str, physical: str):
    assert normalize_resource_name(ResourceName(logical)) == physical


def test_reserved_physical_separator_is_rejected():
    with pytest.raises(InvalidOpiumSemanticError) as exc_info:
        compile_opium_to_gremlin("get('users-data-product___user_roles')")

    assert exc_info.value.detail.code == "semantic.ambiguous_resource_name"
