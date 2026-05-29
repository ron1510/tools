from opium_parser import CallExpr, MethodCallExpr, SubscriptExpr, parse_opium


def test_parse_complex_documented_chain():
    ast = parse_opium(
        "get('users-data-product.user_roles', _key='admin')"
        ".traverse_out("
        "'veto-data-product.role_abilities', "
        "max_depth=3"
        ")"
        ".into('veto-data-product.abilities')"
        ".match_any("
        "eq('_key', 'write'), "
        "regex_matches('name', '^A', caseInsensitive=True)"
        ")"
        ".select('_key', name='ability', source=var('role')['_id'])"
        ".limit(10)"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "limit"
    select = ast.root.receiver
    assert isinstance(select, MethodCallExpr)
    assert select.method == "select"
    assert isinstance(select.kwargs["source"], SubscriptExpr)


def test_parse_nested_subqueries_and_projection():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".assign(traverse_in('users-data-product.user_role_subscriptions')"
        ".into('users-data-product.user_roles')['_key'], 'neighbors')"
        ".select('_key', neighbors=var('neighbors'))"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "select"
    assign = ast.root.receiver
    assert isinstance(assign, MethodCallExpr)
    assert assign.method == "assign"
    assert isinstance(assign.args[0], SubscriptExpr)


def test_parse_top_level_condition_composition():
    ast = parse_opium(
        "match_all("
        "match_any(eq('_key', 'admin'), eq('_key', 'owner')), "
        "gt('priority', 5), "
        "regex_matches('name', '^[AO]', caseInsensitive=True)"
        ")"
    )

    assert isinstance(ast.root, CallExpr)
    assert ast.root.function == "match_all"
    assert len(ast.root.args) == 3
