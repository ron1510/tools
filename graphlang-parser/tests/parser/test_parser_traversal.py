from opium_parser import CallExpr, MethodCallExpr, NumberExpr, StringExpr, parse_opium


def test_get_traverse_chain():
    ast = parse_opium("get('users-data-product.user_roles').traverse()")

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "traverse"
    assert ast.root.args == []
    assert isinstance(ast.root.receiver, CallExpr)
    assert ast.root.receiver.function == "get"


def test_get_traverse_with_edge_resource():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".traverse('users-data-product.user_role_subscriptions')"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "traverse"
    assert ast.root.args == [
        StringExpr(value="users-data-product.user_role_subscriptions")
    ]


def test_get_traverse_with_depth_and_direction():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".traverse(min_depth=1, max_depth=4, direction='any')"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "traverse"
    assert ast.root.kwargs["min_depth"] == NumberExpr(value=1)
    assert ast.root.kwargs["max_depth"] == NumberExpr(value=4)
    assert ast.root.kwargs["direction"] == StringExpr(value="any")


def test_into_chain():
    ast = parse_opium("get('users-data-product.user_roles').traverse().into()")

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "into"
    assert isinstance(ast.root.receiver, MethodCallExpr)
    assert ast.root.receiver.method == "traverse"


def test_into_with_node_resource():
    ast = parse_opium(
        "get('users-data-product.user_roles').traverse()"
        ".into('users-data-product.user_roles')"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "into"
    assert ast.root.args == [StringExpr(value="users-data-product.user_roles")]
