const dbName = "my_db";
const graphName = "my_graph";

// This seed is deliberately small enough to understand by inspection but broad
// enough to exercise the compiler's important assumptions:
//
// - multiple vertex collections prove `get(a, b)` and label selection
// - multiple edge collections prove traversal labels are real Arango
//   collections, not synthetic Gremlin-only names
// - same-type edges and cross-type edges prove `into(label)` filtering
// - numeric, boolean, string, missing, and null-like fields prove match and
//   projection behavior
// - multi-hop chains prove `min_depth` / `max_depth`
const collections = {
  roles: "users-data-product.user_roles",
  users: "users-data-product.users",
  abilities: "permissions-data-product.abilities",
  teams: "org-data-product.teams",
  departments: "org-data-product.departments",
  projects: "delivery-data-product.projects",
  services: "platform-data-product.services",
  incidents: "ops-data-product.incidents",
  regions: "infra-data-product.regions",
  environments: "infra-data-product.environments",
  documents: "knowledge-data-product.documents",
  subscriptions: "users-data-product.user_role_subscriptions",
  roleAbilities: "permissions-data-product.role_abilities",
  memberships: "org-data-product.user_memberships",
  teamHierarchy: "org-data-product.team_hierarchy",
  userRoleAssignments: "users-data-product.user_role_assignments",
  departmentMemberships: "org-data-product.department_memberships",
  departmentProjects: "delivery-data-product.department_projects",
  projectServices: "platform-data-product.project_services",
  serviceDependencies: "platform-data-product.service_dependencies",
  incidentImpacts: "ops-data-product.incident_impacts",
  serviceRegions: "infra-data-product.service_regions",
  serviceEnvironments: "infra-data-product.service_environments",
  documentLinks: "knowledge-data-product.document_links",
};

const vertexCollections = [
  collections.roles,
  collections.users,
  collections.abilities,
  collections.teams,
  collections.departments,
  collections.projects,
  collections.services,
  collections.incidents,
  collections.regions,
  collections.environments,
  collections.documents,
];
const edgeCollections = [
  collections.subscriptions,
  collections.roleAbilities,
  collections.memberships,
  collections.teamHierarchy,
  collections.userRoleAssignments,
  collections.departmentMemberships,
  collections.departmentProjects,
  collections.projectServices,
  collections.serviceDependencies,
  collections.incidentImpacts,
  collections.serviceRegions,
  collections.serviceEnvironments,
  collections.documentLinks,
];

// The script is idempotent for a disposable lab: it recreates the graph and
// truncates all involved collections so repeated e2e runs start from the same
// known state.
if (!db._databases().includes(dbName)) {
  db._createDatabase(dbName);
}

db._useDatabase(dbName);

const graphModule = require("@arangodb/general-graph");

if (graphModule._exists(graphName)) {
  graphModule._drop(graphName, true);
}

for (const name of vertexCollections) {
  if (!db._collection(name)) {
    db._create(name);
  }
}

for (const name of edgeCollections) {
  if (!db._collection(name)) {
    db._createEdgeCollection(name);
  }
}

const roles = db._collection(collections.roles);
const users = db._collection(collections.users);
const abilities = db._collection(collections.abilities);
const teams = db._collection(collections.teams);
const departments = db._collection(collections.departments);
const projects = db._collection(collections.projects);
const services = db._collection(collections.services);
const incidents = db._collection(collections.incidents);
const regions = db._collection(collections.regions);
const environments = db._collection(collections.environments);
const documents = db._collection(collections.documents);
const subscriptions = db._collection(collections.subscriptions);
const roleAbilities = db._collection(collections.roleAbilities);
const memberships = db._collection(collections.memberships);
const teamHierarchy = db._collection(collections.teamHierarchy);
const userRoleAssignments = db._collection(collections.userRoleAssignments);
const departmentMemberships = db._collection(collections.departmentMemberships);
const departmentProjects = db._collection(collections.departmentProjects);
const projectServices = db._collection(collections.projectServices);
const serviceDependencies = db._collection(collections.serviceDependencies);
const incidentImpacts = db._collection(collections.incidentImpacts);
const serviceRegions = db._collection(collections.serviceRegions);
const serviceEnvironments = db._collection(collections.serviceEnvironments);
const documentLinks = db._collection(collections.documentLinks);

