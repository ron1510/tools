import pytest

from opium_parser import compile_opium_to_gremlin
from opium_parser.errors import (
    InvalidOpiumSemanticError,
    UnsupportedOpiumCompilationError,
)


def test_compile_traverse_any_into():
    assert (
        compile_opium_to_gremlin("get('users').traverse().into()")
        == "g.V().hasLabel('users').bothE().otherV()"
    )


def test_compile_traverse_edge_label_direction_and_into_label():
    assert (
        compile_opium_to_gremlin(
            "get('users').traverse('subs', direction='inbound').into('roles')"
        )
        == "g.V().hasLabel('users').inE('subs').otherV().hasLabel('roles')"
    )


def test_compile_traverse_sugar_out():
    assert (
        compile_opium_to_gremlin("get('users').traverse_out('subs').into()")
        == "g.V().hasLabel('users').outE('subs').otherV()"
    )


def test_compile_skip_limit_count_unique():
    assert (
        compile_opium_to_gremlin("get('users').skip(10).limit(5).unique().count()")
        == "g.V().hasLabel('users').skip(10).limit(5).dedup().count()"
    )


def test_compile_projection():
    assert (
        compile_opium_to_gremlin("get('users')['_key']")
        == "g.V().hasLabel('users')"
        ".id().map{it.get().substring(it.get().lastIndexOf('/') + 1)}"
    )


def test_compile_array_flatten():
    assert (
        compile_opium_to_gremlin("get('users').array(traverse().into()).flatten()")
        == "g.V().hasLabel('users').local(__.bothE().otherV()).fold().unfold()"
    )


def test_invalid_direction():
    with pytest.raises(InvalidOpiumSemanticError):
        compile_opium_to_gremlin("get('users').traverse(direction='sideways')")


def test_depth_is_not_supported_yet():
    with pytest.raises(UnsupportedOpiumCompilationError):
        compile_opium_to_gremlin("get('users').traverse(min_depth=1, max_depth=2)")
