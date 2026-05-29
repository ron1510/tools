from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from lark import Token, Transformer, v_args

from opium_parser.ast_nodes import (
    BinaryOpExpr,
    BooleanExpr,
    CallExpr,
    DictExpr,
    Expr,
    ListExpr,
    MethodCallExpr,
    NameExpr,
    NullExpr,
    NumberExpr,
    Query,
    StringExpr,
    SubscriptExpr,
)
from opium_parser.errors import (
    InvalidOpiumExpressionError,
    UnsupportedOpiumSyntaxError,
)

# Function/method allow-list for the Opium grammar.
#
# The grammar can recognize generic `NAME(...)` calls, but this transformer
# narrows them to documented Opium names. This is where we reject expressions
# like `open(...)`, `lambda`, or random helper calls before they can reach a
# compiler.
#
# The allow-list is parser-level, not compiler-level: a name can be valid Opium
# syntax even if the current Gremlin compiler still rejects some semantic
# shapes.
ALLOWED_CALL_NAMES = frozenset(
    {
        "get",
        "traverse",
        "traverse_any",
        "traverse_out",
        "traverse_in",
        "into",
        "skip",
        "limit",
        "count",
        "array",
        "flatten",
        "as_var",
        "var",
        "assign",
        "select",
        "unique",
        "match",
        "match_all",
        "match_any",
        "eq",
        "lt",
        "gt",
        "lte",
        "gte",
        "ne",
        "value_in",
        "nin",
        "is_null",
        "regex_matches",
    }
)


@dataclass(frozen=True)
class _KeywordArg:
    """Temporary transformer value for a parsed keyword argument."""

    name: str
    value: Expr


@dataclass(frozen=True)
class _MethodTrailer:
    """Temporary transformer value for `.method(...)` before receiver binding."""

    method: str
    args: list[Expr]
    kwargs: dict[str, Expr]


@dataclass(frozen=True)
class _SubscriptTrailer:
    """Temporary transformer value for `[field]` before receiver binding."""

    field: str


class OpiumTransformer(Transformer[Any, Query | Expr]):
    """Convert Lark parse trees into the typed Opium AST.

    Lark first parses a chain as one atom plus a list of trailers. The
    transformer then folds those trailers left-to-right so
    `get('x').limit(1)['_key']` becomes:

    `SubscriptExpr(MethodCallExpr(CallExpr(...), "limit", ...), "_key")`.
    """

    def start(self, children: list[Any]) -> Query:
        return Query(root=children[0])

    def chain(self, children: list[Any]) -> Expr:
        expr = children[0]
        for trailer in children[1:]:
            if isinstance(trailer, _MethodTrailer):
                self._validate_call_name(trailer.method)
                expr = MethodCallExpr(
                    receiver=expr,
                    method=trailer.method,
                    args=trailer.args,
                    kwargs=trailer.kwargs,
                )
            elif isinstance(trailer, _SubscriptTrailer):
                expr = SubscriptExpr(receiver=expr, field=trailer.field)
            else:
                msg = f"Unsupported trailer: {trailer!r}"
                raise UnsupportedOpiumSyntaxError(msg)
        return expr

    def call(self, children: list[Any]) -> CallExpr:
        function = str(children[0])
        self._validate_call_name(function)
        args, kwargs = children[1]
        return CallExpr(function=function, args=args, kwargs=kwargs)

    def call_args(self, children: list[Any]) -> tuple[list[Expr], dict[str, Expr]]:
        if not children:
            return [], {}
        return children[0]

    def arguments(self, children: list[Any]) -> tuple[list[Expr], dict[str, Expr]]:
        args: list[Expr] = []
        kwargs: dict[str, Expr] = {}
        seen_keyword = False

        for child in children:
            if isinstance(child, _KeywordArg):
                # Python-style argument ordering is part of the documented Opium
                # syntax, but we enforce it ourselves so duplicate and
                # positional-after-keyword errors become custom Opium errors.
                seen_keyword = True
                if child.name in kwargs:
                    msg = f"Duplicate keyword argument: {child.name}"
                    raise InvalidOpiumExpressionError(msg)
                kwargs[child.name] = child.value
            else:
                if seen_keyword:
                    msg = "Positional arguments cannot follow keyword arguments"
                    raise InvalidOpiumExpressionError(msg)
                args.append(child)

        return args, kwargs

    def kwarg(self, children: list[Any]) -> _KeywordArg:
        return _KeywordArg(name=str(children[0]), value=children[1])

    def method_trailer(self, children: list[Any]) -> _MethodTrailer:
        method = str(children[0])
        args, kwargs = children[1]
        return _MethodTrailer(method=method, args=args, kwargs=kwargs)

    def subscript_trailer(self, children: list[Any]) -> _SubscriptTrailer:
        return _SubscriptTrailer(field=children[0])

    def string_field(self, children: list[Any]) -> str:
        return _decode_string(children[0])

    def identifier_field(self, children: list[Any]) -> str:
        return str(children[0])

    def binary_expr(self, children: list[Any]) -> BinaryOpExpr:
        return BinaryOpExpr(left=children[0], op=str(children[1]), right=children[2])

    def name_expr(self, children: list[Any]) -> NameExpr:
        return NameExpr(name=str(children[0]))

    def string_expr(self, children: list[Any]) -> StringExpr:
        return StringExpr(value=_decode_string(children[0]))

    def number_expr(self, children: list[Any]) -> NumberExpr:
        text = str(children[0])
        if any(marker in text for marker in (".", "e", "E")):
            return NumberExpr(value=float(text))
        return NumberExpr(value=int(text))

    def true_expr(self, _children: list[Any]) -> BooleanExpr:
        return BooleanExpr(value=True)

    def false_expr(self, _children: list[Any]) -> BooleanExpr:
        return BooleanExpr(value=False)

    def null_expr(self, _children: list[Any]) -> NullExpr:
        return NullExpr()

    def list_expr(self, children: list[Any]) -> ListExpr:
        items = children[0] if children else []
        return ListExpr(items=items)

    def expr_list(self, children: list[Any]) -> list[Expr]:
        return children

    def dict_expr(self, children: list[Any]) -> DictExpr:
        pairs = children[0] if children else []
        items: dict[str, Expr] = {}
        for key, value in pairs:
            if key in items:
                msg = f"Duplicate dict key: {key}"
                raise InvalidOpiumExpressionError(msg)
            items[key] = value
        return DictExpr(items=items)

    def dict_items(self, children: list[Any]) -> list[tuple[str, Expr]]:
        return children

    def dict_item(self, children: list[Any]) -> tuple[str, Expr]:
        return children[0], children[1]

    def string_key(self, children: list[Any]) -> str:
        return _decode_string(children[0])

    def identifier_key(self, children: list[Any]) -> str:
        return str(children[0])

    @v_args(inline=True)
    def COMP_OP(self, token: Token) -> str:  # noqa: N802
        return str(token)

    def _validate_call_name(self, name: str) -> None:
        if name not in ALLOWED_CALL_NAMES:
            msg = f"Unsupported Opium function or method: {name}"
            raise UnsupportedOpiumSyntaxError(msg)


def _decode_string(token: Token) -> str:
    """Decode a grammar-approved string literal.

    `ast.literal_eval` is used only after the Lark grammar has matched a single
    string token. This gives correct escape handling for both `'...'` and
    `"..."` without executing arbitrary code.
    """

    value = ast.literal_eval(str(token))
    if not isinstance(value, str):
        msg = f"Expected string literal, got {token}"
        raise InvalidOpiumExpressionError(msg)
    return value
