import asyncio
import os
import sys

import pytest

from opium_parser import compile_opium_to_gremlin
from tests.fixtures.e2e_graph import (
    ABILITY,
    COUNTS,
    DEPARTMENT,
    DEPARTMENT_PROJECT,
    DOCUMENT,
    DOCUMENT_LINK,
    EDGE_LABELS,
    ENVIRONMENT,
    INCIDENT,
    INCIDENT_IMPACT,
    MEMBERSHIP,
    PROJECT,
    PROJECT_SERVICE,
    REGION,
    ROLE,
    ROLE_ABILITY,
    SERVICE,
    SERVICE_DEPENDENCY,
    SERVICE_ENVIRONMENT,
    SERVICE_REGION,
    SUBSCRIPTION,
    TEAM,
    TEAM_HIERARCHY,
    USER,
    USER_ROLE_ASSIGNMENT,
    VERTEX_LABELS,
)

pytestmark = pytest.mark.e2e

gremlin_python = pytest.importorskip("gremlin_python")

from gremlin_python.driver.client import Client  # noqa: E402

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


GREMLIN_URI = os.getenv("GREMLIN_URI", "ws://localhost:8182/gremlin")
TRAVERSAL_SOURCE = os.getenv("GREMLIN_TRAVERSAL_SOURCE", "g")
# RUN_E2E = os.getenv("OPIUM_RUN_E2E") == "1"
RUN_E2E = True


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
    assert run_query(client, f"get('{DEPARTMENT}').count()") == [COUNTS[DEPARTMENT]]
    assert run_query(client, f"get('{PROJECT}').count()") == [COUNTS[PROJECT]]
    assert run_query(client, f"get('{SERVICE}').count()") == [COUNTS[SERVICE]]
    assert run_query(client, f"get('{INCIDENT}').count()") == [COUNTS[INCIDENT]]
    assert run_query(client, f"get('{REGION}').count()") == [COUNTS[REGION]]
    assert run_query(client, f"get('{ENVIRONMENT}').count()") == [COUNTS[ENVIRONMENT]]
    assert run_query(client, f"get('{DOCUMENT}').count()") == [COUNTS[DOCUMENT]]
    assert run_query(client, f"get('{ROLE}', '{ABILITY}').count()") == [
        COUNTS[ROLE] + COUNTS[ABILITY]
    ]


def test_vertex_system_fields_projection_and_select_shape(client):
    assert run_query(client, f"get('{ROLE}', _key='admin')['_key']") == ["admin"]
    assert run_query(client, f"get('{ROLE}', _key='admin')['_id']") == [f"{ROLE}/admin"]
    assert run_query(client, f"get('{ROLE}', _key='admin')['missing_field']") == [None]
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
    assert sorted(run_query(client, score_query)) == [
        "admin",
        "owner",
    ]
    assert sorted(run_query(client, severity_query)) == [
        "approve",
        "read",
        "write",
    ]


def test_containment_match_any_regex_and_null(client):
    value_in_query = (
        f"get('{ROLE}').match(value_in('_key', ['admin', 'viewer']))['_key']"
    )
    nin_query = f"get('{ROLE}').match(nin('_key', ['admin', 'viewer']))['_key']"
    match_any_query = (
        f"get('{ROLE}').match_any(eq('_key', 'admin'), eq('_key', 'viewer'))['_key']"
    )
    regex_query = (
        f"get('{ROLE}').match("
        "regex_matches('name', '^a', caseInsensitive=True)"
        ")['_key']"
    )

    assert sorted(run_query(client, value_in_query)) == ["admin", "viewer"]
    assert sorted(run_query(client, nin_query)) == ["auditor", "editor", "owner"]
    assert sorted(run_query(client, match_any_query)) == ["admin", "viewer"]
    assert sorted(run_query(client, regex_query)) == ["admin", "auditor"]
    assert run_query(
        client,
        f"get('{ROLE}').match(is_null('missing_field')).count()",
    ) == [5]


def test_role_to_ability_traversal_and_unique(client):
    assert sorted(
        run_query(
            client,
            f"get('{ROLE}', _key='admin').traverse_out('{ROLE_ABILITY}')"
            f".into('{ABILITY}')['_key']",
        )
    ) == ["approve", "delete", "write"]
    assert run_query(
        client,
        f"get('{ROLE}').traverse_out('{ROLE_ABILITY}')"
        f".into('{ABILITY}').unique().count()",
    ) == [4]


