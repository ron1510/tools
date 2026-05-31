"""Typed Pydantic syntax tree for the Opium expression language.

The AST models Opium syntax, not Gremlin behavior. For example,
`CallExpr(function="get", ...)` says the user wrote `get(...)`; it does not say
whether that should become `g.V()`, `g.E()`, or `hasLabel(...)`.

All nodes are frozen Pydantic models. That gives us:

- explicit typed fields
- stable equality for tests
- JSON/model serialization via `model_dump()` / `model_dump_json()`
- runtime validation when constructing AST nodes
- a clean future path for API responses or persisted query plans
"""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from opium_parser.opium_names import OpiumCallName


class OpiumAstModel(BaseModel):
    """Common strict configuration for all AST models."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class Expr(OpiumAstModel):
    """Marker base class for all typed Opium expression nodes."""


class CallExpr(Expr):
    """A direct function call such as `get('users')` or `eq('_key', 'x')`."""

    kind: Literal["call"] = "call"
    function: OpiumCallName
    args: list[ExprNode] = Field(default_factory=list)
    kwargs: dict[str, ExprNode] = Field(default_factory=dict)


class MethodCallExpr(Expr):
    """A chained method call such as `get('users').limit(10)`."""

    kind: Literal["method_call"] = "method_call"
    receiver: ExprNode
    method: OpiumCallName
    args: list[ExprNode] = Field(default_factory=list)
    kwargs: dict[str, ExprNode] = Field(default_factory=dict)


class SubscriptExpr(Expr):
    """Projection syntax such as `get('users')['_key']`."""

    kind: Literal["subscript"] = "subscript"
    receiver: ExprNode
    field: str


class NameExpr(Expr):
    """A bare identifier, usually a field name in comparison expressions."""

    kind: Literal["name"] = "name"
    name: str


class StringExpr(Expr):
    kind: Literal["string"] = "string"
    value: str


class NumberExpr(Expr):
    kind: Literal["number"] = "number"
    value: int | float


class BooleanExpr(Expr):
    kind: Literal["boolean"] = "boolean"
    value: bool


class NullExpr(Expr):
    kind: Literal["null"] = "null"


class ListExpr(Expr):
    kind: Literal["list"] = "list"
    items: list[ExprNode] = Field(default_factory=list)


class DictExpr(Expr):
    """A simple dictionary literal."""

    kind: Literal["dict"] = "dict"
    items: dict[str, ExprNode] = Field(default_factory=dict)


class BinaryOpExpr(Expr):
    """A comparison expression such as `age >= 48`."""

    kind: Literal["binary_op"] = "binary_op"
    left: ExprNode
    op: Literal["==", "!=", "<", ">", "<=", ">="]
    right: ExprNode


ExprNode: TypeAlias = Annotated[
    CallExpr
    | MethodCallExpr
    | SubscriptExpr
    | NameExpr
    | StringExpr
    | NumberExpr
    | BooleanExpr
    | NullExpr
    | ListExpr
    | DictExpr
    | BinaryOpExpr,
    Field(discriminator="kind"),
]


class Query(OpiumAstModel):
    """A complete Opium expression."""

    root: ExprNode


for _model in (
    CallExpr,
    MethodCallExpr,
    SubscriptExpr,
    ListExpr,
    DictExpr,
    BinaryOpExpr,
    Query,
):
    _model.model_rebuild()
