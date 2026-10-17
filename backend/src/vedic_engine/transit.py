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

# Largest |apparent geocentric longitudinal speed| in deg/day, rounded up from the maxima Swiss
# Ephemeris reports over the supported range 1800-2399 (checked by test_speed_table_bounds_real_
# speeds) and consistent with the published extremes: Moon ~15.4 (perigee), Mercury ~2.2, Venus
# ~1.26, Sun ~1.02 (perihelion), Mars ~0.79, Jupiter ~0.24, Saturn ~0.134, mean node 0.053
# (true node up to ~0.26 is the bound used for Rahu/Ketu so both node modes are covered).
# These bounds hold for real ephemeris longitudes only; they are NOT valid for synthetic
# longitude functions (a test faking a faster mover must stay inside the near-boundary band).
MAX_SPEED_DEG_PER_DAY: dict[Graha, float] = {
    Graha.SUN: 1.03,
    Graha.MOON: 15.5,
    Graha.MARS: 0.80,
    Graha.MERCURY: 2.21,
    Graha.JUPITER: 0.25,
    Graha.VENUS: 1.27,
    Graha.SATURN: 0.135,
    Graha.RAHU: 0.30,
    Graha.KETU: 0.30,
}
# A leap of (distance to the sign boundary - the near-boundary band) / (max speed * this factor)
# days cannot reach the boundary, so no ingress (and no station hover) can be missed in it.
_SPEED_SAFETY = 1.5


def _lon(jd: float, graha: Graha, settings: Settings) -> float:
    return ephemeris.body_longitude(jd, graha, settings)


def _near_boundary(lon: float, near: float = _NEAR_BOUNDARY_DEG) -> bool:
    d = lon % 30.0
    return d < near or d > 30.0 - near


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
    v_max = MAX_SPEED_DEG_PER_DAY[graha] * _SPEED_SAFETY
    # A step that starts and ends farther than this from a boundary cannot have touched it, so
    # slow grahas (Saturn: 0.2 deg) need the fine re-check in a narrower band than 0.5 deg.
    near = min(_NEAR_BOUNDARY_DEG, v_max * step)
    out: list[tuple[float, int]] = []
    t = jd_start
    lon = _lon(t, graha, settings)
    sign = sign_of(lon)
    while t < jd_end:
        # Far from a boundary the graha cannot reach it within `leap` days, so that many whole
        # steps are skipped unsampled. They are added one by one, so the grid points (and with
        # them every bisection bracket and result) are bit-identical to the plain fixed-step
        # scan. Near a boundary this is the original single step.
        d = lon % 30.0
        n_steps = max(1, int((min(d, 30.0 - d) - near) / v_max / step))
        t_next = t
        for _ in range(n_steps):
            t_next = min(t_next + step, jd_end)
        lon_next = _lon(t_next, graha, settings)
        if _near_boundary(lon, near) or _near_boundary(lon_next, near):
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
