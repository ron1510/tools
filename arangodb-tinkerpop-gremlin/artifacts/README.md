# Gremlin ArangoDB Image Archive

This directory contains a portable Docker archive for the Gremlin Server image
validated against ArangoDB `3.11.14`.

Image:

```text
ron1510/gremlin-arangodb:3.8.1-arangodb-4.0.0-arango311
```

Registry digest:

```text
sha256:bee0ad2ca8ed566218f0b18aad0e03432ff2a36622057bf5a1c6ec978b577eb6
```

Archive:

```text
gremlin-arangodb-3.8.1-provider-4.0.0-arango311.tar
```

Archive SHA-256:

```text
b5435488c73209312c68d7a945a49a25a22d6eb104b69f1802ba70ebcc31761b
```

Load the archive:

```powershell
docker load -i .\gremlin-arangodb-3.8.1-provider-4.0.0-arango311.tar
```

Tag and push it to another organization:

```powershell
docker tag ron1510/gremlin-arangodb:3.8.1-arangodb-4.0.0-arango311 `
  <registry>/<organization>/gremlin-arangodb:3.8.1-arangodb-4.0.0-arango311

docker push <registry>/<organization>/gremlin-arangodb:3.8.1-arangodb-4.0.0-arango311
```

The archive is tracked with Git LFS because normal Git hosting rejects files of
this size. Install Git LFS before cloning or pulling the artifact:

```powershell
git lfs install
git lfs pull
```
