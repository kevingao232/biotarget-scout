"""FastAPI application: API routes + static test UI."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from importlib import metadata
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from biotarget_scout.core.config import ensure_hf_hub_token
from biotarget_scout.core.logging import configure_logging

from biotarget_scout.api.routes.hypothesis import router as hypothesis_router


def _resolve_web_dir() -> Path:
    """Find ``web/`` for both editable (src layout) and installed (e.g. Docker) layouts."""
    override = os.getenv("BIOTARGET_WEB_DIR", "").strip()
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    for base in here.parents:
        w = base / "web"
        if (w / "index.html").is_file():
            return w
    cwd_web = Path.cwd() / "web"
    if (cwd_web / "index.html").is_file():
        return cwd_web
    return here.parents[3] / "web"


WEB_DIR = _resolve_web_dir()
WEB_STATIC = WEB_DIR / "static"


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    ensure_hf_hub_token()
    configure_logging(os.getenv("LOG_LEVEL"))
    yield


def _package_version() -> str:
    try:
        return metadata.version("biotarget-scout")
    except metadata.PackageNotFoundError:
        return "0.1.0"


def create_app() -> FastAPI:
    app = FastAPI(
        title="BioTarget Scout API",
        description="Hypothesis pipeline over literature, KG, and omics legs.",
        version=_package_version(),
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:8000",
            "http://localhost:8000",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(hypothesis_router, prefix="/api/v1")

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": _package_version()}

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        """Browsers request this automatically; avoid noisy 404 in access logs."""
        return Response(status_code=204)

    @app.get("/", response_model=None)
    async def serve_ui() -> FileResponse | PlainTextResponse:
        index = WEB_DIR / "index.html"
        if not index.is_file():
            return PlainTextResponse(
                "BioTarget Scout API — UI missing. Add web/index.html or open /docs",
                status_code=404,
            )
        return FileResponse(index)

    if WEB_STATIC.is_dir():
        app.mount("/static", StaticFiles(directory=str(WEB_STATIC)), name="static")

    return app


app = create_app()
