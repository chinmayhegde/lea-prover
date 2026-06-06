"""FastAPI app factory — mounts the v1 routers, wiring, and error handling.

``create_app`` is the single composition root. ``manager`` is injectable so
tests can drive the run bridge with a scripted generator (no model spend); when
omitted, a default ``RunManager`` backed by ``agent.run_events`` is created.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lea.errors import LeaError

from .auth import AuthDep
from .errors import lea_error_handler
from .jobs import RunManager
from .routers import config as config_router
from .routers import meta as meta_router
from .routers import runs as runs_router
from .routers import tools as tools_router
from .routers import verify as verify_router
from .settings import Settings, get_settings


def create_app(settings: Settings | None = None, manager: RunManager | None = None) -> FastAPI:
    settings = settings or get_settings()
    manager = manager or RunManager(max_concurrent_runs=settings.max_concurrent_runs)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Bind the running loop so worker threads can hand frames to subscribers.
        manager.bind_loop(asyncio.get_running_loop())
        yield
        manager.shutdown()

    app = FastAPI(title="Lea API", version="1", lifespan=lifespan)
    app.state.settings = settings
    app.state.manager = manager

    app.add_exception_handler(LeaError, lea_error_handler)

    # All v1 routes carry the (optionally enforced) bearer dependency, except the
    # meta router (healthz/version/capabilities stay open for probes).
    guarded = [runs_router.router, config_router.router, tools_router.router,
               verify_router.router]
    for r in guarded:
        app.include_router(r, prefix="/v1", dependencies=[AuthDep])
    app.include_router(meta_router.router, prefix="/v1")

    return app