for (const collection of [
  roles,
  users,
  abilities,
  teams,
  departments,
  projects,
  services,
  incidents,
  regions,
  environments,
  documents,
  subscriptions,
  roleAbilities,
  memberships,
  teamHierarchy,
  userRoleAssignments,
  departmentMemberships,
  departmentProjects,
  projectServices,
  serviceDependencies,
  incidentImpacts,
  serviceRegions,
  serviceEnvironments,
  documentLinks,
]) {
  collection.truncate();
}

roles.insert([
  {
    _key: "admin",
    name: "Admin",
    age: 64,
    score: 98.5,
    priority: 10,
    category: "internal",
    active: true,
    nullable_field: null,
  },
  {
    _key: "editor",
    name: "Editor",
    age: 42,
    score: 77.25,
    priority: 5,
    category: "internal",
    active: true,
  },
  {
    _key: "viewer",
    name: "Viewer",
    age: 21,
    score: 12.5,
    priority: 1,
    category: "external",
    active: false,
  },
  {
    _key: "auditor",
    name: "Auditor",
    age: 85,
    score: 64.75,
    priority: 7,
    category: "external",
    active: true,
  },
  {
    _key: "owner",
    name: "Owner",
    age: 91,
    score: 100.0,
    priority: 11,
    category: "internal",
    active: true,
  },
]);

// User documents are intentionally separate from role documents. This prevents
// e2e tests from accidentally passing only because every traversal stays inside
// one domain.
users.insert([
  { _key: "alice", name: "Alice Admin", email: "alice@example.test", active: true },
  { _key: "bob", name: "Bob Editor", email: "bob@example.test", active: true },
  { _key: "carol", name: "Carol Viewer", email: "carol@example.test", active: false },
  { _key: "dave", name: "Dave Auditor", email: "dave@example.test", active: true },
  { _key: "erin", name: "Erin Owner", email: "erin@example.test", active: true },
]);

// Ability severities give containment and numeric predicate tests a second
// collection that is independent from role ages and scores.
abilities.insert([
  { _key: "read", name: "Read", severity: 1 },
  { _key: "write", name: "Write", severity: 5 },
  { _key: "delete", name: "Delete", severity: 9 },
  { _key: "approve", name: "Approve", severity: 7 },
]);

// Team hierarchy creates another directed graph section so traversal behavior is
// tested outside the role-subscription chain.
teams.insert([
  { _key: "platform", name: "Platform", tier: 2, active: true },
  { _key: "security", name: "Security", tier: 2, active: true },
  { _key: "executive", name: "Executive", tier: 1, active: true },
  { _key: "qa", name: "QA", tier: 3, active: false },
]);

departments.insert([
  { _key: "eng", name: "Engineering", region: "global", active: true },
  { _key: "security", name: "Security", region: "global", active: true },
  { _key: "product", name: "Product", region: "us", active: true },
  { _key: "data", name: "Data", region: "eu", active: true },
  { _key: "ops", name: "Operations", region: "global", active: true },
  { _key: "support", name: "Support", region: "apac", active: false },
]);

projects.insert(
  Array.from({ length: 8 }, (_unused, index) => ({
    _key: `project-${index}`,
    name: `Project ${index}`,
    tier: (index % 3) + 1,
    active: index !== 7,
  }))
);

services.insert(
  Array.from({ length: 12 }, (_unused, index) => ({
    _key: `service-${index}`,
    name: `Service ${index}`,
    priority: index + 1,
    active: index % 3 !== 0,
    category: index % 2 === 0 ? "core" : "edge",
  }))
);

incidents.insert(
  Array.from({ length: 9 }, (_unused, index) => ({
    _key: `incident-${index}`,
    name: `Incident ${index}`,
    severity: (index % 5) + 1,
    open: index % 2 === 0,
  }))
);

