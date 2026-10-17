"""FastAPI service: the v1 JSON API under /api/v1 and the user's UI at / (Task 2).

Run from backend/:  uv run uvicorn api.main:app
Environment: VEDIC_EPHE_PATH (default backend/ephe), VEDIC_CITIES_TSV (default
backend/data/cities.tsv), VEDIC_FRONTEND_DIR (default <repo>/frontend).
"""

import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api import places, serialize
from api.schemas import DashaRequest, KundliRequest, PanchangRequest, TransitRequest
from vedic_engine import __version__, ephemeris
from vedic_engine.angles import sign_of
from vedic_engine.constants import Graha
from vedic_engine.dasha._core import DashaPeriod
from vedic_engine.dasha.vimshottari import subtree
from vedic_engine.kundli import build_kundli
from vedic_engine.models import EngineError, EphemerisRangeError, InputError, Settings
from vedic_engine.panchang import day_panchang
from vedic_engine.timeutil import (
    AmbiguousTimeError,
    NonexistentTimeError,
    UnknownTimezoneError,
    birth_utc,
    effective_tz,
)
from vedic_engine.transit import positions_at

log = logging.getLogger("api")

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
API = "/api/v1"
API_VERSION = "1"


def ephe_path() -> Path:
    return Path(os.environ.get("VEDIC_EPHE_PATH", BACKEND / "ephe"))


def frontend_dir() -> Path:
    return Path(os.environ.get("VEDIC_FRONTEND_DIR", REPO / "frontend"))


class ApiInputError(InputError):
    """Invalid input found by the API layer; ``field`` names the request field at fault."""

    def __init__(self, message: str, field: str) -> None:
        super().__init__(message)
        self.field = field


_FIELD_OF: tuple[tuple[type[Exception], str], ...] = (
    (AmbiguousTimeError, "fold"),
    (NonexistentTimeError, "time"),
    (UnknownTimezoneError, "tz"),
    (EphemerisRangeError, "date"),
)


def _field_of(exc: InputError) -> str | None:
    if isinstance(exc, ApiInputError):
        return exc.field
    for kind, field in _FIELD_OF:
        if isinstance(exc, kind):
            return field
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    ephemeris.init(ephe_path())  # raises (the service refuses to start) if unusable
    places.search("a", 1)  # load the place index now, not on the first request
    yield


app = FastAPI(
    title="Vedic Kundli API",
    version=API_VERSION,
    description="Vedic astrology calculation engine (Swiss Ephemeris) with an offline place "
    "search. All indices are 1-based and accompanied by machine keys; every instant is "
    "returned as `*_utc` and `*_local`.",
    lifespan=lifespan,
)


@app.exception_handler(InputError)
async def input_error_handler(_request: Request, exc: InputError) -> JSONResponse:
    field = _field_of(exc)
    loc = ["body", field] if field else ["body"]
    return JSONResponse(
        status_code=422,
        content={"detail": [{"loc": loc, "msg": str(exc), "type": "input_error"}]},
    )


def _internal_error(exc: Exception) -> JSONResponse:
    error_id = uuid.uuid4().hex[:12]
    log.error("internal error %s", error_id, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "internal error", "error_id": error_id},
    )


@app.exception_handler(EngineError)
async def engine_error_handler(_request: Request, exc: EngineError) -> JSONResponse:
    return _internal_error(exc)


@app.exception_handler(Exception)
async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    return _internal_error(exc)


# ---------------------------------------------------------------- health and version


def _health() -> JSONResponse:
    path = ephe_path()
    missing = [f for f in ephemeris.EPHE_FILES if not (path / f).is_file()]
    body = {
        "status": "ok" if not missing else "unavailable",
        "ephemeris": {
            "ok": not missing,
            "path": str(path),
            "files": list(ephemeris.EPHE_FILES),
            "missing": missing,
            "range": {"start": "1800-01-01", "end": "2399-12-31"},
        },
    }
    return JSONResponse(body, status_code=200 if not missing else 503)


def _version() -> dict[str, Any]:
    return {
        "engine_version": __version__,
        "api_version": API_VERSION,
        "ephemeris_files": list(ephemeris.EPHE_FILES),
    }


@app.get(f"{API}/health", summary="Liveness and ephemeris status")
def health() -> JSONResponse:
    return _health()


