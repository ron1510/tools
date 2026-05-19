# fastapi-service-runtime

`fastapi-service-runtime` is an internal package workspace for shared FastAPI service runtime code that is intended to ship inside a common base image.

It currently provides these importable packages:

- `fastapi_settings`
- `fastapi_logging`
- `fastapi_observability`
- `fastapi_health`
- `fastapi_lifespan`
- `fastapi_app_state`
- `fastapi_state`
- `fastapi_demo_service`

## What It Is For

This tool is the common runtime ground for long-lived FastAPI services.

It standardizes:

- typed environment-backed settings
- logging bootstrap
- OpenTelemetry bootstrap
- FastAPI lifespan handling
- health and readiness endpoints
- app state and reusable in-memory state patterns

## Demo Worker

The reference consumer is `fastapi_demo_service`, a small FastAPI app that exercises the runtime stack end to end.

Run it with:

```powershell
$env:SERVICE_NAME="fastapi-demo-service"
fastapi-demo-service
```

## Testing

```powershell
pytest
```
