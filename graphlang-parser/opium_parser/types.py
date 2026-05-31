"""Domain-specific types used by the parser and compiler.

The compiler currently returns Gremlin Groovy source code, not an arbitrary
string and not Gremlin Python bytecode. `NewType` keeps that distinction visible
to static type checkers while remaining a plain `str` at runtime.
"""

from __future__ import annotations

from typing import NewType

GremlinGroovyString = NewType("GremlinGroovyString", str)
GremlinGroovyFragment = NewType("GremlinGroovyFragment", str)
