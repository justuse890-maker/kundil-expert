"""The single adapter over Swiss Ephemeris (pyswisseph). No other engine module may import it.

pyswisseph keeps process-global state (ephemeris path, sidereal mode, open file handles), so
every ``swe`` call goes through ``_LOCK`` and the sidereal mode is re-asserted inside the lock
before each sidereal computation.

Only the shipped ``.se1`` files are used. Dates outside them raise ``EphemerisRangeError``, and
a result computed by any other ephemeris (Swiss Ephemeris silently falls back to Moshier when
a file is unusable) raises ``EngineError``.
"""

import threading
from pathlib import Path
from typing import Literal

import swisseph as swe

from vedic_engine.angles import norm
from vedic_engine.constants import Graha
from vedic_engine.models import (
    EngineError,
    EphemerisRangeError,
    GrahaPosition,
    InputError,
    Settings,
)

EPHE_FILES: tuple[str, ...] = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")

_LOCK = threading.Lock()

# Supported range: 1800-01-01 00:00 UT .. 2399-12-31 24:00 UT (Gregorian).
JD_MIN: float = float(swe.julday(1800, 1, 1, 0.0, swe.GREG_CAL))
JD_MAX: float = float(swe.julday(2399, 12, 31, 24.0, swe.GREG_CAL))

# Window after JD_MIN in which a Moshier fallback is a range problem, not an engine fault.
_EDGE_DAYS = 0.25

_SIDEREAL = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
_TROPICAL = swe.FLG_SWIEPH | swe.FLG_SPEED

_BODY: dict[Graha, int] = {
    Graha.SUN: swe.SUN,
    Graha.MOON: swe.MOON,
    Graha.MARS: swe.MARS,
    Graha.MERCURY: swe.MERCURY,
    Graha.JUPITER: swe.JUPITER,
    Graha.VENUS: swe.VENUS,
    Graha.SATURN: swe.SATURN,
}
_NODE: dict[str, int] = {"MEAN": swe.MEAN_NODE, "TRUE": swe.TRUE_NODE}
_SUPPORTED_AYANAMSA = "LAHIRI"


def init(ephe_path: Path) -> None:
    """Point Swiss Ephemeris at the shipped files and fail fast if any is missing or unusable."""
    missing = [name for name in EPHE_FILES if not (ephe_path / name).is_file()]
    if missing:
        raise EngineError(f"ephemeris files missing in {ephe_path}: {', '.join(missing)}")
    with _LOCK:
        swe.set_ephe_path(str(ephe_path))
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        # Probe both planetary and lunar files: an unreadable file degrades to Moshier silently.
        probe = float(swe.julday(2000, 1, 1, 12.0, swe.GREG_CAL))
        for body in (swe.SUN, swe.MOON):
            _calc(probe, body, _TROPICAL)


def check_range(jd: float) -> None:
    if not JD_MIN <= jd <= JD_MAX:
        raise EphemerisRangeError(
            f"Julian day {jd} outside supported range 1800-01-01 .. 2399-12-31 (CE, Gregorian)"
        )


def _calc(jd_ut: float, body: int, flags: int) -> tuple[float, ...]:
    """``swe.calc_ut`` with a Swiss-Ephemeris-files check. Caller must hold ``_LOCK``."""
    try:
        xx, ret = swe.calc_ut(jd_ut, body, flags)
    except swe.Error as exc:
        raise EngineError(f"Swiss Ephemeris error for body {body} at JD {jd_ut}: {exc}") from exc
    if not ret & swe.FLG_SWIEPH:
        if jd_ut < JD_MIN + _EDGE_DAYS:
            # sepl_18.se1 starts exactly at 1800-01-01 0h; light-time (up to ~1.5 h for Saturn)
            # reaches back before it during the first hours of the range.
            raise EphemerisRangeError(
                f"Julian day {jd_ut} too close to the start of the ephemeris files (1800-01-01)"
            )
        raise EngineError(
            f"Swiss Ephemeris files not used for body {body} at JD {jd_ut} (flags {ret}); "
            "refusing Moshier fallback"
        )
    return tuple(xx)


def _check_settings(settings: Settings) -> None:
    if settings.ayanamsa != _SUPPORTED_AYANAMSA:
        raise InputError(f"unsupported ayanamsa {settings.ayanamsa!r}; only LAHIRI")


def ayanamsa(jd_ut: float, settings: Settings) -> float:
    """True Lahiri ayanamsa (mean + nutation), the value FLG_SIDEREAL subtracts."""
    check_range(jd_ut)
    _check_settings(settings)
    with _LOCK:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        try:
            ret, aya = swe.get_ayanamsa_ex_ut(jd_ut, swe.FLG_SWIEPH)
        except swe.Error as exc:
            raise EngineError(f"Swiss Ephemeris ayanamsa error at JD {jd_ut}: {exc}") from exc
    if not ret & swe.FLG_SWIEPH:
        raise EngineError(f"ayanamsa not computed with Swiss Ephemeris files (flags {ret})")
    return float(aya)


