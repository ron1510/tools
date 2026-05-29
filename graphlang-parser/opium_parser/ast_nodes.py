"""Typed syntax tree for the Opium expression language.

These dataclasses intentionally model syntax, not Gremlin behavior. For example,
`CallExpr(function="get", ...)` says that the user wrote `get(...)`; it does not
say whether that call should become `g.V()`, `g.E()`, `hasLabel(...)`, or
anything else. That separation keeps parsing stable while compiler semantics are
still being refined.

The nodes are frozen so tests and compiler code can treat an AST as immutable
input. Lists and dictionaries inside the nodes are still normal Python
containers because that keeps construction simple and readable; the project does
not mutate them after construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Query:
    """A complete Opium expression.

    The grammar accepts one expression at the top level. The root can be a
    function call, method-call chain, projection, literal, or comparison AST
    depending on what the user wrote. The compiler currently supports only roots
    that can be interpreted as traversals.
    """

    root: Expr


class Expr:
    """Marker base class for all typed Opium expression nodes."""

    pass


@dataclass(frozen=True)
class CallExpr(Expr):
    """A direct function call such as `get('users')` or `eq('_key', 'x')`."""

    function: str
    args: list[Expr]
    kwargs: dict[str, Expr]


@dataclass(frozen=True)
class MethodCallExpr(Expr):
    """A chained method call such as `get('users').limit(10)`.

    Method calls keep their receiver as another expression. A long Opium chain is
    therefore represented as nested receiver nodes, with the final method at the
    root of the chain.
    """

    receiver: Expr
    method: str
    args: list[Expr]
    kwargs: dict[str, Expr]


@dataclass(frozen=True)
class SubscriptExpr(Expr):
    """Projection syntax such as `get('users')['_key']`.

    The parser only stores the requested field name here. It does not decide
    whether the field is a normal property, an Arango system field, or a computed
    provider-specific value.
    """

    receiver: Expr
    field: str


@dataclass(frozen=True)
class NameExpr(Expr):
    """A bare identifier.

    Bare names are mainly useful in documented comparison forms such as
    `match(age > 48)`, where `age` is a field name rather than a Python variable.
    """

    name: str


@dataclass(frozen=True)
class StringExpr(Expr):
    value: str


@dataclass(frozen=True)
class NumberExpr(Expr):
    value: int | float


@dataclass(frozen=True)
class BooleanExpr(Expr):
    value: bool


@dataclass(frozen=True)
class NullExpr(Expr):
    pass


@dataclass(frozen=True)
class ListExpr(Expr):
    items: list[Expr]


@dataclass(frozen=True)
class DictExpr(Expr):
    """A simple dictionary literal.

    Dict literals are parsed so the grammar can represent documented value
    syntax without becoming arbitrary Python. The compiler currently has no
    broad semantic use for dictionaries.
    """

    items: dict[str, Expr]


@dataclass(frozen=True)
class BinaryOpExpr(Expr):
    """A comparison expression such as `age >= 48`.

    Arithmetic is intentionally not represented. If we later support arithmetic,
    it should be added as explicit AST nodes instead of smuggling Python syntax
    through the parser.
    """

    left: Expr
    op: Literal["==", "!=", "<", ">", "<=", ">="]
    right: Expr