def test_dangling_outbound_edge_can_be_inspected_but_not_materialized(client):
    assert run_query(
        client,
        f"get('{ROLE}', _key='auditor').traverse_out('{ROLE_ABILITY}')['_key']",
    ) == ["auditor-missing-ability"]
    assert run_query(
        client,
        f"get('{ROLE}', _key='auditor').traverse_out('{ROLE_ABILITY}')"
        f".into('{ABILITY}')['_key']",
    ) == []


def test_terminal_traverse_returns_safe_edge_documents_with_dangling_edge(client):
    rows = run_query(
        client,
        f"get('{ROLE}', _key='auditor').traverse()",
    )

    by_key = {row["_key"]: row for row in rows}
    dangling = by_key["auditor-missing-ability"]
    assert dangling["_id"] == f"{ROLE_ABILITY}/auditor-missing-ability"
    assert dangling["_from"] == f"{ROLE}/auditor"
    assert dangling["_to"] == f"{ABILITY}/missing-ability"


def test_terminal_labeled_traverse_returns_safe_edge_documents(client):
    rows = run_query(
        client,
        f"get('{USER}', _key='bob').traverse_out('{MEMBERSHIP}')",
    )

    by_key = {row["_key"]: row for row in rows}
    assert set(by_key) == {"bob-missing-team", "bob-platform"}
    assert by_key["bob-missing-team"]["_from"] == f"{USER}/bob"
    assert by_key["bob-missing-team"]["_to"] == f"{TEAM}/missing-team"
    assert by_key["bob-platform"]["_to"] == f"{TEAM}/platform"


def test_dangling_inbound_edge_can_be_inspected_but_not_materialized(client):
    assert sorted(
        run_query(
            client,
            f"get('{ABILITY}', _key='read').traverse_in('{ROLE_ABILITY}')['_key']",
        )
    ) == ["missing-role-read", "viewer-read"]
    assert run_query(
        client,
        f"get('{ABILITY}', _key='read').traverse_in('{ROLE_ABILITY}')"
        f".into('{ROLE}')['_key']",
    ) == ["viewer"]


