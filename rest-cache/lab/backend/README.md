# REST Cache Lab Backend

Small FastAPI backend for testing the Varnish REST cache VCL.

Run locally:

```powershell
python -m pip install -e ".[dev]"
rest-cache-lab-backend
```

Useful endpoints:

```text
GET    /healthz
GET    /api/v1/resources
GET    /api/v1/resources/{id}
GET    /api/v1/resources/search?q=value
POST   /api/v1/resources
PUT    /api/v1/resources/{id}
PATCH  /api/v1/resources/{id}
DELETE /api/v1/resources/{id}
GET    /api/v1/users
GET    /api/v1/permissions
```
