from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GremlinTraversal:
    """Small string-building IR for Gremlin Groovy traversals.

    This is deliberately not a complete Gremlin AST. At this stage the compiler
    emits Gremlin Groovy strings, and most decisions are linear traversal steps.
    Keeping a tiny append-only object makes the compiler easier to read while
    preserving an obvious future replacement point for Gremlin Python bytecode or
    a richer internal IR.
    """

    start: str
    steps: list[str] = field(default_factory=list)

    def add(self, step: str) -> None:
        self.steps.append(step)

    def extend(self, steps: list[str]) -> None:
        self.steps.extend(steps)

    def render(self) -> str:
        return "".join([self.start, *self.steps])
