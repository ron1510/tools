"""Shared names for the live ArangoDB/Gremlin e2e graph.

The constants keep tests and seed documentation aligned. They intentionally use
full Arango collection names because the compiler assumption under review is
that provider COMPLEX mode exposes those collection names as Gremlin labels.
"""

ROLE = "users-data-product.user_roles"
USER = "users-data-product.users"
ABILITY = "permissions-data-product.abilities"
TEAM = "org-data-product.teams"
DEPARTMENT = "org-data-product.departments"
PROJECT = "delivery-data-product.projects"
SERVICE = "platform-data-product.services"
INCIDENT = "ops-data-product.incidents"
REGION = "infra-data-product.regions"
ENVIRONMENT = "infra-data-product.environments"
DOCUMENT = "knowledge-data-product.documents"

SUBSCRIPTION = "users-data-product.user_role_subscriptions"
ROLE_ABILITY = "permissions-data-product.role_abilities"
MEMBERSHIP = "org-data-product.user_memberships"
TEAM_HIERARCHY = "org-data-product.team_hierarchy"
USER_ROLE_ASSIGNMENT = "users-data-product.user_role_assignments"
DEPARTMENT_MEMBERSHIP = "org-data-product.department_memberships"
DEPARTMENT_PROJECT = "delivery-data-product.department_projects"
PROJECT_SERVICE = "platform-data-product.project_services"
SERVICE_DEPENDENCY = "platform-data-product.service_dependencies"
INCIDENT_IMPACT = "ops-data-product.incident_impacts"
SERVICE_REGION = "infra-data-product.service_regions"
SERVICE_ENVIRONMENT = "infra-data-product.service_environments"
DOCUMENT_LINK = "knowledge-data-product.document_links"

VERTEX_LABELS = {
    ROLE,
    USER,
    ABILITY,
    TEAM,
    DEPARTMENT,
    PROJECT,
    SERVICE,
    INCIDENT,
    REGION,
    ENVIRONMENT,
    DOCUMENT,
}
EDGE_LABELS = {
    SUBSCRIPTION,
    ROLE_ABILITY,
    MEMBERSHIP,
    TEAM_HIERARCHY,
    USER_ROLE_ASSIGNMENT,
    DEPARTMENT_MEMBERSHIP,
    DEPARTMENT_PROJECT,
    PROJECT_SERVICE,
    SERVICE_DEPENDENCY,
    INCIDENT_IMPACT,
    SERVICE_REGION,
    SERVICE_ENVIRONMENT,
    DOCUMENT_LINK,
}

COUNTS = {
    ROLE: 5,
    USER: 5,
    ABILITY: 4,
    TEAM: 4,
    DEPARTMENT: 6,
    PROJECT: 8,
    SERVICE: 12,
    INCIDENT: 9,
    REGION: 5,
    ENVIRONMENT: 4,
    DOCUMENT: 15,
    SUBSCRIPTION: 4,
    ROLE_ABILITY: 5,
    MEMBERSHIP: 5,
    TEAM_HIERARCHY: 3,
    USER_ROLE_ASSIGNMENT: 7,
    DEPARTMENT_MEMBERSHIP: 7,
    DEPARTMENT_PROJECT: 8,
    PROJECT_SERVICE: 16,
    SERVICE_DEPENDENCY: 14,
    INCIDENT_IMPACT: 9,
    SERVICE_REGION: 12,
    SERVICE_ENVIRONMENT: 14,
    DOCUMENT_LINK: 14,
}
