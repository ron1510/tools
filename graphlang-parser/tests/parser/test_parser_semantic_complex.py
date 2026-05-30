from opium_parser import (
    BinaryOpExpr,
    CallExpr,
    MethodCallExpr,
    SubscriptExpr,
    parse_opium,
)


def test_parse_complex_filter_aggregation_projection_chain():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".match_all("
        "match_any(eq('_key', 'admin'), eq('_key', 'owner')), "
        "score >= 90.0, "
        "regex_matches('name', '^[AO]', caseInsensitive=True)"
        ")"
        ".traverse_out('permissions-data-product.role_abilities')"
        ".into('permissions-data-product.abilities')"
        ".match(value_in('_key', ['write', 'delete', 'approve']))"
        ".unique()"
        ".count()"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "count"
    unique = ast.root.receiver
    assert isinstance(unique, MethodCallExpr)
    assert unique.method == "unique"

    ability_match = unique.receiver
    assert isinstance(ability_match, MethodCallExpr)
    assert ability_match.method == "match"
    assert isinstance(ability_match.args[0], CallExpr)
    assert ability_match.args[0].function == "value_in"


def test_parse_match_subquery_operand_from_current_row():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".match(eq("
        "traverse_out('permissions-data-product.role_abilities')"
        ".into('permissions-data-product.abilities')['_key'], "
        "'write'"
        "))"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "match"
    condition = ast.root.args[0]
    assert isinstance(condition, CallExpr)
    assert condition.function == "eq"
    assert isinstance(condition.args[0], SubscriptExpr)


def test_parse_match_deep_traversal_operand_from_current_row():
    ast = parse_opium(
        "get('org-data-product.teams')"
        ".match(eq("
        "traverse_out('org-data-product.team_hierarchy', max_depth=2)"
        ".into('org-data-product.teams')['_key'], "
        "'executive'"
        "))"
    )

    condition = ast.root.args[0]
    assert isinstance(condition, CallExpr)
    assert condition.function == "eq"
    assert isinstance(condition.args[0], SubscriptExpr)


def test_parse_match_traversal_aggregation_under_review():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".match("
        "traverse_out('permissions-data-product.role_abilities')"
        ".into('permissions-data-product.abilities')"
        ".count() >= 3"
        ")"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "match"
    assert isinstance(ast.root.args[0], BinaryOpExpr)


def test_parse_var_operand_and_computed_select_columns():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".as_var('role')"
        ".match(eq(var('role')['_key'], 'admin'))"
        ".select("
        "'_key', "
        "role_id=var('role')['_id'], "
        "is_admin=var('role')['_key'] == 'admin'"
        ")"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "select"
    assert isinstance(ast.root.kwargs["role_id"], SubscriptExpr)
    assert isinstance(ast.root.kwargs["is_admin"], BinaryOpExpr)


def test_parse_assign_array_flatten_shape_under_review():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".assign("
        "array("
        "traverse_any('users-data-product.user_role_subscriptions')"
        ".into('users-data-product.user_roles')['_key']"
        "), "
        "'neighborhood'"
        ")"
        ".select('_key', neighbors=var('neighborhood'))"
        ".flatten(depth=2)"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "flatten"
    select = ast.root.receiver
    assert isinstance(select, MethodCallExpr)
    assert select.method == "select"
    assign = select.receiver
    assert isinstance(assign, MethodCallExpr)
    assert assign.method == "assign"
