import asyncio
import os
import sys

import pytest

from opium_parser import compile_opium_to_gremlin

pytestmark = pytest.mark.e2e

gremlin_python = pytest.importorskip("gremlin_python")

from gremlin_python.driver.client import Client  # noqa: E402

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


GREMLIN_URI = os.getenv("GREMLIN_URI", "ws://localhost:8182/gremlin")
TRAVERSAL_SOURCE = os.getenv("GREMLIN_TRAVERSAL_SOURCE", "g")
# RUN_E2E = os.getenv("OPIUM_RUN_E2E") == "1"
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


def test_collection_labels_are_visible(client):
    vertex_labels = set(client.submit("g.V().label().dedup()").all().result())
    edge_labels = set(client.submit("g.E().label().dedup()").all().result())

    assert "users-data-product.user_roles" in vertex_labels
    assert "veto-data-product.abilities" in vertex_labels
    assert "users-data-product.user_role_subscriptions" in edge_labels
    assert "veto-data-product.role_abilities" in edge_labels


def test_get_count_and_key_filter(client):
    assert run_query(client, "get('users-data-product.user_roles').count()") == [4]
    assert (
        run_query(
            client,
            "get('users-data-product.user_roles', _key='admin')['_key']",
        )
        == ["admin"]
    )


def test_match_keyword_comparison_and_containment(client):
    assert run_query(
        client,
        "get('users-data-product.user_roles').match(active=True).count()",
    ) == [3]
    assert run_query(
        client,
        "get('users-data-product.user_roles').match(gt('age', 48), lte('age', 85))"
        ".count()",
    ) == [2]
    assert sorted(
        run_query(
            client,
            "get('users-data-product.user_roles')"
            ".match(value_in('_key', ['admin', 'viewer']))['_key']",
        )
    ) == ["admin", "viewer"]
    assert sorted(
        run_query(
            client,
            "get('users-data-product.user_roles')"
            ".match(nin('_key', ['admin', 'viewer']))['_key']",
        )
    ) == ["auditor", "editor"]


def test_match_any_null_and_regex(client):
    assert sorted(
        run_query(
            client,
            "get('users-data-product.user_roles')"
            ".match_any(eq('_key', 'admin'), eq('_key', 'viewer'))['_key']",
        )
    ) == ["admin", "viewer"]
    assert run_query(
        client,
        "get('users-data-product.user_roles').match(is_null('missing_field'))"
        ".count()",
    ) == [4]
    assert sorted(
        run_query(
            client,
            "get('users-data-product.user_roles')"
            ".match(regex_matches('name', '^a', caseInsensitive=True))['_key']",
        )
    ) == ["admin", "auditor"]


def test_traverse_out_and_in(client):
    assert sorted(
        run_query(
            client,
            "get('users-data-product.user_roles', _key='admin')"
            ".traverse_out('veto-data-product.role_abilities')"
            ".into('veto-data-product.abilities')['_key']",
        )
    ) == ["delete", "write"]
    assert sorted(
        run_query(
            client,
            "get('users-data-product.user_roles', _key='admin')"
            ".traverse_in('users-data-product.user_role_subscriptions')"
            ".into('users-data-product.user_roles')['_key']",
        )
    ) == ["auditor", "editor"]


def test_skip_limit_unique_and_projection(client):
    assert len(
        run_query(
            client,
            "get('users-data-product.user_roles').skip(1).limit(2)['_key']",
        )
    ) == 2
    assert run_query(
        client,
        "get('users-data-product.user_roles')"
        ".traverse_out('veto-data-product.role_abilities')"
        ".into('veto-data-product.abilities').unique().count()",
    ) == [3]


def test_array_flatten_smoke(client):
    result = run_query(
        client,
        "get('users-data-product.user_roles', _key='admin')"
        ".array(traverse_out('veto-data-product.role_abilities')"
        ".into('veto-data-product.abilities')['_key'])"
        ".flatten()",
    )

    assert sorted(result) == ["delete", "write"]
