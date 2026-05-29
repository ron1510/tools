from __future__ import annotations

from opium_parser.ast_nodes import (
    BooleanExpr,
    Expr,
    ListExpr,
    NullExpr,
    NumberExpr,
    StringExpr,
)
from opium_parser.errors import InvalidOpiumSemanticError


def quote_groovy(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def render_literal(expr: Expr) -> str:
    if isinstance(expr, StringExpr):
        return quote_groovy(expr.value)
    if isinstance(expr, NumberExpr):
        return str(expr.value)
    if isinstance(expr, BooleanExpr):
        return "true" if expr.value else "false"
    if isinstance(expr, NullExpr):
        return "null"
    if isinstance(expr, ListExpr):
        return "[" + ", ".join(render_literal(item) for item in expr.items) + "]"

    msg = f"Expected a literal value, got {type(expr).__name__}"
    raise InvalidOpiumSemanticError(msg)


def render_label_args(labels: list[str]) -> str:
    return ", ".join(quote_groovy(label) for label in labels)


def render_predicate(name: str, value: Expr) -> str:
    return f"P.{name}({render_literal(value)})"


def render_within(name: str, value: Expr) -> str:
    if not isinstance(value, ListExpr):
        msg = f"{name} expects a list literal"
        raise InvalidOpiumSemanticError(msg)
    values = ", ".join(render_literal(item) for item in value.items)
    return f"P.{name}({values})"

