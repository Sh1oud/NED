"""FastAPI application factory and default ASGI app."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ned.app.api.routes import router
from ned.app.core.analyzer import NedAnalyzer
from ned.app.ui.personality import web_personality_catalog
from ned.app.version import (
    DISCLAIMER,
    FULL_NAME,
    MOTTO,
    NAME,
    PRIVACY_NOTE,
    SUBTITLE,
    TAGLINE,
    __version__,
)

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"
TEMPLATES_DIR = PACKAGE_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the rule packs once, at startup."""

    app.state.analyzer = NedAnalyzer()
    app.state.started_at = time.time()
    yield


def create_app() -> FastAPI:
    """Build the ASGI application."""

    app = FastAPI(
        title=f"{NAME} — {FULL_NAME}",
        summary="An offline, satirical emotional evidence de-weighting engine.",
        description=(
            f"{TAGLINE}\n\n"
            "NED detects possible positive-affection signals, generates alternative "
            "explanations, discounts the evidence, and reports a verdict — all offline, "
            "with no database, no accounts, no telemetry and no paid APIs.\n\n"
            "**NED cannot determine whether someone likes you. Humans are not APIs.**"
        ),
        version=__version__,
        lifespan=lifespan,
        contact={
            "name": "NED Contributors",
            "url": "https://github.com/Sh1oud/NED",
        },
        license_info={"name": "MIT"},
    )
    app.include_router(router)

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    def _template_context(analyzer: NedAnalyzer | None) -> dict[str, object]:
        instance = analyzer or NedAnalyzer()
        return {
            "version": __version__,
            "name": NAME,
            "full_name": FULL_NAME,
            "subtitle": SUBTITLE,
            "tagline": TAGLINE,
            "motto": MOTTO,
            "modes": [mode.model_dump() for mode in instance.modes()],
            "modes_default": next(iter(instance.book.modes.keys()), "normal"),
            "reaching_labels": [band.model_dump() for band in instance.book.scoring.reaching_bands],
            "examples": [case.model_dump() for case in instance.examples()],
            "disclaimer": instance.book.disclaimer or DISCLAIMER,
            "privacy_note": PRIVACY_NOTE,
            "personality_catalog": web_personality_catalog(),
        }

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index(request: Request) -> HTMLResponse:
        """Serve the single-page web UI."""

        index_file = TEMPLATES_DIR / "index.html"
        if not index_file.is_file():  # pragma: no cover - defensive
            return HTMLResponse(
                "<h1>NED</h1><p>The web UI template is missing from this installation. "
                "The API is still available at <a href='/docs'>/docs</a>.</p>",
                status_code=200,
            )
        analyzer = getattr(request.app.state, "analyzer", None)
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=_template_context(analyzer),
        )

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        """Fail with a structured error instead of leaking a stack trace."""

        return JSONResponse(
            status_code=500,
            content={
                "detail": "NED failed to analyse this input.",
                "error": type(exc).__name__,
                "hint": "NED is satire software; it should never be load-bearing.",
            },
        )

    return app


app = create_app()

__all__ = ["app", "create_app"]
