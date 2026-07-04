import pytest

from opium_parser import compile_opium_to_gremlin
from opium_parser.errors import InvalidOpiumSemanticError
from tests.compiler.expected_gremlin import (
    ANY_VERTEX_STEP,
    IN_VERTEX_STEP,
    OUT_VERTEX_STEP,
)


def test_compile_as_var():
    assert (
        compile_opium_to_gremlin("get('users').as_var('user')")
        == "g.V().hasLabel('users').as('user')"
    )


def test_compile_assign():
    assert (
        compile_opium_to_gremlin(
            "get('users').assign(traverse().into(), 'neighborhood')"
        )
        == "g.V().hasLabel('users')"
        ".sideEffect(__.as('opium_current_vertex').bothE()"
        f"{ANY_VERTEX_STEP}.fold().as('neighborhood'))"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "get('users')"
            ".assign(traverse_out('subs').into('roles')['_key'], 'neighbors')",
            "g.V().hasLabel('users')"
            f".sideEffect(__.outE('subs'){OUT_VERTEX_STEP}.hasLabel('roles')"
            ".id().map{it.get().substring(it.get().lastIndexOf('/') + 1)}"
            ".fold().as('neighbors'))",
        ),
        (
            "get('users').assign(traverse_in('subs'), 'incoming_edges').count()",
            "g.V().hasLabel('users')"
            ".sideEffect(__.inE('subs').fold().as('incoming_edges'))"
            ".count()",
        ),
        (
            "get('users')"
            ".assign(traverse_out('subs').into('roles'), 'out_roles')"
            ".assign(traverse_in('subs').into('roles'), 'in_roles')"
            ".select('_key')",
            "g.V().hasLabel('users')"
            f".sideEffect(__.outE('subs'){OUT_VERTEX_STEP}.hasLabel('roles')"
            ".fold().as('out_roles'))"
            f".sideEffect(__.inE('subs'){IN_VERTEX_STEP}.hasLabel('roles')"
            ".fold().as('in_roles'))"
            ".project('_key')"
            ".by(__.id().map{it.get().substring(it.get().lastIndexOf('/') + 1)})",
        ),
    ],
)
def test_compile_assign_shapes(source, expected):
    assert compile_opium_to_gremlin(source) == expected


def test_compile_select_columns_and_computed_var_projection():
    assert (
        compile_opium_to_gremlin(
            "get('users').assign(traverse().into(), 'neighborhood')"
            ".select('_key', neighbors=var('neighborhood')['_key'])"
        )
        == "g.V().hasLabel('users')"
        ".sideEffect(__.as('opium_current_vertex').bothE()"
        f"{ANY_VERTEX_STEP}.fold().as('neighborhood'))"
        ".project('_key', 'neighbors')"
        ".by(__.id().map{it.get().substring(it.get().lastIndexOf('/') + 1)})"
        ".by(select('neighborhood')"
        ".id().map{it.get().substring(it.get().lastIndexOf('/') + 1)})"
    )


@pytest.mark.parametrize(
    "source",
    [
        "get('users').assign(traverse().into())",
        "get('users').assign(traverse().into(), 'neighbors', 'extra')",
        "get('users').assign(traverse().into(), neighbors='x')",
        "get('users').assign(traverse().into(), var('neighbors'))",
    ],
)
def test_invalid_assign_shapes(source):
    with pytest.raises(InvalidOpiumSemanticError):
        compile_opium_to_gremlin(source)
