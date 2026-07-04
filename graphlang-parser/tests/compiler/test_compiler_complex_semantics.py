import pytest

from opium_parser import compile_opium_to_gremlin
from opium_parser.errors import InvalidOpiumSemanticError
from tests.compiler.expected_gremlin import OUT_VERTEX_STEP


def test_compile_complex_filter_traverse_unique_count():
    source = (
        "get('users-data-product.user_roles')"
        ".match(active=True, category='internal')"
        ".match(gt('priority', 5), score >= 90.0)"
        ".traverse_out('permissions-data-product.role_abilities')"
        ".into('permissions-data-product.abilities')"
        ".match(value_in('_key', ['write', 'delete', 'approve']))"
        ".unique()"
        ".count()"
    )

    assert compile_opium_to_gremlin(source) == (
        "g.V().hasLabel('users-data-product___user_roles')"
        ".has('active', true)"
        ".has('category', 'internal')"
        ".has('priority', P.gt(5))"
        ".has('score', P.gte(90.0d))"
        ".outE('permissions-data-product___role_abilities')"
        f"{OUT_VERTEX_STEP}"
        ".hasLabel('permissions-data-product___abilities')"
        ".or("
        "__.hasId(TextP.endingWith('/write')), "
        "__.hasId(TextP.endingWith('/delete')), "
        "__.hasId(TextP.endingWith('/approve'))"
        ")"
        ".dedup()"
        ".count()"
    )


def test_compile_complex_match_any_projection_and_limit():
    source = (
        "get('users-data-product.user_roles')"
        ".match_any("
        "eq('_key', 'admin'), "
        "regex_matches('name', '^aud', caseInsensitive=True), "
        "gt('priority', 10)"
        ")"
        ".select('_key', '_id', 'name', 'missing_field')"
        ".limit(5)"
    )

    assert compile_opium_to_gremlin(source) == (
        "g.V().hasLabel('users-data-product___user_roles')"
        ".or("
        "__.hasId(TextP.endingWith('/admin')), "
        "__.has('name', TextP.regex('(?i)^aud')), "
        "__.has('priority', P.gt(10))"
        ")"
        ".project('_key', '_id', 'name', 'missing_field')"
        ".by(__.id().map{it.get().substring(it.get().lastIndexOf('/') + 1)})"
        ".by(__.id().map{def id=it.get(); def slash=id.indexOf('/'); "
        "slash < 0 ? id.replace('___', '.') : "
        "id.substring(0, slash).replace('___', '.') + id.substring(slash)})"
        ".by(coalesce(values('name'), constant(null)))"
        ".by(coalesce(values('missing_field'), constant(null)))"
        ".limit(5)"
    )


def test_compile_var_selection_with_current_supported_shape():
    source = (
        "get('users-data-product.user_roles')"
        ".as_var('role')"
        ".select('_key', role_id=var('role')['_id'])"
    )

    assert compile_opium_to_gremlin(source) == (
        "g.V().hasLabel('users-data-product___user_roles')"
        ".as('role')"
        ".project('_key', 'role_id')"
        ".by(__.id().map{it.get().substring(it.get().lastIndexOf('/') + 1)})"
        ".by(select('role').id().map{def id=it.get(); def slash=id.indexOf('/'); "
        "slash < 0 ? id.replace('___', '.') : "
        "id.substring(0, slash).replace('___', '.') + id.substring(slash)})"
    )


def test_compile_match_subquery_operand_expected_shape():
    source = (
        "get('users-data-product.user_roles')"
        ".match(eq("
        "traverse_out('permissions-data-product.role_abilities')"
        ".into('permissions-data-product.abilities')['_key'], "
        "'write'"
        "))"
    )

    assert compile_opium_to_gremlin(source) == (
        "g.V().hasLabel('users-data-product___user_roles')"
        ".filter(__.outE('permissions-data-product___role_abilities')"
        f"{OUT_VERTEX_STEP}"
        ".hasLabel('permissions-data-product___abilities')"
        ".hasId(TextP.endingWith('/write')))"
    )


