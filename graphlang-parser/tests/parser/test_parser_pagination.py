from opium_parser import CallExpr, MethodCallExpr, NumberExpr, parse_opium


def test_get_skip_chain():
    ast = parse_opium("get('users-data-product.user_roles').skip(100)")

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "skip"
    assert ast.root.args == [NumberExpr(value=100)]


def test_get_limit_chain():
    ast = parse_opium("get('users-data-product.user_roles').limit(100)")

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "limit"
    assert ast.root.args == [NumberExpr(value=100)]

    receiver = ast.root.receiver
    assert isinstance(receiver, CallExpr)
    assert receiver.function == "get"


def test_skip_limit_chain():
    ast = parse_opium("get('users-data-product.user_roles').skip(100).limit(100)")

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "limit"
    assert isinstance(ast.root.receiver, MethodCallExpr)
    assert ast.root.receiver.method == "skip"
