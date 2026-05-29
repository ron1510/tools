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
  abilities: "veto-data-product.abilities",
  teams: "org-data-product.teams",
  subscriptions: "users-data-product.user_role_subscriptions",
  roleAbilities: "veto-data-product.role_abilities",
  memberships: "org-data-product.user_memberships",
  teamHierarchy: "org-data-product.team_hierarchy",
};

const vertexCollections = [
  collections.roles,
  collections.users,
  collections.abilities,
  collections.teams,
];
const edgeCollections = [
  collections.subscriptions,
  collections.roleAbilities,
  collections.memberships,
  collections.teamHierarchy,
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
const subscriptions = db._collection(collections.subscriptions);
const roleAbilities = db._collection(collections.roleAbilities);
const memberships = db._collection(collections.memberships);
const teamHierarchy = db._collection(collections.teamHierarchy);

for (const collection of [
  roles,
  users,
  abilities,
  teams,
  subscriptions,
  roleAbilities,
  memberships,
  teamHierarchy,
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
// `into('veto-data-product.abilities')` filters endpoint labels correctly.
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
  subscriptions: subscriptions.count(),
  roleAbilities: roleAbilities.count(),
  memberships: memberships.count(),
  teamHierarchy: teamHierarchy.count(),
}, null, 2));
