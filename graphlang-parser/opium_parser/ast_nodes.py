from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Query:
    root: Expr


class Expr:
    pass


@dataclass(frozen=True)
class CallExpr(Expr):
    function: str
    args: list[Expr]
    kwargs: dict[str, Expr]


@dataclass(frozen=True)
class MethodCallExpr(Expr):
    receiver: Expr
    method: str
    args: list[Expr]
    kwargs: dict[str, Expr]


@dataclass(frozen=True)
class SubscriptExpr(Expr):
    receiver: Expr
    field: str


@dataclass(frozen=True)
class NameExpr(Expr):
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
    items: dict[str, Expr]


@dataclass(frozen=True)
class BinaryOpExpr(Expr):
    left: Expr
    op: Literal["==", "!=", "<", ">", "<=", ">="]
    right: Expr

