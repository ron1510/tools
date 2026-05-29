from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GremlinTraversal:
    start: str
    steps: list[str] = field(default_factory=list)

    def add(self, step: str) -> None:
        self.steps.append(step)

    def extend(self, steps: list[str]) -> None:
        self.steps.extend(steps)

    def render(self) -> str:
        return "".join([self.start, *self.steps])

