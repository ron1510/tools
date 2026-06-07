import pytest

from opium_parser import compile_opium_to_gremlin
from opium_parser.errors import InvalidOpiumSemanticError


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
        compile_opium_to_gremlin("get('users')['_key']") == "g.V().hasLabel('users')"
        ".id().map{it.get().substring(it.get().lastIndexOf('/') + 1)}"
    )


def test_compile_id_projection():
    assert (
        compile_opium_to_gremlin("get('users')['_id']")
        == "g.V().hasLabel('users').id()"
    )


def test_compile_missing_field_projection():
    assert (
        compile_opium_to_gremlin("get('users')['missing']")
        == "g.V().hasLabel('users').coalesce(values('missing'), constant(null))"
    )


def test_compile_edge_from_to_projection():
    assert (
        compile_opium_to_gremlin("get('users').traverse_out('subs')['_from']")
        == "g.V().hasLabel('users').outE('subs').outV().id()"
    )
    assert (
        compile_opium_to_gremlin("get('users').traverse_out('subs')['_to']")
        == "g.V().hasLabel('users').outE('subs').inV().id()"
    )


def test_compile_array_flatten():
    assert (
        compile_opium_to_gremlin("get('users').array(traverse().into()).flatten()")
        == "g.V().hasLabel('users').local(__.bothE().otherV()).fold().unfold()"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "get('users').array(traverse_out('subs').into('roles')['_key'])",
            "g.V().hasLabel('users')"
            ".local(__.outE('subs').otherV().hasLabel('roles')"
            ".id().map{it.get().substring(it.get().lastIndexOf('/') + 1)})"
            ".fold()",
        ),
        (
            "get('users').array(traverse_in('subs')['_from'])",
            "g.V().hasLabel('users').local(__.inE('subs').outV().id()).fold()",
        ),
        (
            "get('users')"
            ".array(traverse_any('subs').match(weight > 1).select('_key', 'weight'))",
            "g.V().hasLabel('users')"
            ".local(__.bothE('subs')"
            ".has('weight', P.gt(1))"
            ".project('_key', 'weight')"
            ".by(__.id().map{it.get().substring(it.get().lastIndexOf('/') + 1)})"
            ".by(coalesce(values('weight'), constant(null))))"
            ".fold()",
        ),
    ],
)
def test_compile_array_subquery_shapes(source, expected):
    assert compile_opium_to_gremlin(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "get('users').array(traverse().into()).flatten(depth=0)",
            "g.V().hasLabel('users').local(__.bothE().otherV()).fold()",
        ),
        (
            "get('users').array(traverse().into()).flatten(depth=1)",
            "g.V().hasLabel('users').local(__.bothE().otherV()).fold().unfold()",
        ),
        (
            "get('users').array(traverse().into()).flatten(depth=3)",
            "g.V().hasLabel('users')"
            ".local(__.bothE().otherV()).fold()"
            ".unfold().unfold().unfold()",
        ),
    ],
)
def test_compile_flatten_depth_shapes(source, expected):
    assert compile_opium_to_gremlin(source) == expected


def test_invalid_direction():
    with pytest.raises(InvalidOpiumSemanticError):
        compile_opium_to_gremlin("get('users').traverse(direction='sideways')")


def test_compile_deep_traverse_into():
    assert (
        compile_opium_to_gremlin(
            "get('users').traverse_out('subs', max_depth=3).into()"
        )
        == "g.V().hasLabel('users')"
        ".repeat(outE('subs').as('opium_edge').inV()).emit().times(3)"
    )


def test_compile_deep_traverse_edges():
    assert (
        compile_opium_to_gremlin(
            "get('users').traverse_out('subs', min_depth=2, max_depth=3)"
        )
        == "g.V().hasLabel('users')"
        ".repeat(outE('subs').as('opium_edge').inV())"
        ".emit(loops().is(P.gte(2))).times(3)"
        ".select('opium_edge')"
    )
