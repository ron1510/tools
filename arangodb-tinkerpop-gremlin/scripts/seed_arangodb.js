const dbName = "my_db";
const graphName = "my_graph";
const vertexCollection = "services";
const edgeCollection = "depends_on";

if (!db._databases().includes(dbName)) {
  db._createDatabase(dbName);
}

db._useDatabase(dbName);

const graphModule = require("@arangodb/general-graph");
const relation = graphModule._relation(edgeCollection, [vertexCollection], [vertexCollection]);

if (!graphModule._exists(graphName)) {
  graphModule._create(graphName, [relation], [vertexCollection]);
}

const services = db._collection(vertexCollection);
const dependsOn = db._collection(edgeCollection);

const apiKey = `${vertexCollection}/api`;
const workerKey = `${vertexCollection}/worker`;

if (!services.exists("api")) {
  services.insert({ _key: "api", name: "api", kind: "service" });
}

if (!services.exists("worker")) {
  services.insert({ _key: "worker", name: "worker", kind: "service" });
}

if (!dependsOn.exists("api-depends-on-worker")) {
  dependsOn.insert({
    _key: "api-depends-on-worker",
    _from: apiKey,
    _to: workerKey,
    relationship: "depends_on"
  });
}

print(JSON.stringify({
  database: dbName,
  graph: graphName,
  vertexCollection,
  edgeCollection,
  vertices: services.count(),
  edges: dependsOn.count()
}, null, 2));
