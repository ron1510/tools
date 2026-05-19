from __future__ import annotations

import uvicorn

from fastapi_demo_service.app import create_app
from fastapi_demo_service.settings import DemoFastAPISettings
from fastapi_logging import configure_logging


def main() -> int:
    settings = DemoFastAPISettings.from_env()
    configure_logging(settings.log_level)
    app = create_app(settings)
    try:
        uvicorn.run(
            app,
            host=settings.app_host,
            port=settings.app_port,
            log_level=settings.log_level.lower(),
            access_log=False,
        )
    except SystemExit as exc:
        if exc.code not in (None, 0, 3):
            raise
    except KeyboardInterrupt:
        pass
    return 0
