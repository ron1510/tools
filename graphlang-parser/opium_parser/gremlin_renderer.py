"""Rendering helpers for Gremlin Groovy fragments.

These helpers are intentionally small and boring. The compiler decides what a
piece of Opium means; this module only serializes already-decided labels,
literals, and predicates into Gremlin Groovy text.
"""

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
    """Return a single-quoted Groovy string literal.

    Opium examples use both single and double quotes, but the compiler normalizes
    to single-quoted Groovy. Escaping is limited to the characters that would
    break the generated string literal.
    """

    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def render_literal(expr: Expr) -> str:
    """Render a literal AST node as a Gremlin Groovy literal.

    Floats are suffixed with `d` on purpose. Plain Groovy decimal literals such
    as `90.0` are `BigDecimal`, and the current ArangoDB TinkerPop Provider
    rejects `BigDecimal` predicate values. Rendering `90.0d` forces a Java
    double, which the provider accepts in live e2e tests.
    """

    if isinstance(expr, StringExpr):
        return quote_groovy(expr.value)
    if isinstance(expr, NumberExpr):
        if isinstance(expr.value, float):
            return f"{expr.value!r}d"
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
