from __future__ import annotations

import pytest
from hypothesis import given

from opium_parser import Query, parse_opium

from .strategies import (
    invalid_parser_sources,
    simple_ast_queries,
    valid_parser_sources,
)


@given(simple_ast_queries())
def test_generated_ast_round_trips_through_pydantic(query: Query):
    assert Query.model_validate(query.model_dump()) == query


@given(valid_parser_sources())
def test_generated_valid_sources_parse_and_serialize(source: str):
    query = parse_opium(source)

    assert isinstance(query, Query)
    assert Query.model_validate(query.model_dump()) == query


@given(invalid_parser_sources())
def test_generated_invalid_sources_raise_expected_parser_error(
    case: tuple[str, type[Exception]],
):
    source, expected_error = case

    with pytest.raises(expected_error):
        parse_opium(source)