@pytest.mark.parametrize(
    ("source", "required_edges", "required_vertices", "forbidden_vertices"),
    [
        (
            f"get('{ROLE}', _key='auditor')",
            ["auditor-missing-ability"],
            ["admin", "dave"],
            ["missing-ability"],
        ),
        (
            f"get('{ABILITY}', _key='read')",
            ["missing-role-read", "viewer-read"],
            ["viewer"],
            ["missing-role"],
        ),
        (
            f"get('{USER}', _key='bob')",
            ["bob-missing-team", "bob-platform"],
            ["platform"],
            ["missing-team"],
        ),
        (
            f"get('{TEAM}', _key='qa')",
            ["missing-user-qa"],
            ["platform"],
            ["missing-user"],
        ),
        (
            f"get('{SERVICE}', _key='service-11')",
            ["service-11-missing-service"],
            ["project-7", "service-10", "service-5"],
            ["missing-service"],
        ),
        (
            f"get('{SERVICE}', _key='service-0')",
            ["missing-service-service-0", "service-0-service-1", "service-0-service-5"],
            ["service-1", "service-5"],
            ["missing-service"],
        ),
        (
            f"get('{DOCUMENT}', _key='doc-14')",
            ["doc-14-missing-doc"],
            ["doc-13"],
            ["missing-doc"],
        ),
        (
            f"get('{DOCUMENT}', _key='doc-0')",
            ["doc-0-doc-1", "missing-doc-doc-0"],
            ["doc-1"],
            ["missing-doc"],
        ),
    ],
)
def test_dangling_edges_across_domains_are_inspectable_and_safe_to_enter(
    client,
    source,
    required_edges,
    required_vertices,
    forbidden_vertices,
):
    edge_rows = run_query(client, f"{source}.traverse()['_key']")
    vertex_rows = run_query(client, f"{source}.traverse().into()['_key']")

    assert set(required_edges) <= set(edge_rows)
    assert set(required_vertices) <= set(vertex_rows)
    assert not (set(forbidden_vertices) & set(vertex_rows))


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            f"get('{ROLE}', _key='auditor').traverse_out('{ROLE_ABILITY}')"
            ".select('_key', '_from', '_to')",
            [
                {
                    "_key": "auditor-missing-ability",
                    "_from": f"{ROLE}/auditor",
                    "_to": f"{ABILITY}/missing-ability",
                }
            ],
        ),
        (
            f"get('{ABILITY}', _key='read').traverse_in('{ROLE_ABILITY}')"
            ".select('_key', '_from', '_to')",
            [
                {
                    "_key": "missing-role-read",
                    "_from": f"{ROLE}/missing-role",
                    "_to": f"{ABILITY}/read",
                },
                {
                    "_key": "viewer-read",
                    "_from": f"{ROLE}/viewer",
                    "_to": f"{ABILITY}/read",
                },
            ],
        ),
        (
            f"get('{SERVICE}', _key='service-11').traverse_out('{SERVICE_DEPENDENCY}')"
            ".select('_key', '_from', '_to')",
            [
                {
                    "_key": "service-11-missing-service",
                    "_from": f"{SERVICE}/service-11",
                    "_to": f"{SERVICE}/missing-service",
                }
            ],
        ),
        (
            f"get('{DOCUMENT}', _key='doc-14').traverse_out('{DOCUMENT_LINK}')"
            ".select('_key', '_from', '_to')",
            [
                {
                    "_key": "doc-14-missing-doc",
                    "_from": f"{DOCUMENT}/doc-14",
                    "_to": f"{DOCUMENT}/missing-doc",
                }
            ],
        ),
    ],
)
def test_dangling_edge_system_fields_are_preserved(client, query, expected):
    rows = sorted(run_query(client, query), key=lambda row: row["_key"])
    assert rows == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            f"get('{ROLE}', _key='auditor').array("
            f"traverse_out('{ROLE_ABILITY}')['_key'])",
            [["auditor-missing-ability"]],
        ),
        (
            f"get('{ROLE}', _key='auditor').array("
            f"traverse_out('{ROLE_ABILITY}').into('{ABILITY}')['_key'])",
            [[]],
        ),
        (
            f"get('{USER}', _key='bob').array("
            f"traverse_out('{MEMBERSHIP}')['_key'])",
            [["bob-missing-team", "bob-platform"]],
        ),
        (
            f"get('{USER}', _key='bob').array("
            f"traverse_out('{MEMBERSHIP}').into('{TEAM}')['_key'])",
            [["platform"]],
        ),
        (
            f"get('{DOCUMENT}', _key='doc-14').array("
            f"traverse_out('{DOCUMENT_LINK}')['_key']).flatten()",
            ["doc-14-missing-doc"],
        ),
        (
            f"get('{DOCUMENT}', _key='doc-14').array("
            f"traverse_out('{DOCUMENT_LINK}').into('{DOCUMENT}')['_key']).flatten()",
            [],
        ),
    ],
)
def test_dangling_edges_in_array_and_flatten_shapes(client, query, expected):
    rows = run_query(client, query)
    if rows and isinstance(rows[0], list):
        rows = [sorted(row) for row in rows]
    assert rows == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            f"get('{ROLE}', _key='auditor').traverse_out('{ROLE_ABILITY}').count()",
            [1],
        ),
        (
            f"get('{ROLE}', _key='auditor').traverse_out('{ROLE_ABILITY}')"
            f".into('{ABILITY}').count()",
            [0],
        ),
        (
            f"get('{USER}', _key='bob').traverse_out('{MEMBERSHIP}').count()",
            [2],
        ),
        (
            f"get('{USER}', _key='bob').traverse_out('{MEMBERSHIP}')"
            f".into('{TEAM}').count()",
            [1],
        ),
        (
            f"get('{SERVICE}', _key='service-11')"
            f".traverse_out('{SERVICE_DEPENDENCY}').count()",
            [1],
        ),
        (
            f"get('{SERVICE}', _key='service-11')"
            f".traverse_out('{SERVICE_DEPENDENCY}').into('{SERVICE}').count()",
            [0],
        ),
    ],
)
def test_dangling_edge_counts_distinguish_edges_from_vertices(client, query, expected):
    assert run_query(client, query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            f"get('{ROLE}').match("
            f"traverse_out('{ROLE_ABILITY}').count() >= 1)['_key']",
            ["admin", "auditor", "editor", "viewer"],
        ),
        (
            f"get('{ROLE}').match("
            f"traverse_out('{ROLE_ABILITY}').into('{ABILITY}').count() >= 1)['_key']",
            ["admin", "editor", "viewer"],
        ),
        (
            f"get('{USER}').match("
            f"traverse_out('{MEMBERSHIP}').count() >= 2)['_key']",
            ["bob"],
        ),
        (
            f"get('{USER}').match("
            f"traverse_out('{MEMBERSHIP}').into('{TEAM}').count() >= 2)['_key']",
            [],
        ),
        (
            f"get('{SERVICE}').match("
            f"traverse_out('{SERVICE_DEPENDENCY}').count() >= 1)['_key']",
            sorted(f"service-{index}" for index in range(12)),
        ),
        (
            f"get('{DOCUMENT}').match("
            f"traverse_out('{DOCUMENT_LINK}', max_depth=2).into('{DOCUMENT}')"
            ".count() >= 1)['_key']",
            sorted(f"doc-{index}" for index in range(14)),
        ),
    ],
)
def test_dangling_edges_inside_match_subqueries(client, query, expected):
    assert sorted(run_query(client, query)) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            f"get('{SERVICE}', _key='service-11')"
            f".traverse_out('{SERVICE_DEPENDENCY}', max_depth=2)['_key']",
            [],
        ),
        (
            f"get('{SERVICE}', _key='service-11')"
            f".traverse_out('{SERVICE_DEPENDENCY}', max_depth=2)"
            f".into('{SERVICE}')['_key']",
            [],
        ),
        (
            f"get('{DOCUMENT}', _key='doc-13')"
            f".traverse_out('{DOCUMENT_LINK}', max_depth=3)['_key']",
            ["doc-13-doc-14"],
        ),
        (
            f"get('{DOCUMENT}', _key='doc-13')"
            f".traverse_out('{DOCUMENT_LINK}', max_depth=3)"
            f".into('{DOCUMENT}')['_key']",
            ["doc-14"],
        ),
    ],
)
def test_dangling_edges_in_deep_traversals(client, query, expected):
    assert sorted(run_query(client, query)) == expected


