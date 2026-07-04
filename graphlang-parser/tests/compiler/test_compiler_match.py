import pytest

from opium_parser import compile_opium_to_gremlin
from opium_parser.errors import InvalidOpiumSemanticError
from tests.compiler.expected_gremlin import OUT_VERTEX_STEP


def test_compile_match_keyword_equality():
    assert (
        compile_opium_to_gremlin("get('users').match(_key='hello', name='goodbye')")
        == "g.V().hasLabel('users')"
        ".hasId(TextP.endingWith('/hello')).has('name', 'goodbye')"
    )


def test_compile_match_comparison_calls():
    assert (
        compile_opium_to_gremlin("get('users').match(gt('age', 48), lte('age', 85))")
        == "g.V().hasLabel('users').has('age', P.gt(48)).has('age', P.lte(85))"
    )


def test_compile_match_binary_comparison():
    assert (
        compile_opium_to_gremlin("get('users').match(age > 48, age <= 85)")
        == "g.V().hasLabel('users').has('age', P.gt(48)).has('age', P.lte(85))"
    )


def test_compile_float_literals_as_java_doubles():
    assert (
        compile_opium_to_gremlin("get('users').match(score >= 90.0)")
        == "g.V().hasLabel('users').has('score', P.gte(90.0d))"
    )


def test_compile_match_any():
    assert (
        compile_opium_to_gremlin("get('users').match_any(_key='one', name='two')")
        == "g.V().hasLabel('users')"
        ".or(__.hasId(TextP.endingWith('/one')), __.has('name', 'two'))"
    )


def test_compile_containment():
    assert (
        compile_opium_to_gremlin("get('users').match(value_in('_key', ['one', 'two']))")
        == "g.V().hasLabel('users')"
        ".or(__.hasId(TextP.endingWith('/one')), "
        "__.hasId(TextP.endingWith('/two')))"
    )
    assert (
        compile_opium_to_gremlin("get('users').match(nin('_key', ['one', 'two']))")
        == "g.V().hasLabel('users')"
        ".not(__.or(__.hasId(TextP.endingWith('/one')), "
        "__.hasId(TextP.endingWith('/two'))))"
    )


def test_compile_null_and_regex():
    assert (
        compile_opium_to_gremlin(
            "get('users').match(is_null('missing'), "
            "regex_matches('_key', '^hello', caseInsensitive=True))"
        )
        == "g.V().hasLabel('users')"
        ".or(__.not(__.has('missing')), __.has('missing', null))"
        ".has('_key', TextP.regex('(?i)^hello'))"
    )


def test_compile_match_subquery_operand():
    assert (
        compile_opium_to_gremlin(
            "get('roles').match("
            "eq(traverse_out('role_abilities').into('abilities')['_key'], 'write')"
            ")"
        )
        == "g.V().hasLabel('roles')"
        f".filter(__.outE('role_abilities'){OUT_VERTEX_STEP}.hasLabel('abilities')"
        ".hasId(TextP.endingWith('/write')))"
    )


def test_compile_match_variable_operand():
    assert (
        compile_opium_to_gremlin(
            "get('roles').as_var('role').match(eq(var('role')['_key'], 'admin'))"
        )
        == "g.V().hasLabel('roles').as('role')"
        ".filter(__.select('role').hasId(TextP.endingWith('/admin')))"
    )


def test_value_in_requires_list():
    with pytest.raises(InvalidOpiumSemanticError):
        compile_opium_to_gremlin("get('users').match(value_in('_key', 'one'))")
