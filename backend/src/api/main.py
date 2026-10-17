"""FastAPI service: the v1 JSON API under /api/v1 and the user's UI at / (Task 2).

Run from backend/:  uv run uvicorn api.main:app
Environment: VEDIC_EPHE_PATH (default backend/ephe), VEDIC_CITIES_TSV (default
backend/data/cities.tsv), VEDIC_FRONTEND_DIR (default <repo>/frontend).
"""

import logging
import os
import re
import uuid
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager, contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api import analysis_out, places, serialize
from api.schemas import (
    AnalysisRequest,
    DailyRequest,
    DashaRequest,
    KundliRequest,
    PanchangRequest,
    TransitRequest,
)
from vedic_engine import __version__, ephemeris
from vedic_engine.analysis import (
    current_periods,
    daily,
    functional_roles,
    income_sources,
    judge_period,
    life_areas,
    lucky_elements,
    moon_waxing,
    timeline,
)
from vedic_engine.angles import sign_of
from vedic_engine.constants import Graha
from vedic_engine.dasha.vimshottari import subtree
from vedic_engine.kundli import Kundli, build_kundli
from vedic_engine.models import EngineError, EphemerisRangeError, InputError, Settings
from vedic_engine.panchang import day_panchang
from vedic_engine.timeutil import (
    AmbiguousTimeError,
    NonexistentTimeError,
    UnknownTimezoneError,
    birth_utc,
    effective_tz,
    lmt_tz,
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
    """Invalid input found by the API layer; ``loc`` is the path of the request field at fault."""

    def __init__(self, message: str, loc: Sequence[str]) -> None:
        super().__init__(message)
        self.loc = list(loc)


_FIELD_OF: tuple[tuple[type[Exception], str], ...] = (
    (AmbiguousTimeError, "fold"),
    (NonexistentTimeError, "time"),
    (UnknownTimezoneError, "tz"),
    (EphemerisRangeError, "date"),
)


def _field_of(exc: InputError) -> str | None:
    for kind, field in _FIELD_OF:
        if isinstance(exc, kind):
            return field
    return None


@contextmanager
def located(*prefix: str, field: str | None = None) -> Iterator[None]:
    """Re-raise engine ``InputError`` with the request-field path ``prefix`` (+ field)."""
    try:
        yield
    except ApiInputError as exc:
        raise ApiInputError(str(exc), [*prefix, *exc.loc]) from exc
    except InputError as exc:
        name = field or _field_of(exc)
        raise ApiInputError(str(exc), [*prefix, *([name] if name else [])]) from exc


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


ECHO_LIMIT = 60
_QUOTED = re.compile(rf"(['\"])([^'\"]{{{ECHO_LIMIT},}})\1")


def _clip(text: str) -> str:
    return text if len(text) <= ECHO_LIMIT else text[:ECHO_LIMIT] + "\u2026"


def _clip_msg(msg: str) -> str:
    """Shorten any quoted (echoed) input in an error message; cap the whole message."""
    msg = _QUOTED.sub(lambda m: f"{m[1]}{_clip(m[2])}{m[1]}", msg)
    return msg if len(msg) <= 300 else msg[:300] + "\u2026"


def _clip_value(value: Any) -> Any:
    if isinstance(value, str):
        return _clip(value)
    if isinstance(value, dict):
        return {k: _clip_value(v) for k, v in list(value.items())[:20]}
    if isinstance(value, list):
        return [_clip_value(v) for v in value[:20]]
    return value


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = jsonable_encoder(exc.errors())
    for e in errors:
        e["msg"] = _clip_msg(str(e.get("msg", "")))
        if "input" in e:
            e["input"] = _clip_value(e["input"])
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(InputError)
async def input_error_handler(_request: Request, exc: InputError) -> JSONResponse:
    if isinstance(exc, ApiInputError):
        loc = ["body", *exc.loc]
    else:
        field = _field_of(exc)
        loc = ["body", field] if field else ["body"]
    return JSONResponse(
        status_code=422,
        content={"detail": [{"loc": loc, "msg": _clip_msg(str(exc)), "type": "input_error"}]},
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


def test_hooks_enabled() -> bool:
    return os.environ.get("KUNDLI_TEST_HOOKS") == "1"


@app.get(f"{API}/config", summary="Front-end switches")
def config() -> dict[str, Any]:
    """`test_hooks` is true only when the server was started with KUNDLI_TEST_HOOKS=1."""
    return {"test_hooks": test_hooks_enabled()}


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
    """Expand one maha of the `/kundli` response.

    `maha_index` is the 0-based position of the maha in `/kundli`'s `vimshottari` or `yogini`
    list (the same lord can occur twice in the 120-year span, so a lord alone is ambiguous);
    `path` holds the lords below it (antar, pratyantar, ...), and `depth` the levels to
    expand below the addressed period.
    """
    birth = req.kundli.to_birth()
    settings = req.kundli.settings.to_engine()
    with located("kundli"):
        result = build_kundli(birth, settings, [1], 1)
    mahas = result.vimshottari if req.scheme == "vimshottari" else result.yogini
    if req.maha_index >= len(mahas):
        raise ApiInputError(
            f"maha_index {req.maha_index} out of range: this birth has {len(mahas)} "
            f"{req.scheme} mahas (0-{len(mahas) - 1})",
            ["maha_index"],
        )
    period = mahas[req.maha_index]
    for i, lord in enumerate(req.path):
        found = next((p for p in subtree(period, settings, 1).children if p.lord == lord), None)
        if found is None:
            raise ApiInputError(
                f"no {req.scheme} period {lord!r} under {period.lord!r}", ["path", str(i)]
            )
        period = found
    return {
        "scheme": req.scheme,
        "maha_index": req.maha_index,
        "path": req.path,
        "depth": req.depth,
        "period": serialize.dasha_period(subtree(period, settings, req.depth), effective_tz(birth)),
    }


@app.post(f"{API}/transit", summary="Graha positions at an instant", response_model=dict[str, Any])
def transit(req: TransitRequest) -> dict[str, Any]:
    """Graha positions at `datetime_utc`, optionally as houses from a natal chart.

    The one UTC-only endpoint: `datetime_utc` must carry a `Z` or offset, and the response gives
    the instant in UTC only (no `*_local`), because no zone is attached to a transit.
    """
    if req.settings is not None:
        settings = req.settings.to_engine()
    elif req.natal is not None:
        settings = req.natal.settings.to_engine()
    else:
        settings = Settings()
    at = req.datetime_utc
    with located(field="datetime_utc"):
        positions = positions_at(at, settings)
    natal: tuple[int, int, str] | None = None
    if req.natal is not None:
        with located("natal"):
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


# ---------------------------------------------------------------- analysis


def _analysis_chart(req: KundliRequest) -> tuple[Kundli, str]:
    birth = req.to_birth()
    # all vargas: the readings use D9 and D10 whatever the request's `vargas` says
    return build_kundli(birth, req.settings.to_engine(), dasha_depth=req.dasha_depth), (
        effective_tz(birth)
    )


@app.post(
    f"{API}/analysis", summary="Chart analysis and 24-month timeline", response_model=dict[str, Any]
)
def analysis(req: AnalysisRequest) -> dict[str, Any]:
    """The `/kundli` body plus optional `gender` and `now_utc` (default: the current time).

    Returns life `areas`, `income_sources`, `lucky`, `functional_roles` and `periods` (the
    running maha/antar/pratyantar with judgements, the antar and pratyantar `timeline` over
    the next 24 months, monthly ratings, the three best and challenging months, and the
    Saturn/Jupiter transit overlays). Every statement has `why` and `ref`.
    """
    k, tz = _analysis_chart(req)
    now = req.now_utc or datetime.now(UTC)
    with located(field="now_utc"):
        maha, antar, pratyantar = current_periods(k, now)
        tl = timeline(k, now)
    chain = (maha, antar, pratyantar)
    current = [
        (level, chain[i], judge_period(k, tuple(Graha(p.lord) for p in chain[: i + 1])))
        for i, level in enumerate(("maha", "antar", "pratyantar"))
    ]
    return analysis_out.analysis(
        life_areas(k, req.gender),
        income_sources(k),
        lucky_elements(k),
        functional_roles(sign_of(k.lagna_lon), moon_waxing(k)),
        analysis_out.periods(current, tl, tz, full=req.detail == "full"),
        {
            "time_known": k.meta["time_known"],
            "lagna_basis": k.meta["lagna_basis"],
            "tz": tz,
            "gender": req.gender,
        },
    )


@app.post(
    f"{API}/daily",
    summary="Today's guidance: horas, colours, conduct, decisions",
    response_model=dict[str, Any],
)
def daily_guidance(req: DailyRequest) -> dict[str, Any]:
    """The `/kundli` body plus `today` (local date) and optional `current_lat`, `current_lon`,
    `current_tz` (default: the birth place and zone). Horas run from sunrise of `today` to the
    next sunrise at the current place; `*_local` times are in the current zone."""
    k, birth_tz = _analysis_chart(req)
    lat = req.current_lat if req.current_lat is not None else req.lat
    lon = req.current_lon if req.current_lon is not None else req.lon
    if req.current_tz is not None:
        tz = req.current_tz
    elif req.lmt:
        tz = lmt_tz(lon)
    else:
        tz = birth_tz
    try:
        g = daily(k, req.today, tz, lat, lon)
    except UnknownTimezoneError as exc:
        raise ApiInputError(str(exc), ["current_tz"]) from exc
    except InputError as exc:  # no sunrise (polar), date out of range, beyond the dasha span
        raise ApiInputError(str(exc), ["today"]) from exc
    return analysis_out.daily(g, lat, lon)


@app.api_route(
    "/api/{rest:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
def api_not_found(rest: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": f"no such API path: /api/{rest}"})


# ---------------------------------------------------------------- the user's UI at /
# Mounted last so that every API route above takes precedence.

_FRONTEND = frontend_dir()
if _FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND, html=True), name="frontend")
else:
    log.warning("frontend directory %s not found; serving the API only", _FRONTEND)
