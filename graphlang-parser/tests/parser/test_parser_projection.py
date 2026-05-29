from opium_parser import CallExpr, MethodCallExpr, SubscriptExpr, parse_opium


def test_get_projection():
    ast = parse_opium("get('users-data-product.user_roles')['_key']")

    assert isinstance(ast.root, SubscriptExpr)
    assert ast.root.field == "_key"
    assert isinstance(ast.root.receiver, CallExpr)
    assert ast.root.receiver.function == "get"


def test_var_projection():
    ast = parse_opium("var('neighborhood')['_key']")

    assert isinstance(ast.root, SubscriptExpr)
    assert ast.root.field == "_key"
    assert isinstance(ast.root.receiver, CallExpr)
    assert ast.root.receiver.function == "var"


def test_projection_inside_select_kwarg():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".assign(traverse().into(), 'neighborhood')"
        ".select('_key', neighbors=var('neighborhood')['_key'])"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "select"
    projection = ast.root.kwargs["neighbors"]
    assert isinstance(projection, SubscriptExpr)
    assert projection.field == "_key"

