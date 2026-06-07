from opium_parser import (
    CallExpr,
    MethodCallExpr,
    StringExpr,
    SubscriptExpr,
    parse_opium,
)


def test_as_var():
    ast = parse_opium("get('users-data-product.user_roles').as_var('user_role')")

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "as_var"
    assert ast.root.args == [StringExpr(value="user_role")]


def test_assign_nested_subquery():
    ast = parse_opium(
        "get('users-data-product.user_roles').assign(traverse().into(), 'neighborhood')"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "assign"

    nested = ast.root.args[0]
    assert isinstance(nested, MethodCallExpr)
    assert nested.method == "into"
    assert isinstance(nested.receiver, CallExpr)
    assert nested.receiver.function == "traverse"


def test_select_with_variable():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".assign(traverse().into(), 'neighborhood')"
        ".select('_key', neighbors=var('neighborhood'))"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "select"
    assert ast.root.args == [StringExpr(value="_key")]
    assert isinstance(ast.root.kwargs["neighbors"], CallExpr)
    assert ast.root.kwargs["neighbors"].function == "var"


def test_assign_projected_subquery_to_variable():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".assign("
        "traverse_out('permissions-data-product.role_abilities')"
        ".into('permissions-data-product.abilities')['_key'], "
        "'ability_keys'"
        ")"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "assign"
    projected = ast.root.args[0]
    assert isinstance(projected, SubscriptExpr)
    assert projected.field == "_key"
    assert ast.root.args[1] == StringExpr(value="ability_keys")


def test_multiple_assigns_then_select():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".assign(traverse_out('edge_a').into('node_a'), 'out_nodes')"
        ".assign(traverse_in('edge_b').into('node_b'), 'in_nodes')"
        ".select('_key', out=var('out_nodes'), incoming=var('in_nodes'))"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "select"
    assert ast.root.args == [StringExpr(value="_key")]
    assert set(ast.root.kwargs) == {"out", "incoming"}
    assert isinstance(ast.root.receiver, MethodCallExpr)
    assert ast.root.receiver.method == "assign"
