"""Public parsing API.

The parser uses Lark to recognize the documented Opium expression subset and a
transformer to convert the parse tree into the typed AST in `ast_nodes.py`.

Important boundary: this module never calls `eval`, `exec`, Python's AST
evaluator, or user code. String literal decoding uses `ast.literal_eval` inside
the transformer only to unescape Python-style string tokens that the grammar has
already recognized.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

from lark import Lark, LarkError
from lark.exceptions import UnexpectedEOF, UnexpectedInput, UnexpectedToken, VisitError

from opium_parser.ast_nodes import Query
from opium_parser.errors import (
    InvalidOpiumExpressionError,
    OpiumParserError,
    OpiumSourceSpan,
    UnsupportedOpiumSyntaxError,
    error_context,
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
        raise _parse_lark_error(exc, source) from exc

    if not isinstance(result, Query):
        msg = "Parser did not produce a Query AST"
        raise InvalidOpiumExpressionError(msg)
    return result


def _parse_lark_error(exc: LarkError, source: str) -> UnsupportedOpiumSyntaxError:
    if isinstance(exc, UnexpectedEOF):
        return UnsupportedOpiumSyntaxError(
            "Unexpected end of Opium expression",
            code="syntax.unexpected_eof",
            stage="parse",
            hint=(
                "Check for a missing closing parenthesis, bracket, quote, or argument."
            ),
            expected=tuple(sorted(str(item) for item in exc.expected)),
        )
    if isinstance(exc, UnexpectedToken):
        code = _unexpected_token_code(source, exc)
        return UnsupportedOpiumSyntaxError(
            "Unexpected token in Opium expression",
            code=code,
            stage="parse",
            span=_source_span(exc),
            expected=tuple(sorted(str(item) for item in exc.expected)),
            actual=str(exc.token),
            context=error_context(token_type=exc.token.type),
        )
    if isinstance(exc, UnexpectedInput):
        return UnsupportedOpiumSyntaxError(
            "Unsupported Opium syntax",
            code="syntax.unexpected_token",
            stage="parse",
            span=_source_span(exc),
            actual=exc.get_context(source).strip(),
        )
    return UnsupportedOpiumSyntaxError(
        str(exc),
        code="syntax.unsupported",
        stage="parse",
    )


def _source_span(exc: UnexpectedInput) -> OpiumSourceSpan | None:
    line = getattr(exc, "line", None)
    column = getattr(exc, "column", None)
    if not isinstance(line, int) or not isinstance(column, int):
        return None
    return OpiumSourceSpan(line=line, column=column)


def _unexpected_token_code(source: str, exc: UnexpectedToken) -> str:
    if {"STRING", "NAME"} <= set(exc.expected) and _inside_subscript(source, exc):
        return "syntax.invalid_subscript"
    return "syntax.unexpected_token"


def _inside_subscript(source: str, exc: UnexpectedToken) -> bool:
    start_pos = getattr(exc.token, "start_pos", None)
    if not isinstance(start_pos, int):
        return False
    prefix = source[:start_pos]
    return prefix.rfind("[") > prefix.rfind("]")


@lru_cache(maxsize=1)
def _parser() -> Lark:
    # The parser is cached because the grammar is static and Lark construction is
    # more expensive than parsing one expression. Keeping this private also
    # leaves room to change parser options without affecting the public API.
    grammar = resources.files("opium_parser").joinpath("grammar.lark").read_text()
    return Lark(grammar, parser="lalr", maybe_placeholders=False)
