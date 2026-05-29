"""Shared names for the live ArangoDB/Gremlin e2e graph.

The constants keep tests and seed documentation aligned. They intentionally use
full Arango collection names because the compiler assumption under review is
that provider COMPLEX mode exposes those collection names as Gremlin labels.
"""

ROLE = "users-data-product.user_roles"
USER = "users-data-product.users"
ABILITY = "veto-data-product.abilities"
TEAM = "org-data-product.teams"

SUBSCRIPTION = "users-data-product.user_role_subscriptions"
ROLE_ABILITY = "veto-data-product.role_abilities"
MEMBERSHIP = "org-data-product.user_memberships"
TEAM_HIERARCHY = "org-data-product.team_hierarchy"

VERTEX_LABELS = {ROLE, USER, ABILITY, TEAM}
EDGE_LABELS = {SUBSCRIPTION, ROLE_ABILITY, MEMBERSHIP, TEAM_HIERARCHY}

COUNTS = {
    ROLE: 5,
    USER: 5,
    ABILITY: 4,
    TEAM: 4,
    SUBSCRIPTION: 4,
    ROLE_ABILITY: 5,
    MEMBERSHIP: 5,
    TEAM_HIERARCHY: 3,
}
