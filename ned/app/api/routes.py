"""REST API routes.

All analysis is local and stateless: NED stores nothing, logs no input, and has
no database, no accounts and no telemetry.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import (
    AnalysisResult,
    AnalyzeRequest,
    AsymmetryRequest,
    AsymmetryResult,
    ExampleCase,
    FnbpRequest,
    FnbpResult,
    HealthResponse,
    ModeDescription,
    VersionResponse,
)
from ned.app.providers import available_providers
from ned.app.version import (
    API_VERSION,
    ENGINE_NAME,
    FULL_NAME,
    MOTTO,
    NAME,
    TAGLINE,
    __version__,
)

router = APIRouter(prefix="/api", tags=["ned"])


def get_analyzer(request: Request) -> NedAnalyzer:
    """Fetch the process-wide analyzer from application state."""

    analyzer: NedAnalyzer | None = getattr(request.app.state, "analyzer", None)
    if analyzer is None:  # pragma: no cover - only if the app was built oddly
        raise HTTPException(status_code=503, detail="analyzer is not initialised")
    return analyzer


@router.get("/health", response_model=HealthResponse, summary="Liveness and provenance")
def health(request: Request) -> HealthResponse:
    """Report that the service is up, and which engine is answering."""

    started = float(getattr(request.app.state, "started_at", time.time()))
    return HealthResponse(
        status="ok",
        version=__version__,
        uptime_seconds=round(max(0.0, time.time() - started), 3),
        local_only=True,
        engine=ENGINE_NAME,
    )


@router.get("/version", response_model=VersionResponse, summary="Version and identity")
def version() -> VersionResponse:
    """Single-source version information (``ned/app/version.py``)."""

    return VersionResponse(
        name=NAME,
        full_name=FULL_NAME,
        version=__version__,
        api_version=API_VERSION,
        python=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        tagline=TAGLINE,
        motto=MOTTO,
    )


@router.get("/modes", response_model=list[ModeDescription], summary="Available analysis modes")
def modes(request: Request) -> list[ModeDescription]:
    """The modes configured in ``rules/modes.json``."""

    return get_analyzer(request).modes()


@router.get("/examples", summary="Shipped example cases")
def examples(request: Request) -> dict[str, list[ExampleCase]]:
    """Example inputs. These are synthetic cases, never collected user data."""

    return {"cases": get_analyzer(request).examples()}


@router.get("/providers", summary="Explanation providers")
def providers(request: Request) -> dict[str, Any]:
    """Registered explanation providers and the active one."""

    analyzer = get_analyzer(request)
    return {
        "available": available_providers(),
        "active": analyzer.provider_key,
        "active_engine": analyzer.provider.name,
        "offline": bool(analyzer.provider.offline),
        "note": (
            "v0.1 ships the offline rule provider only. The 'llm' provider is a "
            "declared stub that raises; NED never sends your text anywhere."
        ),
    }


@router.get("/rules", summary="Rule-pack provenance")
def rules(request: Request) -> dict[str, Any]:
    """Which rule packs produced this server's behaviour."""

    book = get_analyzer(request).book
    return {
        "rules_version": book.version,
        "source_dir": str(book.source_dir),
        "signal_rules": len(book.signals),
        "escape_tiers": len(book.escape_tiers),
        "keyword_escapes": len(book.keyword_escapes),
        "verdict_rules": len(book.verdicts),
        "easter_eggs": len(book.easter_eggs),
        "modes": book.mode_ids,
    }


@router.get("/easter-eggs", summary="Cosmetic easter eggs")
def easter_eggs(request: Request) -> dict[str, Any]:
    """Easter eggs are cosmetic and never affect a verdict."""

    book = get_analyzer(request).book
    return {
        "eggs": [
            {"id": egg.id, "trigger": egg.trigger, "note": egg.message.get("en", "")}
            for egg in book.easter_eggs
        ],
        "note": "Easter eggs are decorative. They never change the verdict.",
    }


@router.post("/analyze", response_model=AnalysisResult, summary="Analyze one message or event")
def analyze(payload: AnalyzeRequest, request: Request) -> AnalysisResult:
    """Run the full PED / NEA / Semantic Escape pipeline on one input."""

    return get_analyzer(request).analyze(payload)


@router.post("/asymmetry", response_model=AsymmetryResult, summary="Compare two evidence standards")
def asymmetry(payload: AsymmetryRequest, request: Request) -> AsymmetryResult:
    """Detect evidence-standard asymmetry (the double standard detector)."""

    if not (payload.positive_text or payload.negative_text or payload.text or payload.events):
        raise HTTPException(
            status_code=422,
            detail=(
                "supply positive_text and negative_text, or text, or events — "
                "NED cannot compare evidence it has not been given."
            ),
        )
    return get_analyzer(request).compare(payload)


@router.post("/fnbp", response_model=FnbpResult, summary="Fuyuki Notification Branch Predictor")
def fnbp(payload: FnbpRequest, request: Request) -> FnbpResult:
    """The Lab easter egg. Fuyuki is a fictional codename, not a real person."""

    language = (
        "zh"
        if _looks_chinese(" ".join([payload.expected_sender, *payload.actual_senders]))
        else "en"
    )
    return get_analyzer(request).fnbp_analysis(payload, language=language)


def _looks_chinese(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


__all__ = ["router"]