regions.insert(
  ["us-east", "us-west", "eu-central", "ap-south", "global"].map((key, index) => ({
    _key: key,
    name: key,
    tier: index + 1,
  }))
);

environments.insert(
  ["dev", "stage", "prod", "dr"].map((key, index) => ({
    _key: key,
    name: key,
    production: key === "prod" || key === "dr",
    rank: index + 1,
  }))
);

documents.insert(
  Array.from({ length: 15 }, (_unused, index) => ({
    _key: `doc-${index}`,
    title: `Document ${index}`,
    public: index % 2 === 0,
  }))
);

// Role subscriptions are same-label role -> role edges. The edge documents have
// properties so tests can project edge fields before calling `into(...)`.
subscriptions.insert([
  {
    _key: "editor-to-admin",
    _from: `${collections.roles}/editor`,
    _to: `${collections.roles}/admin`,
    relationship: "reports_to",
    weight: 1,
  },
  {
    _key: "viewer-to-editor",
    _from: `${collections.roles}/viewer`,
    _to: `${collections.roles}/editor`,
    relationship: "reports_to",
    weight: 2,
  },
  {
    _key: "auditor-to-admin",
    _from: `${collections.roles}/auditor`,
    _to: `${collections.roles}/admin`,
    relationship: "reports_to",
    weight: 3,
  },
  {
    _key: "admin-to-owner",
    _from: `${collections.roles}/admin`,
    _to: `${collections.roles}/owner`,
    relationship: "reports_to",
    weight: 4,
  },
]);

// Role abilities are cross-label role -> ability edges. They prove that
// `into('permissions-data-product.abilities')` filters endpoint labels correctly.
roleAbilities.insert([
  {
    _key: "admin-delete",
    _from: `${collections.roles}/admin`,
    _to: `${collections.abilities}/delete`,
  },
  {
    _key: "admin-write",
    _from: `${collections.roles}/admin`,
    _to: `${collections.abilities}/write`,
  },
  {
    _key: "admin-approve",
    _from: `${collections.roles}/admin`,
    _to: `${collections.abilities}/approve`,
  },
  {
    _key: "editor-write",
    _from: `${collections.roles}/editor`,
    _to: `${collections.abilities}/write`,
  },
  {
    _key: "viewer-read",
    _from: `${collections.roles}/viewer`,
    _to: `${collections.abilities}/read`,
  },
]);

// Memberships give the suite a user -> team traversal independent of roles.
memberships.insert([
  {
    _key: "alice-platform",
    _from: `${collections.users}/alice`,
    _to: `${collections.teams}/platform`,
    role: "lead",
    allocation: 1.0,
  },
  {
    _key: "bob-platform",
    _from: `${collections.users}/bob`,
    _to: `${collections.teams}/platform`,
    role: "member",
    allocation: 0.75,
  },
  {
    _key: "carol-security",
    _from: `${collections.users}/carol`,
    _to: `${collections.teams}/security`,
    role: "member",
    allocation: 0.5,
  },
  {
    _key: "dave-security",
    _from: `${collections.users}/dave`,
    _to: `${collections.teams}/security`,
    role: "lead",
    allocation: 1.0,
  },
  {
    _key: "erin-executive",
    _from: `${collections.users}/erin`,
    _to: `${collections.teams}/executive`,
    role: "owner",
    allocation: 1.0,
  },
]);

// Team hierarchy is a directed multi-hop chain. It is used to validate deep
// traversal with intermediate vertex results.
teamHierarchy.insert([
  {
    _key: "platform-to-executive",
    _from: `${collections.teams}/platform`,
    _to: `${collections.teams}/executive`,
    relationship: "rolls_up_to",
    depth_hint: 1,
  },
  {
    _key: "security-to-executive",
    _from: `${collections.teams}/security`,
    _to: `${collections.teams}/executive`,
    relationship: "rolls_up_to",
    depth_hint: 1,
  },
  {
    _key: "qa-to-platform",
    _from: `${collections.teams}/qa`,
    _to: `${collections.teams}/platform`,
    relationship: "rolls_up_to",
    depth_hint: 2,
  },
]);

