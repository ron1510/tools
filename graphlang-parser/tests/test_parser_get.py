import pytest

from opium_parser import CallExpr, NumberExpr, StringExpr, parse_opium
from opium_parser.errors import InvalidOpiumExpressionError


def test_get_with_resource():
    ast = parse_opium("get('users-data-product.user_roles')")

    assert isinstance(ast.root, CallExpr)
    assert ast.root.function == "get"
    assert ast.root.args == [StringExpr("users-data-product.user_roles")]
    assert ast.root.kwargs == {}


def test_get_with_resource_and_key():
    ast = parse_opium("get('users-data-product.user_roles', _key='admin')")

    assert isinstance(ast.root, CallExpr)
    assert ast.root.function == "get"
    assert ast.root.args[0] == StringExpr("users-data-product.user_roles")
    assert ast.root.kwargs["_key"] == StringExpr("admin")


def test_get_with_multiple_sources():
    ast = parse_opium(
        "get('users-data-product.user_roles', 'veto-data-product.abilities')"
    )

    assert isinstance(ast.root, CallExpr)
    assert ast.root.args == [
        StringExpr("users-data-product.user_roles"),
        StringExpr("veto-data-product.abilities"),
    ]


def test_literals():
    ast = parse_opium("get('x', active=True, deleted=False, score=1.5, empty=None)")

    assert isinstance(ast.root, CallExpr)
    assert ast.root.args == [StringExpr("x")]
    assert ast.root.kwargs["score"] == NumberExpr(1.5)
    assert "active" in ast.root.kwargs
    assert "deleted" in ast.root.kwargs
    assert "empty" in ast.root.kwargs


def test_duplicate_kwargs_are_rejected():
    with pytest.raises(InvalidOpiumExpressionError):
        parse_opium("get('x', _key='one', _key='two')")

