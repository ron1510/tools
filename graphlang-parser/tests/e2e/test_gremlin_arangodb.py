import asyncio
import os
import sys

import pytest

from opium_parser import compile_opium_to_gremlin
from tests.fixtures.e2e_graph import (
    ABILITY,
    COUNTS,
    EDGE_LABELS,
    MEMBERSHIP,
    ROLE,
    ROLE_ABILITY,
    SUBSCRIPTION,
    TEAM,
    TEAM_HIERARCHY,
    USER,
    VERTEX_LABELS,
)

pytestmark = pytest.mark.e2e

gremlin_python = pytest.importorskip("gremlin_python")

from gremlin_python.driver.client import Client  # noqa: E402

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


GREMLIN_URI = os.getenv("GREMLIN_URI", "ws://localhost:8182/gremlin")
TRAVERSAL_SOURCE = os.getenv("GREMLIN_TRAVERSAL_SOURCE", "g")
RUN_E2E = os.getenv("OPIUM_RUN_E2E") == "1"


@pytest.fixture(scope="module")
def client():
    if not RUN_E2E:
        pytest.skip("Set OPIUM_RUN_E2E=1 to run Gremlin/ArangoDB e2e tests")

    gremlin_client = Client(GREMLIN_URI, TRAVERSAL_SOURCE)
    try:
        gremlin_client.submit("g.V().limit(1).count()").all().result()
    except Exception as exc:
        gremlin_client.close()
        pytest.skip(f"Gremlin endpoint is not reachable at {GREMLIN_URI}: {exc}")

    yield gremlin_client
    gremlin_client.close()


def run_query(client: Client, opium: str):
    gremlin = compile_opium_to_gremlin(opium)
    return client.submit(gremlin).all().result()


def projected_values(rows, field: str):
    return [row[field] for row in rows]


def sorted_projected(rows, field: str):
    return sorted(projected_values(rows, field))


def test_collection_labels_are_visible(client):
    vertex_labels = set(client.submit("g.V().label().dedup()").all().result())
    edge_labels = set(client.submit("g.E().label().dedup()").all().result())

    assert VERTEX_LABELS <= vertex_labels
    assert EDGE_LABELS <= edge_labels


def test_get_counts_and_multi_source_get(client):
    assert run_query(client, f"get('{ROLE}').count()") == [COUNTS[ROLE]]
    assert run_query(client, f"get('{USER}').count()") == [COUNTS[USER]]
    assert run_query(client, f"get('{ABILITY}').count()") == [COUNTS[ABILITY]]
    assert run_query(client, f"get('{TEAM}').count()") == [COUNTS[TEAM]]
    assert run_query(client, f"get('{ROLE}', '{ABILITY}').count()") == [
        COUNTS[ROLE] + COUNTS[ABILITY]
    ]


def test_vertex_system_fields_and_projection_maps(client):
    assert run_query(client, f"get('{ROLE}', _key='admin')['_key']") == [
        {"_key": "admin"}
    ]
    assert run_query(client, f"get('{ROLE}', _key='admin')['_id']") == [
        {"_id": f"{ROLE}/admin"}
    ]
    assert run_query(client, f"get('{ROLE}', _key='admin')['missing_field']") == [
        {"missing_field": None}
    ]
    assert run_query(client, f"get('{ROLE}', _key='admin').select('_key', 'name')") == [
        {"_key": "admin", "name": "Admin"}
    ]
    assert run_query(
        client,
        f"get('{ROLE}', _key='admin').select('_key', 'missing_field')",
    ) == [{"_key": "admin", "missing_field": None}]


def test_keyword_match_and_comparison_predicates(client):
    assert run_query(client, f"get('{ROLE}').match(active=True).count()") == [4]
    assert run_query(client, f"get('{USER}').match(active=False).count()") == [1]
    score_query = f"get('{ROLE}').match(score >= 90.0)['_key']"
    severity_query = f"get('{ABILITY}').match(lt('severity', 8))['_key']"

    assert run_query(
        client,
        f"get('{ROLE}').match(gt('age', 48), lte('age', 85)).count()",
    ) == [2]
    assert sorted_projected(run_query(client, score_query), "_key") == [
        "admin",
        "owner",
    ]
    assert sorted_projected(run_query(client, severity_query), "_key") == [
        "approve",
        "read",
        "write",
    ]


def test_containment_match_any_regex_and_null(client):
    value_in_query = (
        f"get('{ROLE}').match(value_in('_key', ['admin', 'viewer']))['_key']"
    )
    nin_query = (
        f"get('{ROLE}').match(nin('_key', ['admin', 'viewer']))['_key']"
    )
    match_any_query = (
        f"get('{ROLE}').match_any("
        "eq('_key', 'admin'), "
        "eq('_key', 'viewer')"
        ")['_key']"
    )
    regex_query = (
        f"get('{ROLE}').match("
        "regex_matches('name', '^a', caseInsensitive=True)"
        ")['_key']"
    )

    assert sorted_projected(
        run_query(client, value_in_query),
        "_key",
    ) == ["admin", "viewer"]
    assert sorted_projected(
        run_query(client, nin_query),
        "_key",
    ) == ["auditor", "editor", "owner"]
    assert sorted_projected(
        run_query(client, match_any_query),
        "_key",
    ) == ["admin", "viewer"]
    assert sorted_projected(
        run_query(client, regex_query),
        "_key",
    ) == ["admin", "auditor"]
    assert run_query(
        client,
        f"get('{ROLE}').match(is_null('missing_field')).count()",
    ) == [5]