userRoleAssignments.insert([
  {
    _key: "alice-admin",
    _from: `${collections.users}/alice`,
    _to: `${collections.roles}/admin`,
  },
  {
    _key: "bob-editor",
    _from: `${collections.users}/bob`,
    _to: `${collections.roles}/editor`,
  },
  {
    _key: "carol-viewer",
    _from: `${collections.users}/carol`,
    _to: `${collections.roles}/viewer`,
  },
  {
    _key: "dave-auditor",
    _from: `${collections.users}/dave`,
    _to: `${collections.roles}/auditor`,
  },
  {
    _key: "erin-owner",
    _from: `${collections.users}/erin`,
    _to: `${collections.roles}/owner`,
  },
  {
    _key: "alice-owner",
    _from: `${collections.users}/alice`,
    _to: `${collections.roles}/owner`,
  },
  {
    _key: "bob-viewer",
    _from: `${collections.users}/bob`,
    _to: `${collections.roles}/viewer`,
  },
]);

departmentMemberships.insert([
  {
    _key: "alice-eng",
    _from: `${collections.users}/alice`,
    _to: `${collections.departments}/eng`,
  },
  {
    _key: "bob-eng",
    _from: `${collections.users}/bob`,
    _to: `${collections.departments}/eng`,
  },
  {
    _key: "carol-security",
    _from: `${collections.users}/carol`,
    _to: `${collections.departments}/security`,
  },
  {
    _key: "dave-ops",
    _from: `${collections.users}/dave`,
    _to: `${collections.departments}/ops`,
  },
  {
    _key: "erin-product",
    _from: `${collections.users}/erin`,
    _to: `${collections.departments}/product`,
  },
  {
    _key: "alice-data",
    _from: `${collections.users}/alice`,
    _to: `${collections.departments}/data`,
  },
  {
    _key: "bob-support",
    _from: `${collections.users}/bob`,
    _to: `${collections.departments}/support`,
  },
]);

departmentProjects.insert([
  ["eng", "project-0"],
  ["eng", "project-1"],
  ["security", "project-2"],
  ["product", "project-3"],
  ["product", "project-4"],
  ["data", "project-5"],
  ["ops", "project-6"],
  ["support", "project-7"],
].map(([department, project]) => ({
  _key: `${department}-${project}`,
  _from: `${collections.departments}/${department}`,
  _to: `${collections.projects}/${project}`,
})));

projectServices.insert(
  Array.from({ length: 8 }, (_unused, index) => ([
    {
      _key: `project-${index}-service-${index}`,
      _from: `${collections.projects}/project-${index}`,
      _to: `${collections.services}/service-${index}`,
    },
    {
      _key: `project-${index}-service-${(index + 4) % 12}`,
      _from: `${collections.projects}/project-${index}`,
      _to: `${collections.services}/service-${(index + 4) % 12}`,
    },
  ])).flat()
);

serviceDependencies.insert([
  ...Array.from({ length: 11 }, (_unused, index) => ({
    _key: `service-${index}-service-${index + 1}`,
    _from: `${collections.services}/service-${index}`,
    _to: `${collections.services}/service-${index + 1}`,
  })),
  {
    _key: "service-0-service-5",
    _from: `${collections.services}/service-0`,
    _to: `${collections.services}/service-5`,
  },
  {
    _key: "service-2-service-7",
    _from: `${collections.services}/service-2`,
    _to: `${collections.services}/service-7`,
  },
  {
    _key: "service-5-service-11",
    _from: `${collections.services}/service-5`,
    _to: `${collections.services}/service-11`,
  },
]);

incidentImpacts.insert(
  Array.from({ length: 9 }, (_unused, index) => ({
    _key: `incident-${index}-service-${index % 12}`,
    _from: `${collections.incidents}/incident-${index}`,
    _to: `${collections.services}/service-${index % 12}`,
    impact: index % 3 === 0 ? "high" : "medium",
  }))
);

