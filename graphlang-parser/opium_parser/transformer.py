from __future__ import annotations

import ast
from typing import Any, Literal, cast

from lark import Token, Transformer, v_args
from pydantic import BaseModel, ConfigDict

from opium_parser.ast_nodes import (
    BinaryOpExpr,
    BooleanExpr,
    CallExpr,
    DictExpr,
    Expr,
    ExprNode,
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
from opium_parser.opium_names import parse_call_name


class _TransformerValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _KeywordArg(_TransformerValue):
    """Temporary transformer value for a parsed keyword argument."""

    name: str
    value: ExprNode


class _MethodTrailer(_TransformerValue):
    """Temporary transformer value for `.method(...)` before receiver binding."""

    method: str
    args: list[ExprNode]
    kwargs: dict[str, ExprNode]


class _SubscriptTrailer(_TransformerValue):
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
        return Query(root=cast(ExprNode, children[0]))

    def chain(self, children: list[Any]) -> Expr:
        expr = cast(ExprNode, children[0])
        for trailer in children[1:]:
            if isinstance(trailer, _MethodTrailer):
                method = parse_call_name(trailer.method)
                expr = MethodCallExpr(
                    receiver=expr,
                    method=method,
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
        function = parse_call_name(str(children[0]))
        args, kwargs = cast(tuple[list[ExprNode], dict[str, ExprNode]], children[1])
        return CallExpr(function=function, args=args, kwargs=kwargs)

    def call_args(
        self, children: list[Any]
    ) -> tuple[list[ExprNode], dict[str, ExprNode]]:
        if not children:
            return [], {}
        return cast(tuple[list[ExprNode], dict[str, ExprNode]], children[0])

    def arguments(
        self, children: list[Any]
    ) -> tuple[list[ExprNode], dict[str, ExprNode]]:
        args: list[ExprNode] = []
        kwargs: dict[str, ExprNode] = {}
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
                args.append(cast(ExprNode, child))

        return args, kwargs

    def kwarg(self, children: list[Any]) -> _KeywordArg:
        return _KeywordArg(name=str(children[0]), value=cast(ExprNode, children[1]))

    def method_trailer(self, children: list[Any]) -> _MethodTrailer:
        method = str(children[0])
        args, kwargs = cast(tuple[list[ExprNode], dict[str, ExprNode]], children[1])
        return _MethodTrailer(method=method, args=args, kwargs=kwargs)

    def subscript_trailer(self, children: list[Any]) -> _SubscriptTrailer:
        return _SubscriptTrailer(field=cast(str, children[0]))

    def string_field(self, children: list[Any]) -> str:
        return _decode_string(children[0])

    def identifier_field(self, children: list[Any]) -> str:
        return str(children[0])

    def binary_expr(self, children: list[Any]) -> BinaryOpExpr:
        op = cast(Literal["==", "!=", "<", ">", "<=", ">="], str(children[1]))
        return BinaryOpExpr(
            left=cast(ExprNode, children[0]),
            op=op,
            right=cast(ExprNode, children[2]),
        )

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
        return ListExpr(items=cast(list[ExprNode], items))

    def expr_list(self, children: list[Any]) -> list[ExprNode]:
        return cast(list[ExprNode], children)

    def dict_expr(self, children: list[Any]) -> DictExpr:
        pairs = cast(list[tuple[str, ExprNode]], children[0] if children else [])
        items: dict[str, ExprNode] = {}
        for key, value in pairs:
            if key in items:
                msg = f"Duplicate dict key: {key}"
                raise InvalidOpiumExpressionError(msg)
            items[key] = value
        return DictExpr(items=items)

    def dict_items(self, children: list[Any]) -> list[tuple[str, ExprNode]]:
        return cast(list[tuple[str, ExprNode]], children)

    def dict_item(self, children: list[Any]) -> tuple[str, ExprNode]:
        return str(children[0]), cast(ExprNode, children[1])

    def string_key(self, children: list[Any]) -> str:
        return _decode_string(children[0])

    def identifier_key(self, children: list[Any]) -> str:
        return str(children[0])

    @v_args(inline=True)
    def COMP_OP(self, token: Token) -> str:  # noqa: N802
        return str(token)


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
