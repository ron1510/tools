from opium_parser import MethodCallExpr, NumberExpr, SubscriptExpr, parse_opium


def test_count():
    ast = parse_opium("get('users-data-product.user_roles').count()")

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "count"
    assert ast.root.args == []


def test_unique():
    ast = parse_opium("get('users-data-product.user_roles').unique()")

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "unique"


def test_array_with_nested_subquery():
    ast = parse_opium("get('users-data-product.user_roles').array(traverse().into())")

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "array"
    nested = ast.root.args[0]
    assert isinstance(nested, MethodCallExpr)
    assert nested.method == "into"


def test_flatten_with_depth():
    ast = parse_opium(
        "get('users-data-product.user_roles').array(traverse().into()).flatten(depth=2)"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "flatten"
    assert ast.root.kwargs["depth"] == NumberExpr(value=2)


def test_array_with_filtered_projected_subquery():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".array("
        "traverse_out('permissions-data-product.role_abilities')"
        ".into('permissions-data-product.abilities')"
        ".match(gt('severity', 4))"
        "['_key']"
        ")"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "array"
    projected = ast.root.args[0]
    assert isinstance(projected, SubscriptExpr)
    assert projected.field == "_key"
    assert isinstance(projected.receiver, MethodCallExpr)
    assert projected.receiver.method == "match"


def test_array_flatten_depth_chain_preserves_nested_receiver_shape():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".array(traverse_out('edge').into('node')['_key'])"
        ".flatten(depth=3)"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "flatten"
    assert ast.root.kwargs["depth"] == NumberExpr(value=3)
    assert isinstance(ast.root.receiver, MethodCallExpr)
    assert ast.root.receiver.method == "array"
