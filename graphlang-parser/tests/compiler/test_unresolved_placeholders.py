import pytest

from opium_parser import compile_opium_to_gremlin


def test_array_per_row_semantics_compile_shape():
    assert (
        compile_opium_to_gremlin("get('users').array(traverse().into())")
        == "g.V().hasLabel('users').local(__.bothE().otherV()).fold()"
    )


def test_flatten_depth_compile_shape():
    assert (
        compile_opium_to_gremlin(
            "get('users').array(traverse().into()).flatten(depth=2)"
        )
        == "g.V().hasLabel('users')"
        ".local(__.bothE().otherV()).fold()"
        ".unfold().unfold()"
    )


@pytest.mark.skip(reason="assign variable value projection still needs live semantics")
def test_assign_variable_projection_placeholder():
    compile_opium_to_gremlin(
        "get('users').assign(traverse().into(), 'neighbors')"
        ".select('_key', neighbors=var('neighbors')['_key'])"
    )
