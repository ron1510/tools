import pytest

from opium_parser import compile_opium_to_gremlin


@pytest.mark.skip(reason="array semantics are not fully specified yet")
def test_array_per_row_semantics_placeholder():
    compile_opium_to_gremlin("get('users').array(traverse().into())")


@pytest.mark.skip(
    reason="flatten nested-array semantics are not fully specified yet"
)
def test_flatten_depth_semantics_placeholder():
    compile_opium_to_gremlin("get('users').array(traverse().into()).flatten(depth=2)")


@pytest.mark.skip(reason="match subquery operand semantics are not specified yet")
def test_match_subquery_operand_placeholder():
    compile_opium_to_gremlin(
        "get('users').match(eq(traverse().into()['_key'], 'admin'))"
    )


@pytest.mark.skip(reason="match variable operand semantics are not specified yet")
def test_match_variable_operand_placeholder():
    compile_opium_to_gremlin(
        "get('users').as_var('u').match(eq(var('u')['_key'], 'admin'))"
    )
