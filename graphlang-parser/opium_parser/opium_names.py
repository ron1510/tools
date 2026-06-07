from __future__ import annotations

from typing import Final, NewType

from opium_parser.errors import UnsupportedOpiumSyntaxError, error_context

OpiumCallName = NewType("OpiumCallName", str)

ALLOWED_CALL_NAMES: Final[frozenset[str]] = frozenset(
    {
        "get",
        "traverse",
        "traverse_any",
        "traverse_out",
        "traverse_in",
        "into",
        "skip",
        "limit",
        "count",
        "array",
        "flatten",
        "as_var",
        "var",
        "assign",
        "select",
        "unique",
        "match",
        "match_all",
        "match_any",
        "eq",
        "lt",
        "gt",
        "lte",
        "gte",
        "ne",
        "value_in",
        "nin",
        "is_null",
        "regex_matches",
    }
)


def parse_call_name(name: str) -> OpiumCallName:
    if name not in ALLOWED_CALL_NAMES:
        msg = f"Unsupported Opium function or method: {name}"
        raise UnsupportedOpiumSyntaxError(
            msg,
            code="syntax.unsupported_call",
            stage="transform",
            expected=tuple(sorted(ALLOWED_CALL_NAMES)),
            actual=name,
            context=error_context(name=name),
        )
    return OpiumCallName(name)
