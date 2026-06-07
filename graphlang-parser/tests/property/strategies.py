from __future__ import annotations

from collections.abc import Callable

from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy

from opium_parser import (
    BinaryOpExpr,
    BooleanExpr,
    CallExpr,
    ListExpr,
    NameExpr,
    NullExpr,
    NumberExpr,
    Query,
    StringExpr,
)
from opium_parser.ast_nodes import ExprNode
from opium_parser.errors import (
    InvalidOpiumExpressionError,
    InvalidOpiumSemanticError,
    UnsupportedOpiumSyntaxError,
)
from opium_parser.opium_names import ALLOWED_CALL_NAMES

ParserError = type[InvalidOpiumExpressionError] | type[UnsupportedOpiumSyntaxError]
CompilerSemanticError = type[InvalidOpiumSemanticError]

RESOURCES = (
    "users",
    "roles",
    "abilities",
    "users-data-product.user_roles",
    "permissions-data-product.abilities",
)
EDGES = (
    "subs",
    "permissions-data-product.role_abilities",
    "users-data-product.user_role_subscriptions",
)
FIELDS = ("_key", "_id", "name", "age", "score", "active", "category")
KEYS = ("admin", "owner", "viewer", "write", "read")


def quoted(value: str) -> str:
    return repr(value)


def resource_sources() -> SearchStrategy[str]:
    return st.sampled_from(RESOURCES).map(quoted)


def edge_sources() -> SearchStrategy[str]:
    return st.sampled_from(EDGES).map(quoted)


def field_sources() -> SearchStrategy[str]:
    return st.sampled_from(FIELDS).map(quoted)


def key_sources() -> SearchStrategy[str]:
    return st.sampled_from(KEYS).map(quoted)


def literal_sources() -> SearchStrategy[str]:
    return st.one_of(
        key_sources(),
        st.integers(min_value=0, max_value=100).map(str),
        st.floats(
            min_value=0,
            max_value=100,
            allow_nan=False,
            allow_infinity=False,
            width=32,
        ).map(lambda value: f"{value:.2f}"),
        st.booleans().map(lambda value: "True" if value else "False"),
        st.sampled_from(("None", "null")),
    )


def simple_ast_queries() -> SearchStrategy[Query]:
    literal_exprs: SearchStrategy[ExprNode] = st.one_of(
        st.sampled_from(KEYS).map(lambda value: StringExpr(value=value)),
        st.integers(min_value=0, max_value=100).map(
            lambda value: NumberExpr(value=value)
        ),
        st.booleans().map(lambda value: BooleanExpr(value=value)),
        st.just(NullExpr()),
    )
    field_exprs: SearchStrategy[ExprNode] = st.sampled_from(FIELDS).map(
        lambda name: NameExpr(name=name)
    )
    list_exprs: SearchStrategy[ExprNode] = st.lists(
        literal_exprs,
        min_size=0,
        max_size=3,
    ).map(lambda items: ListExpr(items=items))
    comparisons: SearchStrategy[ExprNode] = st.builds(
        BinaryOpExpr,
        left=field_exprs,
        op=st.sampled_from(("==", "!=", "<", ">", "<=", ">=")),
        right=literal_exprs,
    )
    calls: SearchStrategy[ExprNode] = st.builds(
        CallExpr,
        function=st.sampled_from(("get", "var", "eq", "gt", "value_in")),
        args=st.lists(st.one_of(literal_exprs, list_exprs), min_size=0, max_size=2),
        kwargs=st.dictionaries(
            keys=st.sampled_from(("_key", "name", "active")),
            values=literal_exprs,
            max_size=2,
        ),
    )
    return st.one_of(literal_exprs, list_exprs, comparisons, calls).map(
        lambda root: Query(root=root)
    )


def valid_parser_sources() -> SearchStrategy[str]:
    get = resource_sources().map(lambda resource: f"get({resource})")
    get_key = st.builds(
        lambda resource, key: f"get({resource}, _key={key})",
        resource_sources(),
        key_sources(),
    )
    traversal = st.builds(
        lambda resource, edge, direction: (
            f"get({resource}).traverse({edge}, direction={quoted(direction)}).into()"
        ),
        resource_sources(),
        edge_sources(),
        st.sampled_from(("any", "outbound", "inbound")),
    )
    pagination = st.builds(
        lambda resource, skip, limit: f"get({resource}).skip({skip}).limit({limit})",
        resource_sources(),
        st.integers(min_value=0, max_value=20),
        st.integers(min_value=1, max_value=20),
    )
    match_keyword = st.builds(
        lambda resource, field, value: f"get({resource}).match({field}={value})",
        resource_sources(),
        st.sampled_from(("name", "active", "score", "category")),
        literal_sources(),
    )
    match_compare = st.builds(
        lambda resource, op, field, value: (
            f"get({resource}).match({op}({field}, {value}))"
        ),
        resource_sources(),
        st.sampled_from(("eq", "ne", "lt", "gt", "lte", "gte")),
        field_sources(),
        literal_sources(),
    )
    projection = st.builds(
        lambda resource, field: f"get({resource})[{field}]",
        resource_sources(),
        field_sources(),
    )
    return st.one_of(
        get,
        get_key,
        traversal,
        pagination,
        match_keyword,
        match_compare,
        projection,
    )


