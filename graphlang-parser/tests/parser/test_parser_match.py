from opium_parser import (
    BinaryOpExpr,
    CallExpr,
    ListExpr,
    MethodCallExpr,
    NameExpr,
    NumberExpr,
    StringExpr,
    parse_opium,
)


def test_match_keyword_equality():
    ast = parse_opium("get('users-data-product.user_roles').match(_key='hello')")

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "match"
    assert ast.root.kwargs["_key"] == StringExpr("hello")


def test_match_any_keyword_equality():
    ast = parse_opium(
        "get('users-data-product.user_roles').match_any(_key='hello', name='goodbye')"
    )

    assert isinstance(ast.root, MethodCallExpr)
    assert ast.root.method == "match_any"
    assert ast.root.kwargs["_key"] == StringExpr("hello")
    assert ast.root.kwargs["name"] == StringExpr("goodbye")


def test_match_function_comparison():
    ast = parse_opium("get('users-data-product.user_roles').match(eq('_key', 'hello'))")

    condition = ast.root.args[0]
    assert isinstance(condition, CallExpr)
    assert condition.function == "eq"
    assert condition.args == [StringExpr("_key"), StringExpr("hello")]


def test_match_multiple_comparison_functions():
    ast = parse_opium(
        "get('users-data-product.user_roles').match(gt('age', 48), lte('age', 85))"
    )

    assert [condition.function for condition in ast.root.args] == ["gt", "lte"]
    assert ast.root.args[0].args[1] == NumberExpr(48)


def test_match_binary_comparison():
    ast = parse_opium("get('users-data-product.user_roles').match(age > 48, age <= 85)")

    first = ast.root.args[0]
    assert isinstance(first, BinaryOpExpr)
    assert first.left == NameExpr("age")
    assert first.op == ">"
    assert first.right == NumberExpr(48)


def test_match_ne():
    ast = parse_opium("get('users-data-product.user_roles').match(ne('_key', 'hello'))")

    condition = ast.root.args[0]
    assert isinstance(condition, CallExpr)
    assert condition.function == "ne"


def test_match_value_in():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".match(value_in('_key', ['one', 'two', 'three']))"
    )

    condition = ast.root.args[0]
    assert isinstance(condition, CallExpr)
    assert condition.function == "value_in"
    assert isinstance(condition.args[1], ListExpr)
    assert condition.args[1].items == [
        StringExpr("one"),
        StringExpr("two"),
        StringExpr("three"),
    ]


def test_match_nin():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".match(nin('_key', ['one', 'two', 'three']))"
    )

    assert ast.root.args[0].function == "nin"


def test_match_is_null():
    ast = parse_opium(
        "get('users-data-product.user_roles').match(is_null('non_existent_field'))"
    )

    assert ast.root.args[0].function == "is_null"


def test_match_regex_matches():
    ast = parse_opium(
        "get('users-data-product.user_roles')"
        ".match(regex_matches('_key', '^hello', caseInsensitive=True))"
    )

    condition = ast.root.args[0]
    assert condition.function == "regex_matches"
    assert condition.kwargs["caseInsensitive"].value is True


def test_match_all_call():
    ast = parse_opium("match_all(eq('_key', 'one'), eq('name', 'two'))")

    assert isinstance(ast.root, CallExpr)
    assert ast.root.function == "match_all"
    assert len(ast.root.args) == 2

