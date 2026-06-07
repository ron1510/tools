import pytest

from opium_parser import parse_opium
from opium_parser.errors import InvalidOpiumExpressionError, UnsupportedOpiumSyntaxError


def test_unsupported_lambda():
    with pytest.raises(UnsupportedOpiumSyntaxError):
        parse_opium("get('x').match(lambda x: x)")


def test_unknown_function():
    with pytest.raises(UnsupportedOpiumSyntaxError):
        parse_opium("unknown('x')")


def test_unknown_method():
    with pytest.raises(UnsupportedOpiumSyntaxError):
        parse_opium("get('x').unknown()")


def test_arithmetic_is_rejected():
    with pytest.raises(UnsupportedOpiumSyntaxError):
        parse_opium("get('x').limit(1 + 2)")


def test_assignment_is_rejected():
    with pytest.raises(UnsupportedOpiumSyntaxError):
        parse_opium("x = get('x')")


def test_import_is_rejected():
    with pytest.raises(UnsupportedOpiumSyntaxError):
        parse_opium("import os")


def test_comprehension_is_rejected():
    with pytest.raises(UnsupportedOpiumSyntaxError):
        parse_opium("[x for x in y]")


def test_positional_after_keyword_is_rejected():
    with pytest.raises(InvalidOpiumExpressionError):
        parse_opium("get('x', _key='one', 'two')")


def test_numeric_subscript_is_rejected():
    with pytest.raises(UnsupportedOpiumSyntaxError):
        parse_opium("get('x')[0]")
