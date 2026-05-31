"""Small Pydantic IR for Gremlin Groovy traversal strings."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from opium_parser.types import GremlinGroovyString


class GremlinTraversal(BaseModel):
    """Append-only builder for a Gremlin Groovy traversal.

    This is deliberately not a complete Gremlin AST. It gives the compiler a
    typed place to accumulate Groovy fragments and a future replacement point for
    bytecode or a richer IR.
    """

    model_config = ConfigDict(extra="forbid")

    start: str
    steps: list[str] = Field(default_factory=list)

    def __init__(self, start: str | None = None, **data: Any) -> None:
        if start is not None:
            data["start"] = start
        super().__init__(**data)

    def add(self, step: str) -> None:
        self.steps.append(step)

    def extend(self, steps: list[str]) -> None:
        self.steps.extend(steps)

    def render(self) -> GremlinGroovyString:
        return GremlinGroovyString("".join([self.start, *self.steps]))
