'''FastAPI application entry point for DEAL Audio Quality Assessment Dashboard.

This module creates the FastAPI app, registers all API routers,
initialises the async SQLite database, and mounts the static frontend
(build output from Vite) when available.
''' 

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Import routers defined in the `api` package
from .api import auth, admin, process, metrics, eval, audit, dashboard, benchmark

# Database initialisation utilities
from .db import database



def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns
    -------
    FastAPI
        Configured FastAPI instance with routers and startup events.
    """
    app = FastAPI(
        title="DEAL Audio Quality Assessment Dashboard",
        description="Air‑gapped speech‑enhancement and evaluation service",
        version="0.1.0",
    )
    # Enable CORS for development (allow all origins)
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    app.include_router(auth.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(process.router, prefix="/api")
    app.include_router(metrics.router, prefix="/api")
    app.include_router(eval.router, prefix="/api")
    app.include_router(audit.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(benchmark.router, prefix="/api")


    # Startup / shutdown events for the async SQLite engine
    @app.on_event("startup")
    async def on_startup() -> None:
        await database.init_db()

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await database.close_db()

    # Serve static frontend assets if they exist (air‑gapped friendly).
    # The build output is expected under `frontend/dist` relative to the project root.
    try:
        app.mount(
            "/",
            StaticFiles(directory="frontend/dist", html=True),
            name="static",
        )
    except Exception:
        # In development or when the frontend hasn't been built yet we simply ignore.
        pass

    return app


# Instantiate the app for `uvicorn` entry point.
app = create_app()
