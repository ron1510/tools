import pytest

from opium_parser import compile_opium_to_gremlin
from opium_parser.errors import InvalidOpiumSemanticError
from tests.compiler.expected_gremlin import (
    ANY_VERTEX_STEP,
    IN_VERTEX_STEP,
    LOGICAL_ID_MAP,
    OUT_VERTEX_STEP,
    SOURCE_ID_STEP,
    TARGET_ID_STEP,
    VERTEX_DOCUMENT_STEP,
)


def test_compile_terminal_traverse_materializes_safe_edge_documents():
    gremlin = compile_opium_to_gremlin("get('users').traverse()")

    assert gremlin.startswith(
        "g.V().hasLabel('users').as('opium_current_vertex').bothE().map{"
    )
    assert "m['_key']=key" in gremlin
    assert "m['_id']=logicalId" in gremlin
    assert "m['_from']=source.replace('___', '.')" in gremlin
    assert "m['_to']=target.replace('___', '.')" in gremlin
    assert "while(ps.hasNext())" in gremlin


def test_compile_terminal_deep_traverse_materializes_safe_edge_documents():
    gremlin = compile_opium_to_gremlin(
        "get('users').traverse_out('subs', min_depth=2, max_depth=3)"
    )

    assert ".select('opium_edge').map{" in gremlin
    assert "m['_from']=source.replace('___', '.')" in gremlin
    assert "m['_to']=target.replace('___', '.')" in gremlin


def test_compile_traverse_any_into():
    assert (
        compile_opium_to_gremlin("get('users').traverse().into()")
        == "g.V().hasLabel('users')"
        ".as('opium_current_vertex')"
        ".bothE()"
        f"{ANY_VERTEX_STEP}"
        f"{VERTEX_DOCUMENT_STEP}"
    )


def test_compile_traverse_edge_label_direction_and_into_label():
    assert (
        compile_opium_to_gremlin(
            "get('users').traverse('subs', direction='inbound').into('roles')"
        )
        == f"g.V().hasLabel('users').inE('subs'){IN_VERTEX_STEP}.hasLabel('roles')"
        f"{VERTEX_DOCUMENT_STEP}"
    )


def test_compile_traverse_sugar_out():
    assert (
        compile_opium_to_gremlin("get('users').traverse_out('subs').into()")
        == f"g.V().hasLabel('users').outE('subs'){OUT_VERTEX_STEP}"
        f"{VERTEX_DOCUMENT_STEP}"
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
        ".map{def id=it.get(); def slash=id.indexOf('/'); "
        "slash < 0 ? id.replace('___', '.') : "
        "id.substring(0, slash).replace('___', '.') + id.substring(slash)}"
    )


def test_compile_missing_field_projection():
    assert (
        compile_opium_to_gremlin("get('users')['missing']")
        == "g.V().hasLabel('users').coalesce(values('missing'), constant(null))"
    )


def test_compile_edge_from_to_projection():
    assert (
        compile_opium_to_gremlin("get('users').traverse_out('subs')['_from']")
        == "g.V().hasLabel('users').outE('subs')"
        f"{SOURCE_ID_STEP}"
        f"{LOGICAL_ID_MAP}"
    )
    assert (
        compile_opium_to_gremlin("get('users').traverse_out('subs')['_to']")
        == "g.V().hasLabel('users').outE('subs')"
        f"{TARGET_ID_STEP}"
        f"{LOGICAL_ID_MAP}"
    )


def test_compile_array_flatten():
    assert (
        compile_opium_to_gremlin("get('users').array(traverse().into()).flatten()")
        == "g.V().hasLabel('users')"
        ".local(__.as('opium_current_vertex').bothE()"
        f"{ANY_VERTEX_STEP})"
        ".fold().unfold()"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "get('users').array(traverse_out('subs').into('roles')['_key'])",
            "g.V().hasLabel('users')"
            f".local(__.outE('subs'){OUT_VERTEX_STEP}.hasLabel('roles')"
            ".id().map{it.get().substring(it.get().lastIndexOf('/') + 1)})"
            ".fold()",
        ),
        (
            "get('users').array(traverse_in('subs')['_from'])",
            "g.V().hasLabel('users').local(__.inE('subs')"
            f"{SOURCE_ID_STEP}"
            f"{LOGICAL_ID_MAP})"
            ".fold()",
        ),
        (
            "get('users')"
            ".array(traverse_any('subs').match(weight > 1).select('_key', 'weight'))",
            "g.V().hasLabel('users')"
            ".local(__.as('opium_current_vertex').bothE('subs')"
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
            "g.V().hasLabel('users')"
            ".local(__.as('opium_current_vertex').bothE()"
            f"{ANY_VERTEX_STEP})"
            ".fold()",
        ),
        (
            "get('users').array(traverse().into()).flatten(depth=1)",
            "g.V().hasLabel('users')"
            ".local(__.as('opium_current_vertex').bothE()"
            f"{ANY_VERTEX_STEP})"
            ".fold().unfold()",
        ),
        (
            "get('users').array(traverse().into()).flatten(depth=3)",
            "g.V().hasLabel('users')"
            ".local(__.as('opium_current_vertex').bothE()"
            f"{ANY_VERTEX_STEP})"
            ".fold()"
            ".unfold().unfold().unfold()",
        ),
    ],
)
def test_compile_flatten_depth_shapes(source, expected):
    assert compile_opium_to_gremlin(source) == expected


def test_invalid_direction():
    with pytest.raises(InvalidOpiumSemanticError):
        compile_opium_to_gremlin("get('users').traverse(direction='sideways')")


def test_compile_traverse_match_preserves_edge_cursor_for_into():
    assert (
        compile_opium_to_gremlin(
            "get('users').traverse_out('subs').match(weight > 1).into('roles')"
        )
        == "g.V().hasLabel('users')"
        ".outE('subs')"
        ".has('weight', P.gt(1))"
        f"{OUT_VERTEX_STEP}"
        ".hasLabel('roles')"
        f"{VERTEX_DOCUMENT_STEP}"
    )


@pytest.mark.parametrize(
    "source",
    [
        "get('users').traverse_out('subs').select('_key').into('roles')",
        "get('users').traverse_out('subs').count().into('roles')",
        "get('users').traverse_out('subs')['_key'].into('roles')",
    ],
)
def test_into_rejects_non_edge_cursor(source):
    with pytest.raises(InvalidOpiumSemanticError, match="edge documents"):
        compile_opium_to_gremlin(source)


def test_compile_deep_traverse_into():
    assert (
        compile_opium_to_gremlin(
            "get('users').traverse_out('subs', max_depth=3).into()"
        )
        == "g.V().hasLabel('users')"
        f".repeat(outE('subs').as('opium_edge'){OUT_VERTEX_STEP})"
        ".emit().times(3)"
        f"{VERTEX_DOCUMENT_STEP}"
    )


def test_compile_deep_traverse_edges():
    gremlin = compile_opium_to_gremlin(
        "get('users').traverse_out('subs', min_depth=2, max_depth=3)"
    )
    assert gremlin.startswith(
        "g.V().hasLabel('users')"
        f".repeat(outE('subs').as('opium_edge'){OUT_VERTEX_STEP})"
        ".emit(loops().is(P.gte(2))).times(3)"
        ".select('opium_edge').map{"
    )
    assert "m['_from']=source.replace('___', '.')" in gremlin
    assert "m['_to']=target.replace('___', '.')" in gremlin