def _ketu(rahu: GrahaPosition) -> GrahaPosition:
    return GrahaPosition(Graha.KETU, norm(rahu.lon + 180.0), -rahu.lat, rahu.speed, True)


def _sidereal(jd_ut: float, graha: Graha, settings: Settings) -> GrahaPosition:
    """Caller must hold ``_LOCK`` and have asserted the sidereal mode."""
    if graha is Graha.KETU:
        return _ketu(_sidereal(jd_ut, Graha.RAHU, settings))
    body = _NODE[settings.node] if graha is Graha.RAHU else _BODY[graha]
    xx = _calc(jd_ut, body, _SIDEREAL)
    speed = float(xx[3])
    retro = True if graha is Graha.RAHU else speed < 0.0
    return GrahaPosition(graha, norm(float(xx[0])), float(xx[1]), speed, retro)


def positions(jd_ut: float, settings: Settings) -> dict[Graha, GrahaPosition]:
    """Sidereal (Lahiri) positions of all nine grahas. Rahu/Ketu are always retrograde."""
    check_range(jd_ut)
    _check_settings(settings)
    out: dict[Graha, GrahaPosition] = {}
    with _LOCK:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        for graha in Graha:
            if graha is not Graha.KETU:
                out[graha] = _sidereal(jd_ut, graha, settings)
    out[Graha.KETU] = _ketu(out[Graha.RAHU])
    return out


def body_longitude(jd_ut: float, graha: Graha, settings: Settings) -> float:
    """Sidereal longitude of one graha (fast path for root finders)."""
    check_range(jd_ut)
    _check_settings(settings)
    with _LOCK:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        return _sidereal(jd_ut, graha, settings).lon


def tropical_longitude(jd_ut: float, graha: Graha) -> float:
    """Apparent geocentric tropical longitude of date (mean node for Rahu/Ketu).

    Used only to verify the ephemeris against JPL Horizons.
    """
    check_range(jd_ut)
    body = swe.MEAN_NODE if graha in (Graha.RAHU, Graha.KETU) else _BODY[graha]
    with _LOCK:
        lon = float(_calc(jd_ut, body, _TROPICAL)[0])
    return norm(lon + 180.0) if graha is Graha.KETU else norm(lon)


def ascendant(jd_ut: float, lat: float, lon: float) -> float:
    """Sidereal (Lahiri) ascendant longitude for geographic ``lat``/``lon`` (east positive)."""
    check_range(jd_ut)
    with _LOCK:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        try:
            _cusps, ascmc = swe.houses_ex(jd_ut, lat, lon, b"W", swe.FLG_SIDEREAL)
        except swe.Error as exc:
            raise EngineError(f"Swiss Ephemeris houses error at JD {jd_ut}: {exc}") from exc
    return norm(float(ascmc[0]))


_RISE_SET_BODY: dict[str, int] = {"sun": swe.SUN, "moon": swe.MOON}
_RISE_SET_EVENT: dict[str, int] = {"rise": swe.CALC_RISE, "set": swe.CALC_SET}
_CIRCUMPOLAR = -2


def rise_set(
    jd_start: float,
    lat: float,
    lon: float,
    alt: float,
    body: Literal["sun", "moon"],
    event: Literal["rise", "set"],
    settings: Settings,
) -> float | None:
    """UT Julian day of the first rise/set in [jd_start, jd_start + 1), else ``None``.

    ``None`` means the body does not rise/set in that day: circumpolar or never above the
    horizon (polar day/night), or - for the Moon - the next event falls on the following day.
    """
    check_range(jd_start)
    check_range(jd_start + 1.0)
    rsmi = _RISE_SET_EVENT[event]
    if settings.sunrise == "CENTER_NO_REFRACTION":
        rsmi |= swe.BIT_DISC_CENTER | swe.BIT_NO_REFRACTION
    with _LOCK:
        try:
            res, tret = swe.rise_trans(
                jd_start, _RISE_SET_BODY[body], rsmi, (lon, lat, alt), 0.0, 0.0, swe.FLG_SWIEPH
            )
        except swe.Error as exc:
            raise EngineError(f"Swiss Ephemeris rise_trans error at JD {jd_start}: {exc}") from exc
    if res == _CIRCUMPOLAR:
        return None
    if res != 0:
        raise EngineError(f"Swiss Ephemeris rise_trans returned {res} at JD {jd_start}")
    t = float(tret[0])
    return t if jd_start <= t < jd_start + 1.0 else None
