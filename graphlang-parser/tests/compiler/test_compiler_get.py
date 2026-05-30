import pytest

from opium_parser import compile_opium_to_gremlin, parse_opium
from opium_parser.compiler import compile_ast_to_gremlin
from opium_parser.errors import InvalidOpiumSemanticError


def test_compile_get():
    assert (
        compile_opium_to_gremlin("get('users-data-product.user_roles')")
        == "g.V().hasLabel('users-data-product.user_roles')"
    )


def test_compile_get_multiple_collections():
    assert (
        compile_opium_to_gremlin(
            "get('users-data-product.user_roles', 'permissions-data-product.abilities')"
        )
        == "g.V().hasLabel('users-data-product.user_roles', "
        "'permissions-data-product.abilities')"
    )


def test_compile_get_key():
    assert (
        compile_opium_to_gremlin("get('users-data-product.user_roles', _key='admin')")
        == "g.V().hasLabel('users-data-product.user_roles')"
        ".hasId(TextP.endingWith('/admin'))"
    )


def test_compile_ast_api():
    ast = parse_opium("get('x').limit(1)")

    assert compile_ast_to_gremlin(ast) == "g.V().hasLabel('x').limit(1)"


def test_get_requires_resource():
    with pytest.raises(InvalidOpiumSemanticError):
        compile_opium_to_gremlin("get()")