serviceRegions.insert(
  Array.from({ length: 12 }, (_unused, index) => ({
    _key: `service-${index}-region-${index % 5}`,
    _from: `${collections.services}/service-${index}`,
    _to: `${collections.regions}/${["us-east", "us-west", "eu-central", "ap-south", "global"][index % 5]}`,
  }))
);

serviceEnvironments.insert([
  ...Array.from({ length: 12 }, (_unused, index) => ({
    _key: `service-${index}-${index % 2 === 0 ? "prod" : "stage"}`,
    _from: `${collections.services}/service-${index}`,
    _to: `${collections.environments}/${index % 2 === 0 ? "prod" : "stage"}`,
  })),
  {
    _key: "service-0-dev",
    _from: `${collections.services}/service-0`,
    _to: `${collections.environments}/dev`,
  },
  {
    _key: "service-0-dr",
    _from: `${collections.services}/service-0`,
    _to: `${collections.environments}/dr`,
  },
]);

documentLinks.insert(
  Array.from({ length: 14 }, (_unused, index) => ({
    _key: `doc-${index}-doc-${index + 1}`,
    _from: `${collections.documents}/doc-${index}`,
    _to: `${collections.documents}/doc-${index + 1}`,
  }))
);

// The graph definition mirrors the COMPLEX edge definitions rendered into the
// Gremlin Server chart values. If these diverge, the provider may expose labels
// differently from the seeded Arango graph.
graphModule._create(
  graphName,
  [
    graphModule._relation(
      collections.subscriptions,
      [collections.roles],
      [collections.roles]
    ),
    graphModule._relation(
      collections.roleAbilities,
      [collections.roles],
      [collections.abilities]
    ),
    graphModule._relation(
      collections.memberships,
      [collections.users],
      [collections.teams]
    ),
    graphModule._relation(
      collections.teamHierarchy,
      [collections.teams],
      [collections.teams]
    ),
    graphModule._relation(
      collections.userRoleAssignments,
      [collections.users],
      [collections.roles]
    ),
    graphModule._relation(
      collections.departmentMemberships,
      [collections.users],
      [collections.departments]
    ),
    graphModule._relation(
      collections.departmentProjects,
      [collections.departments],
      [collections.projects]
    ),
    graphModule._relation(
      collections.projectServices,
      [collections.projects],
      [collections.services]
    ),
    graphModule._relation(
      collections.serviceDependencies,
      [collections.services],
      [collections.services]
    ),
    graphModule._relation(
      collections.incidentImpacts,
      [collections.incidents],
      [collections.services]
    ),
    graphModule._relation(
      collections.serviceRegions,
      [collections.services],
      [collections.regions]
    ),
    graphModule._relation(
      collections.serviceEnvironments,
      [collections.services],
      [collections.environments]
    ),
    graphModule._relation(
      collections.documentLinks,
      [collections.documents],
      [collections.documents]
    ),
  ],
  []
);

print(JSON.stringify({
  database: dbName,
  graph: graphName,
  vertexCollections,
  edgeCollections,
  roles: roles.count(),
  users: users.count(),
  abilities: abilities.count(),
  teams: teams.count(),
  departments: departments.count(),
  projects: projects.count(),
  services: services.count(),
  incidents: incidents.count(),
  regions: regions.count(),
  environments: environments.count(),
  documents: documents.count(),
  subscriptions: subscriptions.count(),
  roleAbilities: roleAbilities.count(),
  memberships: memberships.count(),
  teamHierarchy: teamHierarchy.count(),
  userRoleAssignments: userRoleAssignments.count(),
  departmentMemberships: departmentMemberships.count(),
  departmentProjects: departmentProjects.count(),
  projectServices: projectServices.count(),
  serviceDependencies: serviceDependencies.count(),
  incidentImpacts: incidentImpacts.count(),
  serviceRegions: serviceRegions.count(),
  serviceEnvironments: serviceEnvironments.count(),
  documentLinks: documentLinks.count(),
}, null, 2));
