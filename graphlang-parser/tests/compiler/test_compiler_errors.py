import pytest

from opium_parser import compile_opium_to_gremlin
from opium_parser.errors import (
    InvalidOpiumSemanticError,
    UnsupportedOpiumCompilationError,
)


def test_invalid_direction_error_detail():
    with pytest.raises(InvalidOpiumSemanticError) as exc_info:
        compile_opium_to_gremlin("get('users').traverse(direction='sideways')")

    detail = exc_info.value.detail
    assert detail.code == "semantic.invalid_direction"
    assert detail.actual == "sideways"
    assert detail.expected == ("any", "outbound", "inbound")


def test_invalid_depth_range_error_detail():
    with pytest.raises(InvalidOpiumSemanticError) as exc_info:
        compile_opium_to_gremlin("get('users').traverse(min_depth=3, max_depth=2)")

    detail = exc_info.value.detail
    assert detail.code == "semantic.invalid_depth_range"
    assert detail.expected == ("1 <= min_depth <= max_depth",)


def test_invalid_limit_type_error_detail():
    with pytest.raises(InvalidOpiumSemanticError) as exc_info:
        compile_opium_to_gremlin("get('users').limit(1.5)")

    detail = exc_info.value.detail
    assert detail.code == "semantic.invalid_argument_type"
    assert detail.context["method"] == "limit"


def test_unknown_kwarg_error_detail():
    with pytest.raises(InvalidOpiumSemanticError) as exc_info:
        compile_opium_to_gremlin("get('users').into(extra=True)")

    detail = exc_info.value.detail
    assert detail.code == "semantic.unknown_kwarg"
    assert detail.actual == "extra"


def test_unsupported_child_get_error_detail():
    with pytest.raises(UnsupportedOpiumCompilationError) as exc_info:
        compile_opium_to_gremlin("get('users').array(get('roles'))")

    detail = exc_info.value.detail
    assert detail.code == "compile.unsupported_root"
    assert detail.context == {"function": "get", "position": "child"}


def test_unsupported_select_expression_error_detail():
    with pytest.raises(UnsupportedOpiumCompilationError) as exc_info:
        compile_opium_to_gremlin("get('users').select(is_admin=active == True)")

    assert exc_info.value.detail.code == "compile.unsupported_select_expression"


def test_non_numeric_count_comparison_error_detail():
    with pytest.raises(InvalidOpiumSemanticError) as exc_info:
        compile_opium_to_gremlin("get('users').match(traverse().into().count() == '3')")

    assert exc_info.value.detail.code == "semantic.invalid_count_comparison"


def test_unsupported_key_comparison_error_detail():
    with pytest.raises(InvalidOpiumSemanticError) as exc_info:
        compile_opium_to_gremlin("get('users').match(_key > 'admin')")

    detail = exc_info.value.detail
    assert detail.code == "semantic.unsupported_key_comparison"
    assert detail.context["field"] == "_key"
