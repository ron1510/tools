const dbName = "my_db";
const graphName = "my_graph";

const vertexCollections = [
  "users-data-product.user_roles",
  "veto-data-product.abilities",
];
const edgeCollections = [
  "users-data-product.user_role_subscriptions",
  "veto-data-product.role_abilities",
];

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

const userRoles = db._collection("users-data-product.user_roles");
const abilities = db._collection("veto-data-product.abilities");
const subscriptions = db._collection(
  "users-data-product.user_role_subscriptions"
);
const roleAbilities = db._collection("veto-data-product.role_abilities");

userRoles.truncate();
abilities.truncate();
subscriptions.truncate();
roleAbilities.truncate();

userRoles.insert([
  {
    _key: "admin",
    name: "Admin",
    age: 64,
    priority: 10,
    category: "internal",
    active: true,
    nullable_field: null,
  },
  {
    _key: "editor",
    name: "Editor",
    age: 42,
    priority: 5,
    category: "internal",
    active: true,
  },
  {
    _key: "viewer",
    name: "Viewer",
    age: 21,
    priority: 1,
    category: "external",
    active: false,
  },
  {
    _key: "auditor",
    name: "Auditor",
    age: 85,
    priority: 7,
    category: "external",
    active: true,
  },
]);

abilities.insert([
  { _key: "read", name: "Read", severity: 1 },
  { _key: "write", name: "Write", severity: 5 },
  { _key: "delete", name: "Delete", severity: 9 },
]);

subscriptions.insert([
  {
    _key: "editor-to-admin",
    _from: "users-data-product.user_roles/editor",
    _to: "users-data-product.user_roles/admin",
    relationship: "reports_to",
    weight: 1,
  },
  {
    _key: "viewer-to-editor",
    _from: "users-data-product.user_roles/viewer",
    _to: "users-data-product.user_roles/editor",
    relationship: "reports_to",
    weight: 2,
  },
  {
    _key: "auditor-to-admin",
    _from: "users-data-product.user_roles/auditor",
    _to: "users-data-product.user_roles/admin",
    relationship: "reports_to",
    weight: 3,
  },
]);

roleAbilities.insert([
  {
    _key: "admin-delete",
    _from: "users-data-product.user_roles/admin",
    _to: "veto-data-product.abilities/delete",
  },
  {
    _key: "admin-write",
    _from: "users-data-product.user_roles/admin",
    _to: "veto-data-product.abilities/write",
  },
  {
    _key: "editor-write",
    _from: "users-data-product.user_roles/editor",
    _to: "veto-data-product.abilities/write",
  },
  {
    _key: "viewer-read",
    _from: "users-data-product.user_roles/viewer",
    _to: "veto-data-product.abilities/read",
  },
]);

graphModule._create(
  graphName,
  [
    graphModule._relation(
      "users-data-product.user_role_subscriptions",
      ["users-data-product.user_roles"],
      ["users-data-product.user_roles"]
    ),
    graphModule._relation(
      "veto-data-product.role_abilities",
      ["users-data-product.user_roles"],
      ["veto-data-product.abilities"]
    ),
  ],
  []
);

print(JSON.stringify({
  database: dbName,
  graph: graphName,
  vertexCollections,
  edgeCollections,
  userRoles: userRoles.count(),
  abilities: abilities.count(),
  subscriptions: subscriptions.count(),
  roleAbilities: roleAbilities.count(),
}, null, 2));
