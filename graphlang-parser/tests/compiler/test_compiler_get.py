import pytest

from opium_parser import compile_opium_to_gremlin, parse_opium
from opium_parser.compiler import compile_ast_to_gremlin
from opium_parser.errors import InvalidOpiumSemanticError
from tests.compiler.expected_gremlin import VERTEX_DOCUMENT_STEP


def test_compile_get():
    assert (
        compile_opium_to_gremlin("get('users-data-product.user_roles')")
        == "g.V().hasLabel('users-data-product___user_roles')"
        f"{VERTEX_DOCUMENT_STEP}"
    )


def test_compile_get_multiple_collections():
    assert (
        compile_opium_to_gremlin(
            "get('users-data-product.user_roles', 'permissions-data-product.abilities')"
        )
        == "g.V().hasLabel('users-data-product___user_roles', "
        "'permissions-data-product___abilities')"
        f"{VERTEX_DOCUMENT_STEP}"
    )


def test_compile_get_key():
    assert (
        compile_opium_to_gremlin("get('users-data-product.user_roles', _key='admin')")
        == "g.V().hasLabel('users-data-product___user_roles')"
        ".hasId(TextP.endingWith('/admin'))"
        f"{VERTEX_DOCUMENT_STEP}"
    )


def test_compile_ast_api():
    ast = parse_opium("get('x').limit(1)")

    assert compile_ast_to_gremlin(ast) == (
        "g.V().hasLabel('x').limit(1)" f"{VERTEX_DOCUMENT_STEP}"
    )


def test_terminal_get_materializes_plain_vertex_documents():
    gremlin = compile_opium_to_gremlin("get('users')")

    assert gremlin.startswith("g.V().hasLabel('users').map{")
    assert "m['_key']=key" in gremlin
    assert "m['_id']=logicalId" in gremlin
    assert "while(ps.hasNext())" in gremlin


@pytest.mark.parametrize(
    "source",
    [
        "get('users')['_key']",
        "get('users').select('_key', 'name')",
        "get('users').count()",
    ],
)
def test_non_vertex_terminal_shapes_do_not_get_full_document_maps(source):
    gremlin = compile_opium_to_gremlin(source)

    assert "def v=it.get()" not in gremlin


def test_get_requires_resource():
    with pytest.raises(InvalidOpiumSemanticError):
        compile_opium_to_gremlin("get()")