def test_role_to_ability_traversal_and_unique(client):
    assert sorted_projected(
        run_query(
            client,
            f"get('{ROLE}', _key='admin').traverse_out('{ROLE_ABILITY}')"
            f".into('{ABILITY}')['_key']",
        ),
        "_key",
    ) == ["approve", "delete", "write"]
    assert run_query(
        client,
        f"get('{ROLE}').traverse_out('{ROLE_ABILITY}')"
        f".into('{ABILITY}').unique().count()",
    ) == [4]


def test_subscription_traversal_directions_and_any(client):
    assert sorted_projected(
        run_query(
            client,
            f"get('{ROLE}', _key='admin').traverse_in('{SUBSCRIPTION}')"
            f".into('{ROLE}')['_key']",
        ),
        "_key",
    ) == ["auditor", "editor"]
    assert sorted_projected(
        run_query(
            client,
            f"get('{ROLE}', _key='admin').traverse_any('{SUBSCRIPTION}')"
            f".into('{ROLE}')['_key']",
        ),
        "_key",
    ) == ["auditor", "editor", "owner"]


def test_edge_document_projection_from_traverse_without_into(client):
    assert run_query(
        client,
        f"get('{ROLE}', _key='viewer').traverse_out('{SUBSCRIPTION}')"
        ".select('_key', '_id', '_from', '_to', 'weight')",
    ) == [
        {
            "_key": "viewer-to-editor",
            "_id": f"{SUBSCRIPTION}/viewer-to-editor",
            "_from": f"{ROLE}/viewer",
            "_to": f"{ROLE}/editor",
            "weight": 2,
        }
    ]


def test_user_team_memberships_and_team_hierarchy(client):
    assert run_query(
        client,
        f"get('{USER}', _key='alice').traverse_out('{MEMBERSHIP}')"
        f".into('{TEAM}')['_key']",
    ) == [{"_key": "platform"}]
    assert sorted_projected(
        run_query(
            client,
            f"get('{TEAM}', _key='executive').traverse_in('{TEAM_HIERARCHY}')"
            f".into('{TEAM}')['_key']",
        ),
        "_key",
    ) == ["platform", "security"]


def test_deep_traversal_vertices_and_edges(client):
    deep_roles_query = (
        f"get('{ROLE}', _key='viewer')"
        f".traverse_out('{SUBSCRIPTION}', max_depth=3)"
        f".into('{ROLE}')['_key']"
    )
    deep_team_query = (
        f"get('{TEAM}', _key='qa')"
        f".traverse_out('{TEAM_HIERARCHY}', max_depth=2)"
        f".into('{TEAM}')['_key']"
    )

    assert sorted_projected(
        run_query(client, deep_roles_query),
        "_key",
    ) == ["admin", "editor", "owner"]
    assert sorted_projected(
        run_query(
            client,
            f"get('{ROLE}', _key='viewer').traverse_out("
            f"'{SUBSCRIPTION}', min_depth=2, max_depth=3"
            ")['_key']",
        ),
        "_key",
    ) == ["admin-to-owner", "editor-to-admin"]
    assert sorted_projected(
        run_query(client, deep_team_query),
        "_key",
    ) == ["executive", "platform"]


def test_skip_limit_count_and_projection_shape(client):
    assert len(run_query(client, f"get('{ROLE}').skip(1).limit(2)['_key']")) == 2
    assert run_query(client, f"get('{ROLE}').limit(2).count()") == [2]


def test_array_flatten_smoke_for_current_behavior(client):
    result = run_query(
        client,
        f"get('{ROLE}', _key='admin').array(traverse_out('{ROLE_ABILITY}')"
        f".into('{ABILITY}')['_key']).flatten()",
    )

    assert sorted_projected(result, "_key") == ["approve", "delete", "write"]


@pytest.mark.skip(reason="Default full-document materialization is not implemented yet")
def test_default_full_document_result_shape(client):
    rows = run_query(client, f"get('{ROLE}', _key='admin')")
    assert rows == [
        {
            "_key": "admin",
            "_id": f"{ROLE}/admin",
            "name": "Admin",
            "age": 64,
            "score": 98.5,
            "priority": 10,
            "category": "internal",
            "active": True,
            "nullable_field": None,
        }
    ]


@pytest.mark.skip(reason="assign/select computed-column semantics are unresolved")
def test_assign_select_computed_column_placeholder(client):
    run_query(
        client,
        f"get('{ROLE}', _key='admin').assign("
        f"traverse_in('{SUBSCRIPTION}').into('{ROLE}'), 'neighborhood'"
        ").select('_key', neighbors=var('neighborhood')['_key'])",
    )


@pytest.mark.skip(reason="match subquery operand semantics are unresolved")
def test_match_subquery_operand_placeholder(client):
    run_query(
        client,
        f"get('{ROLE}').match("
        f"eq(traverse_out('{ROLE_ABILITY}').into()['_key'], 'write'))",
    )


@pytest.mark.skip(reason="match variable operand semantics are unresolved")
def test_match_variable_operand_placeholder(client):
    run_query(
        client,
        f"get('{ROLE}').as_var('role').match(eq(var('role')['_key'], 'admin'))",
    )
