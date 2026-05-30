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

