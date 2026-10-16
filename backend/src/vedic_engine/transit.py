"""Transits: sign ingresses of a graha and graha positions at an instant (spec section 5.8)."""

from datetime import datetime

from vedic_engine import ephemeris
from vedic_engine.angles import sign_of
from vedic_engine.constants import Graha
from vedic_engine.models import GrahaPosition, Settings
from vedic_engine.timeutil import jd_from_utc

BISECT_TOLERANCE_DAYS = 1.0 / 1440.0  # 1 minute

# Scan step in days. It must be smaller than the graha's minimum time in a sign, or a whole
# sign could be skipped between two samples: the Moon crosses a sign in >= ~1.0 day (fastest
# ~15 deg/day), so it gets 0.25 day; Saturn needs ~2.5 years per sign (a 1-day step moves it
# ~0.1 deg) and every other graha is also slower than 1 deg/day, so they use 1 day.
_STEP_DAYS: dict[Graha, float] = {Graha.MOON: 0.25}
_DEFAULT_STEP_DAYS = 1.0
# Near a sign boundary a station can make a graha cross, turn and re-cross within one step, so
# a step that starts or ends within this many degrees of a boundary is re-sampled finely.
_NEAR_BOUNDARY_DEG = 0.5
_FINE_SUBSTEPS = 48


def _lon(jd: float, graha: Graha, settings: Settings) -> float:
    return ephemeris.body_longitude(jd, graha, settings)


def _near_boundary(lon: float) -> bool:
    d = lon % 30.0
    return d < _NEAR_BOUNDARY_DEG or d > 30.0 - _NEAR_BOUNDARY_DEG


def _bisect(lo: float, hi: float, sign_lo: int, graha: Graha, settings: Settings) -> float:
    """First instant (to 1 minute) in (lo, hi] whose sign differs from ``sign_lo``."""
    while hi - lo > BISECT_TOLERANCE_DAYS:
        mid = (lo + hi) / 2.0
        if sign_of(_lon(mid, graha, settings)) == sign_lo:
            lo = mid
        else:
            hi = mid
    return hi


def sign_ingresses(
    graha: Graha, jd_start: float, jd_end: float, settings: Settings
) -> list[tuple[float, int]]:
    """(JD, new sign 0-11) of every sidereal sign change in (jd_start, jd_end], retrograde
    re-entries included, in time order."""
    step = _STEP_DAYS.get(graha, _DEFAULT_STEP_DAYS)
    out: list[tuple[float, int]] = []
    t = jd_start
    lon = _lon(t, graha, settings)
    sign = sign_of(lon)
    while t < jd_end:
        t_next = min(t + step, jd_end)
        lon_next = _lon(t_next, graha, settings)
        if _near_boundary(lon) or _near_boundary(lon_next):
            n = _FINE_SUBSTEPS
            marks = [t + (t_next - t) * i / n for i in range(1, n + 1)]
        else:
            marks = [t_next]
        prev = t
        for i, m in enumerate(marks):
            m_sign = sign_of(lon_next if i == len(marks) - 1 else _lon(m, graha, settings))
            if m_sign != sign:
                cross = _bisect(prev, m, sign, graha, settings)
                out.append((cross, m_sign))
                sign = m_sign
            prev = m
        t, lon = t_next, lon_next
    return out


def positions_at(dt_utc: datetime, settings: Settings) -> dict[Graha, GrahaPosition]:
    """Sidereal positions of all nine grahas at a UTC instant."""
    return ephemeris.positions(jd_from_utc(dt_utc), settings)
