from opium_parser import CallExpr, MethodCallExpr, StringExpr, parse_opium


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
