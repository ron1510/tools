from __future__ import annotations

from functools import lru_cache
from importlib import resources

from lark import Lark, LarkError
from lark.exceptions import VisitError

from opium_parser.ast_nodes import Query
from opium_parser.errors import (
    InvalidOpiumExpressionError,
    OpiumParserError,
    UnsupportedOpiumSyntaxError,
)
from opium_parser.transformer import OpiumTransformer


def parse_opium(source: str) -> Query:
    """Parse an Opium expression into a typed AST.

    The parser recognizes the documented Opium expression subset only. It never
    evaluates or executes user-provided input.
    """
    try:
        tree = _parser().parse(source)
        result = OpiumTransformer().transform(tree)
    except VisitError as exc:
        if isinstance(exc.orig_exc, OpiumParserError):
            raise exc.orig_exc from exc
        raise UnsupportedOpiumSyntaxError(str(exc.orig_exc)) from exc
    except LarkError as exc:
        raise UnsupportedOpiumSyntaxError(str(exc)) from exc

    if not isinstance(result, Query):
        msg = "Parser did not produce a Query AST"
        raise InvalidOpiumExpressionError(msg)
    return result


@lru_cache(maxsize=1)
def _parser() -> Lark:
    grammar = resources.files("opium_parser").joinpath("grammar.lark").read_text()
    return Lark(grammar, parser="lalr", maybe_placeholders=False)