def test_subscription_traversal_directions_and_any(client):
    assert sorted(
        run_query(
            client,
            f"get('{ROLE}', _key='admin').traverse_in('{SUBSCRIPTION}')"
            f".into('{ROLE}')['_key']",
        )
    ) == ["auditor", "editor"]
    assert sorted(
        run_query(
            client,
            f"get('{ROLE}', _key='admin').traverse_any('{SUBSCRIPTION}')"
            f".into('{ROLE}')['_key']",
        )
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
    ) == ["platform"]
    assert sorted(
        run_query(
            client,
            f"get('{TEAM}', _key='executive').traverse_in('{TEAM_HIERARCHY}')"
            f".into('{TEAM}')['_key']",
        )
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

    assert sorted(run_query(client, deep_roles_query)) == ["admin", "editor", "owner"]
    assert sorted(
        run_query(
            client,
            f"get('{ROLE}', _key='viewer').traverse_out("
            f"'{SUBSCRIPTION}', min_depth=2, max_depth=3"
            ")['_key']",
        )
    ) == ["admin-to-owner", "editor-to-admin"]
    assert sorted(run_query(client, deep_team_query)) == ["executive", "platform"]


def test_skip_limit_count_and_projection_shape(client):
    assert len(run_query(client, f"get('{ROLE}').skip(1).limit(2)['_key']")) == 2
    assert run_query(client, f"get('{ROLE}').limit(2).count()") == [2]


def test_complex_filter_traversal_aggregation_query(client):
    query = (
        f"get('{ROLE}')"
        ".match(active=True, category='internal')"
        ".match(gt('priority', 5), score >= 90.0)"
        f".traverse_out('{ROLE_ABILITY}')"
        f".into('{ABILITY}')"
        ".match(value_in('_key', ['write', 'delete', 'approve']))"
        ".unique()"
        ".count()"
    )

    assert run_query(client, query) == [3]


def test_complex_match_any_select_and_limit_query(client):
    query = (
        f"get('{ROLE}')"
        ".match_any("
        "eq('_key', 'admin'), "
        "regex_matches('name', '^aud', caseInsensitive=True), "
        "gt('priority', 10)"
        ")"
        ".select('_key', '_id', 'name', 'missing_field')"
        ".limit(5)"
    )

    rows = run_query(client, query)
    assert sorted_projected(rows, "_key") == ["admin", "auditor", "owner"]
    assert all(set(row) == {"_key", "_id", "name", "missing_field"} for row in rows)
    assert all(row["missing_field"] is None for row in rows)


def test_array_flatten_smoke_for_current_behavior(client):
    result = run_query(
        client,
        f"get('{ROLE}', _key='admin').array(traverse_out('{ROLE_ABILITY}')"
        f".into('{ABILITY}')['_key']).flatten()",
    )

    assert sorted(result) == ["approve", "delete", "write"]


def test_array_replaces_current_row_with_per_row_subquery_result(client):
    rows = run_query(
        client,
        f"get('{ROLE}', _key='admin')"
        f".array(traverse_out('{ROLE_ABILITY}').into('{ABILITY}')['_key'])",
    )

    assert len(rows) == 1
    assert sorted(rows[0]) == ["approve", "delete", "write"]


def test_array_empty_subquery_keeps_row_as_empty_array(client):
    rows = run_query(
        client,
        f"get('{ROLE}', _key='auditor')"
        f".array(traverse_out('{ROLE_ABILITY}').into('{ABILITY}')['_key'])",
    )

    assert rows == [[]]


def test_array_flatten_across_multiple_current_rows(client):
    rows = run_query(
        client,
        f"get('{ROLE}').match(value_in('_key', ['admin', 'editor', 'viewer']))"
        f".array(traverse_out('{ROLE_ABILITY}').into('{ABILITY}')['_key'])"
        ".flatten()",
    )

    assert sorted(rows) == ["approve", "delete", "read", "write", "write"]


def test_array_can_collect_selected_edge_documents(client):
    rows = run_query(
        client,
        f"get('{ROLE}', _key='admin')"
        f".array(traverse_out('{ROLE_ABILITY}').select('_key', '_from', '_to'))",
    )

    assert len(rows) == 1
    edge_rows = sorted(rows[0], key=lambda row: row["_key"])
    assert edge_rows == [
        {
            "_key": "admin-approve",
            "_from": f"{ROLE}/admin",
            "_to": f"{ABILITY}/approve",
        },
        {
            "_key": "admin-delete",
            "_from": f"{ROLE}/admin",
            "_to": f"{ABILITY}/delete",
        },
        {
            "_key": "admin-write",
            "_from": f"{ROLE}/admin",
            "_to": f"{ABILITY}/write",
        },
    ]


def test_array_with_deep_traversal_subquery(client):
    rows = run_query(
        client,
        f"get('{TEAM}', _key='qa')"
        f".array(traverse_out('{TEAM_HIERARCHY}', max_depth=2)"
        f".into('{TEAM}')['_key'])",
    )

    assert len(rows) == 1
    assert sorted(rows[0]) == ["executive", "platform"]


def test_assign_preserves_current_rows_for_count(client):
    assert run_query(
        client,
        f"get('{ROLE}').assign("
        f"traverse_out('{ROLE_ABILITY}').into('{ABILITY}'), "
        "'ability_neighbors'"
        ").count()",
    ) == [COUNTS[ROLE]]


def test_assign_preserves_current_rows_for_later_select(client):
    rows = run_query(
        client,
        f"get('{ROLE}', _key='admin').assign("
        f"traverse_out('{ROLE_ABILITY}').into('{ABILITY}'), "
        "'ability_neighbors'"
        ").select('_key', 'name')",
    )

    assert rows == [{"_key": "admin", "name": "Admin"}]


def test_assign_preserves_current_rows_for_later_traversal(client):
    rows = run_query(
        client,
        f"get('{USER}', _key='alice').assign("
        f"traverse_out('{MEMBERSHIP}').into('{TEAM}'), "
        "'teams'"
        f").traverse_out('{USER_ROLE_ASSIGNMENT}').into('{ROLE}')['_key']",
    )

    assert sorted(rows) == ["admin", "owner"]


def test_large_graph_department_project_service_dependency_chain(client):
    query = (
        f"get('{DEPARTMENT}', _key='eng')"
        f".traverse_out('{DEPARTMENT_PROJECT}')"
        f".into('{PROJECT}')"
        f".traverse_out('{PROJECT_SERVICE}')"
        f".into('{SERVICE}')"
        f".traverse_out('{SERVICE_DEPENDENCY}')"
        f".into('{SERVICE}')"
        ".match(value_in('_key', "
        "['service-1', 'service-2', 'service-5', 'service-6', 'service-11']"
        "))"
        ".unique()"
        "['_key']"
    )

    assert sorted(run_query(client, query)) == [
        "service-1",
        "service-11",
        "service-2",
        "service-5",
        "service-6",
    ]


def test_large_graph_incident_reverse_traversal_and_aggregation(client):
    query = (
        f"get('{SERVICE}', _key='service-0')"
        f".traverse_in('{INCIDENT_IMPACT}')"
        f".into('{INCIDENT}')"
        ".match(open=True, severity=1)"
        ".count()"
    )

    assert run_query(client, query) == [1]


def test_large_graph_regions_environments_and_documents(client):
    service_to_targets = (
        f"get('{SERVICE}', _key='service-0')"
        f".traverse_out('{SERVICE_REGION}', '{SERVICE_ENVIRONMENT}')"
        f".into('{REGION}', '{ENVIRONMENT}')"
        ".select('_key', '_id')"
    )
    doc_chain = (
        f"get('{DOCUMENT}', _key='doc-0')"
        f".traverse_out('{DOCUMENT_LINK}', max_depth=4)"
        f".into('{DOCUMENT}')"
        ".unique()"
        ".count()"
    )

    assert sorted_projected(run_query(client, service_to_targets), "_key") == [
        "dev",
        "dr",
        "prod",
        "us-east",
    ]
    assert run_query(client, doc_chain) == [4]


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
    rows = run_query(
        client,
        f"get('{ROLE}', _key='admin').assign("
        f"traverse_in('{SUBSCRIPTION}').into('{ROLE}'), 'neighborhood'"
        ").select('_key', neighbors=var('neighborhood')['_key'])",
    )

    assert rows == [{"_key": "admin", "neighbors": ["auditor", "editor"]}]


def test_match_subquery_operand_expected_result(client):
    rows = run_query(
        client,
        f"get('{ROLE}').match("
        f"eq(traverse_out('{ROLE_ABILITY}').into('{ABILITY}')['_key'], 'write'))"
        "['_key']",
    )

    assert sorted(rows) == ["admin", "editor"]


def test_match_subquery_operand_with_value_in_expected_result(client):
    rows = run_query(
        client,
        f"get('{ROLE}').match("
        f"value_in(traverse_out('{ROLE_ABILITY}').into('{ABILITY}')['_key'], "
        "['read', 'approve'])"
        ")['_key']",
    )

    assert sorted(rows) == ["admin", "viewer"]


def test_match_deep_traversal_operand_expected_result(client):
    rows = run_query(
        client,
        f"get('{TEAM}').match("
        f"eq(traverse_out('{TEAM_HIERARCHY}', max_depth=2)"
        f".into('{TEAM}')['_key'], 'executive')"
        ")['_key']",
    )

    assert sorted(rows) == ["platform", "qa", "security"]


def test_match_variable_operand_expected_result(client):
    rows = run_query(
        client,
        f"get('{ROLE}').as_var('role').match(eq(var('role')['_key'], 'admin'))['_key']",
    )

    assert rows == ["admin"]


def test_is_null_matches_missing_or_explicit_null_expected_result(client):
    assert run_query(
        client,
        f"get('{ROLE}').match(is_null('nullable_field')).count()",
    ) == [5]


def test_match_traversal_count_at_least_three_expected_result(client):
    rows = run_query(
        client,
        f"get('{ROLE}').match("
        f"traverse_out('{ROLE_ABILITY}').into('{ABILITY}').count() >= 3"
        ")['_key']",
    )

    assert rows == ["admin"]


def test_match_traversal_count_zero_expected_result(client):
    rows = run_query(
        client,
        f"get('{ROLE}').match("
        f"traverse_out('{ROLE_ABILITY}').into('{ABILITY}').count() == 0"
        ")['_key']",
    )

    assert sorted(rows) == ["auditor", "owner"]


def test_match_unique_traversal_count_expected_result(client):
    rows = run_query(
        client,
        f"get('{SERVICE}').match("
        f"traverse_out('{SERVICE_DEPENDENCY}').into('{SERVICE}')"
        ".unique()"
        ".count() >= 2"
        ")['_key']",
    )

    assert sorted(rows) == ["service-0", "service-2", "service-5"]


def test_match_function_style_traversal_count_expected_result(client):
    rows = run_query(
        client,
        f"get('{ROLE}').match("
        f"gt(traverse_out('{ROLE_ABILITY}').into('{ABILITY}').count(), 1)"
        ")['_key']",
    )

    assert rows == ["admin"]