def test_compile_match_subquery_operand_value_in_expected_shape():
    source = (
        "get('users-data-product.user_roles')"
        ".match(value_in("
        "traverse_out('permissions-data-product.role_abilities')"
        ".into('permissions-data-product.abilities')['_key'], "
        "['read', 'approve']"
        "))"
    )

    assert compile_opium_to_gremlin(source) == (
        "g.V().hasLabel('users-data-product___user_roles')"
        ".filter(__.outE('permissions-data-product___role_abilities')"
        f"{OUT_VERTEX_STEP}"
        ".hasLabel('permissions-data-product___abilities')"
        ".or("
        "__.hasId(TextP.endingWith('/read')), "
        "__.hasId(TextP.endingWith('/approve'))"
        "))"
    )


def test_compile_match_deep_traversal_operand_expected_shape():
    source = (
        "get('org-data-product.teams')"
        ".match(eq("
        "traverse_out('org-data-product.team_hierarchy', max_depth=2)"
        ".into('org-data-product.teams')['_key'], "
        "'executive'"
        "))"
    )

    assert compile_opium_to_gremlin(source) == (
        "g.V().hasLabel('org-data-product___teams')"
        ".filter(__"
        ".repeat(outE('org-data-product___team_hierarchy').as('opium_edge')"
        f"{OUT_VERTEX_STEP})"
        ".emit()"
        ".times(2)"
        ".hasLabel('org-data-product___teams')"
        ".hasId(TextP.endingWith('/executive')))"
    )


def test_compile_match_traversal_count_at_least_three_expected_shape():
    source = (
        "get('users-data-product.user_roles')"
        ".match("
        "traverse_out('permissions-data-product.role_abilities')"
        ".into('permissions-data-product.abilities')"
        ".count() >= 3"
        ")"
    )

    assert compile_opium_to_gremlin(source) == (
        "g.V().hasLabel('users-data-product___user_roles')"
        ".filter(__.outE('permissions-data-product___role_abilities')"
        f"{OUT_VERTEX_STEP}"
        ".hasLabel('permissions-data-product___abilities')"
        ".count()"
        ".is(P.gte(3)))"
    )


def test_compile_match_unique_traversal_count_expected_shape():
    source = (
        "get('platform-data-product.services')"
        ".match("
        "traverse_out('platform-data-product.service_dependencies')"
        ".into('platform-data-product.services')"
        ".unique()"
        ".count() >= 2"
        ")"
    )

    assert compile_opium_to_gremlin(source) == (
        "g.V().hasLabel('platform-data-product___services')"
        ".filter(__.outE('platform-data-product___service_dependencies')"
        f"{OUT_VERTEX_STEP}"
        ".hasLabel('platform-data-product___services')"
        ".dedup()"
        ".count()"
        ".is(P.gte(2)))"
    )


def test_compile_match_function_style_traversal_count_expected_shape():
    source = (
        "get('users-data-product.user_roles')"
        ".match(gt("
        "traverse_out('permissions-data-product.role_abilities')"
        ".into('permissions-data-product.abilities')"
        ".count(), "
        "1"
        "))"
    )

    assert compile_opium_to_gremlin(source) == (
        "g.V().hasLabel('users-data-product___user_roles')"
        ".filter(__.outE('permissions-data-product___role_abilities')"
        f"{OUT_VERTEX_STEP}"
        ".hasLabel('permissions-data-product___abilities')"
        ".count()"
        ".is(P.gt(1)))"
    )


def test_compile_match_var_operand_expected_shape():
    source = (
        "get('users-data-product.user_roles')"
        ".as_var('role')"
        ".match(eq(var('role')['_key'], 'admin'))"
    )

    assert compile_opium_to_gremlin(source) == (
        "g.V().hasLabel('users-data-product___user_roles')"
        ".as('role')"
        ".filter(__.select('role').hasId(TextP.endingWith('/admin')))"
    )


def test_compile_is_null_matches_missing_or_explicit_null_expected_shape():
    assert compile_opium_to_gremlin(
        "get('users-data-product.user_roles').match(is_null('nullable_field'))"
    ) == (
        "g.V().hasLabel('users-data-product___user_roles')"
        ".or(__.not(__.has('nullable_field')), __.has('nullable_field', null))"
    )


def test_compile_match_traversal_count_rejects_non_numeric_comparison():
    with pytest.raises(InvalidOpiumSemanticError):
        compile_opium_to_gremlin(
            "get('users-data-product.user_roles')"
            ".match(traverse_out('permissions-data-product.role_abilities')"
            ".into('permissions-data-product.abilities')"
            ".count() == '3')"
        )
