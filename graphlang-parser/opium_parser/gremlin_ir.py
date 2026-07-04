"""Small Pydantic IR for Gremlin Groovy traversal strings."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from opium_parser.types import GremlinGroovyString

CursorKind = Literal["vertex", "edge", "scalar", "map", "list", "unknown"]
EdgeDirection = Literal["any", "outbound", "inbound"]


class GremlinTraversal(BaseModel):
    """Append-only builder for a Gremlin Groovy traversal.

    This is deliberately not a complete Gremlin AST. It gives the compiler a
    typed place to accumulate Groovy fragments and a future replacement point for
    bytecode or a richer IR.
    """

    model_config = ConfigDict(extra="forbid")

    start: str
    steps: list[str] = Field(default_factory=list)
    cursor_kind: CursorKind = "unknown"
    edge_direction: EdgeDirection | None = None

    def __init__(self, start: str | None = None, **data: Any) -> None:
        if start is not None:
            data["start"] = start
        super().__init__(**data)

    def add(self, step: str) -> None:
        self.steps.append(step)

    def extend(self, steps: list[str]) -> None:
        self.steps.extend(steps)

    def set_cursor(
        self,
        kind: CursorKind,
        *,
        edge_direction: EdgeDirection | None = None,
    ) -> None:
        self.cursor_kind = kind
        self.edge_direction = edge_direction

    def render(self) -> GremlinGroovyString:
        return GremlinGroovyString("".join([self.start, *self.steps]))
