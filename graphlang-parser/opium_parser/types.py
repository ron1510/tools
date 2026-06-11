"""Domain-specific types used by the parser and compiler.

The compiler currently returns Gremlin Groovy source code, not an arbitrary
string and not Gremlin Python bytecode. `NewType` keeps that distinction visible
to static type checkers while remaining a plain `str` at runtime.
"""

from __future__ import annotations

from typing import NewType

from pydantic import BaseModel, ConfigDict

GremlinGroovyString = NewType("GremlinGroovyString", str)
GremlinGroovyFragment = NewType("GremlinGroovyFragment", str)

ResourceName = NewType("ResourceName", str)
ArangoCollectionName = NewType("ArangoCollectionName", str)
FieldName = NewType("FieldName", str)
ProjectionField = NewType("ProjectionField", str)
VariableName = NewType("VariableName", str)
TraversalDirection = NewType("TraversalDirection", str)
MatchOperator = NewType("MatchOperator", str)

NonNegativeInt = NewType("NonNegativeInt", int)
PositiveDepth = NewType("PositiveDepth", int)
LimitCount = NewType("LimitCount", int)
SkipCount = NewType("SkipCount", int)
FlattenDepth = NewType("FlattenDepth", int)


class DepthRange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_depth: PositiveDepth
    max_depth: PositiveDepth