def compiler_supported_sources() -> SearchStrategy[str]:
    traversal = st.builds(
        lambda resource, edge, direction: (
            f"get({resource}).traverse({edge}, direction={quoted(direction)}).into()"
        ),
        resource_sources(),
        edge_sources(),
        st.sampled_from(("any", "outbound", "inbound")),
    )
    match_key = st.builds(
        lambda resource, key: f"get({resource}).match(eq('_key', {key}))",
        resource_sources(),
        key_sources(),
    )
    match_numeric = st.builds(
        lambda resource, op, field, value: (
            f"get({resource}).match({op}({quoted(field)}, {value}))"
        ),
        resource_sources(),
        st.sampled_from(("lt", "gt", "lte", "gte")),
        st.sampled_from(("age", "score")),
        st.integers(min_value=0, max_value=100),
    )
    select = st.builds(
        lambda resource, field: f"get({resource}).select('_key', {field})",
        resource_sources(),
        st.sampled_from(("'name'", "'age'", "'active'")),
    )
    pagination = st.builds(
        lambda resource, skip, limit: (
            f"get({resource}).skip({skip}).limit({limit}).unique().count()"
        ),
        resource_sources(),
        st.integers(min_value=0, max_value=20),
        st.integers(min_value=1, max_value=20),
    )
    array_flatten = st.builds(
        lambda resource, edge, depth: (
            f"get({resource}).array(traverse_out({edge}).into()['_key'])"
            f".flatten(depth={depth})"
        ),
        resource_sources(),
        edge_sources(),
        st.integers(min_value=0, max_value=3),
    )
    assign_count = st.builds(
        lambda resource, edge: (
            f"get({resource}).assign(traverse_any({edge}).into(), 'neighbors').count()"
        ),
        resource_sources(),
        edge_sources(),
    )
    assign_select = st.builds(
        lambda resource, edge: (
            f"get({resource}).assign(traverse_out({edge}).into(), 'neighbors')"
            ".select('_key')"
        ),
        resource_sources(),
        edge_sources(),
    )
    return st.one_of(
        traversal,
        match_key,
        match_numeric,
        select,
        pagination,
        array_flatten,
        assign_count,
        assign_select,
    )


def invalid_parser_sources() -> SearchStrategy[tuple[str, ParserError]]:
    unknown_name = st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz",
        min_size=3,
        max_size=10,
    ).filter(lambda name: name not in ALLOWED_CALL_NAMES)

    return st.one_of(
        unknown_name.map(lambda name: (f"{name}('x')", UnsupportedOpiumSyntaxError)),
        unknown_name.map(
            lambda name: (f"get('x').{name}()", UnsupportedOpiumSyntaxError)
        ),
        st.just(("get('x', _key='one', _key='two')", InvalidOpiumExpressionError)),
        st.just(("get('x', _key='one', 'two')", InvalidOpiumExpressionError)),
        st.just(("get('x').limit(1 + 2)", UnsupportedOpiumSyntaxError)),
        st.just(("get('x')[0]", UnsupportedOpiumSyntaxError)),
        st.just(("get('x').match(lambda x: x)", UnsupportedOpiumSyntaxError)),
    )


def invalid_compiler_sources() -> SearchStrategy[tuple[str, CompilerSemanticError]]:
    bad_direction = st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz",
        min_size=1,
        max_size=10,
    ).filter(lambda value: value not in {"any", "outbound", "inbound"})

    invalid_templates: tuple[
        Callable[[str], str],
        ...,
    ] = (
        lambda value: f"get('users').traverse(direction={quoted(value)})",
        lambda _value: "get('users').traverse(min_depth=3, max_depth=2)",
        lambda _value: "get('users', _key=1)",
        lambda _value: "get('users').limit(1.5)",
        lambda _value: "get('users').skip('1')",
        lambda _value: (
            "get('users').match(regex_matches('name', 'a', caseInsensitive='yes'))"
        ),
        lambda _value: "get('users').match(value_in('_key', 'admin'))",
    )
    return st.builds(
        lambda template, value: (template(value), InvalidOpiumSemanticError),
        st.sampled_from(invalid_templates),
        bad_direction,
    )
