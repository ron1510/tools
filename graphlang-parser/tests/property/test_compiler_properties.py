from __future__ import annotations

import pytest
from hypothesis import given

from opium_parser import (
    GremlinGroovyString,
    compile_ast_to_gremlin,
    compile_opium_to_gremlin,
    parse_opium,
)

from .strategies import compiler_supported_sources, invalid_compiler_sources


@given(compiler_supported_sources())
def test_generated_supported_sources_compile_consistently(source: str):
    from_source = compile_opium_to_gremlin(source)
    from_ast = compile_ast_to_gremlin(parse_opium(source))

    assert from_source == from_ast
    assert isinstance(from_source, str)
    assert GremlinGroovyString(from_source) == from_source
    assert from_source.startswith("g.V().hasLabel(")
    assert from_source.count("(") == from_source.count(")")
    assert "TODO" not in from_source
    assert "PLACEHOLDER" not in from_source


@given(invalid_compiler_sources())
def test_generated_invalid_semantic_sources_raise_expected_compiler_error(
    case: tuple[str, type[Exception]],
):
    source, expected_error = case

    with pytest.raises(expected_error):
        compile_opium_to_gremlin(source)
