import pytest

from opium_parser import parse_opium
from opium_parser.errors import InvalidOpiumExpressionError, UnsupportedOpiumSyntaxError


def test_unknown_function_error_detail():
    with pytest.raises(UnsupportedOpiumSyntaxError) as exc_info:
        parse_opium("unknown('x')")

    detail = exc_info.value.detail
    assert detail.code == "syntax.unsupported_call"
    assert detail.stage == "transform"
    assert detail.actual == "unknown"
    assert "get" in detail.expected


def test_duplicate_keyword_error_detail():
    with pytest.raises(InvalidOpiumExpressionError) as exc_info:
        parse_opium("get('x', _key='one', _key='two')")

    detail = exc_info.value.detail
    assert detail.code == "syntax.duplicate_kwarg"
    assert detail.stage == "transform"
    assert detail.context["kwarg"] == "_key"


def test_positional_after_keyword_error_detail():
    with pytest.raises(InvalidOpiumExpressionError) as exc_info:
        parse_opium("get('x', _key='one', 'two')")

    assert exc_info.value.detail.code == "syntax.positional_after_keyword"


def test_unexpected_token_error_detail_has_best_effort_span():
    with pytest.raises(UnsupportedOpiumSyntaxError) as exc_info:
        parse_opium("get('x').limit(1 + 2)")

    detail = exc_info.value.detail
    assert detail.code == "syntax.unexpected_token"
    assert detail.stage == "parse"
    assert detail.span is not None
    assert detail.span.line == 1
    assert detail.span.column > 0


def test_invalid_subscript_error_detail():
    with pytest.raises(UnsupportedOpiumSyntaxError) as exc_info:
        parse_opium("get('x')[0]")

    detail = exc_info.value.detail
    assert detail.code == "syntax.invalid_subscript"
    assert detail.expected == ("NAME", "STRING")