@app.get(f"{API}/version", summary="Engine and ephemeris versions")
def version() -> dict[str, Any]:
    return _version()


@app.get("/health", include_in_schema=False)
def health_alias() -> JSONResponse:
    return _health()


@app.get("/version", include_in_schema=False)
def version_alias() -> dict[str, Any]:
    return _version()


# ---------------------------------------------------------------- calculations


@app.post(f"{API}/kundli", summary="Full kundli", response_model=dict[str, Any])
def kundli(req: KundliRequest) -> dict[str, Any]:
    birth = req.to_birth()
    result = build_kundli(birth, req.settings.to_engine(), req.vargas_list(), req.dasha_depth)
    tz = effective_tz(birth)
    instant = birth_utc(birth) if birth.time_known else None
    return serialize.kundli(result, tz, instant, birth.lmt, birth.name)


@app.post(f"{API}/panchang", summary="Panchang of a date and place", response_model=dict[str, Any])
def panchang(req: PanchangRequest) -> dict[str, Any]:
    tz = req.engine_tz(req.lon)
    result = day_panchang(req.date, tz, req.lat, req.lon, req.alt, req.settings.to_engine())
    return serialize.day_panchang(result, tz)


@app.post(f"{API}/dasha", summary="Dasha subtree on demand", response_model=dict[str, Any])
def dasha(req: DashaRequest) -> dict[str, Any]:
    birth = req.kundli.to_birth()
    settings = req.kundli.settings.to_engine()
    result = build_kundli(birth, settings, [1], 1)
    scheme = "vimshottari" if req.path[0] in {p.lord for p in result.vimshottari} else "yogini"
    level: tuple[DashaPeriod, ...] = (
        result.vimshottari if scheme == "vimshottari" else result.yogini
    )
    period: DashaPeriod | None = None
    for i, lord in enumerate(req.path):
        if i > 0:
            assert period is not None
            level = subtree(period, settings, 1).children
        period = next((p for p in level if p.lord == lord), None)
        if period is None:
            where = " > ".join(req.path[: i + 1])
            raise ApiInputError(f"no {scheme} period {where} for this birth", "path")
    assert period is not None
    tz = effective_tz(birth)
    return {
        "scheme": scheme,
        "path": req.path,
        "depth": req.depth,
        "period": serialize.dasha_period(subtree(period, settings, req.depth), tz),
    }


@app.post(f"{API}/transit", summary="Graha positions at an instant", response_model=dict[str, Any])
def transit(req: TransitRequest) -> dict[str, Any]:
    if req.settings is not None:
        settings = req.settings.to_engine()
    elif req.natal is not None:
        settings = req.natal.settings.to_engine()
    else:
        settings = Settings()
    at = req.datetime_utc
    positions = positions_at(at, settings)
    natal: tuple[int, int, str] | None = None
    if req.natal is not None:
        chart = build_kundli(req.natal.to_birth(), settings, [1], 1)
        natal = (
            sign_of(chart.lagna_lon),
            sign_of(chart.grahas[Graha.MOON].lon),
            chart.meta["lagna_basis"],
        )
    return serialize.transit(at, positions, natal)


# ---------------------------------------------------------------- places


class PlaceOut(BaseModel):
    name: str
    admin1: str
    country: str
    lat: float
    lon: float
    tz: str
    population: int


@app.get(f"{API}/places", summary="Offline city search", response_model=list[PlaceOut])
def search_places(
    q: Annotated[str, Query(min_length=1, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[dict[str, Any]]:
    return [asdict(p) for p in places.search(q, limit)]


# ---------------------------------------------------------------- placeholders (Task 6 wires these)


def _not_implemented() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented yet"})


def _placeholder(name: str, summary: str) -> None:
    def handler() -> JSONResponse:
        return _not_implemented()

    handler.__name__ = name
    app.post(f"{API}/{name}", summary=summary)(handler)
    app.get(f"{API}/{name}", include_in_schema=False)(handler)


_placeholder("analysis", "Analysis (not implemented yet)")
_placeholder("daily", "Daily guidance (not implemented yet)")


# ---------------------------------------------------------------- the user's UI at /
# Mounted last so that every API route above takes precedence.

_FRONTEND = frontend_dir()
if _FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND, html=True), name="frontend")
else:
    log.warning("frontend directory %s not found; serving the API only", _FRONTEND)
