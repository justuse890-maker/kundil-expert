"""Panchang: tithi, paksha, nakshatra, yoga, karana, vaar, with end times (spec section 5.1).

Element indices follow the spec formulas: tithi 1-30, nakshatra 0-26, yoga 1-27 and karana
(half-tithi) 0-59. End times are found by root-finding on the underlying angle.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from vedic_engine import ephemeris
from vedic_engine.angles import arc, nak_of, norm
from vedic_engine.constants import (
    KARANAS_FIXED,
    KARANAS_MOVABLE,
    NAKSHATRAS,
    TITHIS,
    VAARS,
    YOGAS,
    Graha,
)
from vedic_engine.models import EngineError, EphemerisRangeError, InputError, Settings
from vedic_engine.timeutil import NonexistentTimeError, jd_from_utc, to_utc, utc_from_jd

TITHI_SPAN = 12.0
KARANA_SPAN = 6.0
NAK_SPAN = 360.0 / 27
YOGA_SPAN = 360.0 / 27

_STEP_DAYS = 0.25  # bracket step; every element moves < 5 deg in it, far below its span
_MAX_SEARCH_DAYS = 3.0  # longest element (a tithi or nakshatra) lasts < 1.2 days
_SECOND = 1.0 / 86400.0


def tithi(sun: float, moon: float) -> int:
    """Tithi 1-30: 1-15 Shukla (15 = Purnima), 16-30 Krishna (30 = Amavasya)."""
    return min(int(arc(sun, moon) // TITHI_SPAN), 29) + 1


def paksha(tithi: int) -> Literal["shukla", "krishna"]:
    return "shukla" if tithi <= 15 else "krishna"


def yoga(sun: float, moon: float) -> int:
    """Yoga 1-27 (Vishkambha ... Vaidhriti) from the sum of the longitudes."""
    return min(int(norm(sun + moon) // YOGA_SPAN), 26) + 1


def karana(sun: float, moon: float) -> int:
    """Half-tithi index k, 0-59."""
    return min(int(arc(sun, moon) // KARANA_SPAN), 59)


def karana_key(k: int) -> str:
    """k = 0 Kimstughna; 1-56 the movable cycle Bava..Vishti; 57-59 Shakuni, Chatushpada, Naga."""
    if not 0 <= k <= 59:
        raise ValueError(f"karana index must be 0-59, got {k}")
    if k == 0:
        return KARANAS_FIXED[0]
    if k >= 57:
        return KARANAS_FIXED[k - 56]
    return KARANAS_MOVABLE[(k - 1) % 7]


@dataclass(frozen=True, slots=True)
class Element:
    key: str
    index: int
    ends_utc: datetime


@dataclass(frozen=True, slots=True)
class PanchangAt:
    tithi: Element
    paksha: str
    nakshatra: Element
    pada: int
    yoga: Element
    karana: Element
    vaar: str


@dataclass(frozen=True, slots=True)
class DayPanchang:
    date: date
    sunrise_utc: datetime
    sunset_utc: datetime
    moonrise_utc: datetime | None
    moonset_utc: datetime | None
    at_sunrise: PanchangAt


def find_end(f: Callable[[float], float], jd: float, span_deg: float) -> float:
    """JD at which the increasing angle ``f`` (degrees, mod 360) next crosses a multiple of
    ``span_deg``: bracketed in 0.25-day steps, then bisected to 1 second.

    The bracket never steps past ``JD_MAX + DERIVED_MARGIN_DAYS``; an end that lies after it
    raises ``EphemerisRangeError``.
    """
    limit = ephemeris.JD_MAX + ephemeris.DERIVED_MARGIN_DAYS
    f0 = f(jd)
    need = span_deg - f0 % span_deg  # in (0, span_deg]

    def reached(t: float) -> bool:
        return norm(f(t) - f0) >= need

    lo = jd
    while True:
        if lo >= limit:
            raise EphemerisRangeError(
                f"end time after Julian day {jd} lies beyond the supported range (2399-12-31)"
            )
        hi = min(lo + _STEP_DAYS, limit)
        if reached(hi):
            break
        lo = hi
        if lo - jd > _MAX_SEARCH_DAYS:
            raise EngineError(f"no {span_deg} deg crossing within {_MAX_SEARCH_DAYS} days of {jd}")
    while hi - lo > _SECOND:
        mid = (lo + hi) / 2.0
        if reached(mid):
            hi = mid
        else:
            lo = mid
    return hi


def _vaar(jd: float, lat: float, lon: float, alt: float, settings: Settings) -> str:
    """Weekday of the most recent local sunrise at or before ``jd``.

    Days are taken in local mean time (UT + longitude), so no timezone is needed: the sunrise
    that decides is the one between the moment's local mean midnight and the next. The search
    never starts before ``JD_MIN``; a sunrise not found there lay before the moment (or the Sun
    does not rise that day, polar day or night), and the vaar is that of the local mean date.
    """
    lmt = jd + lon / 360.0
    midnight = math.floor(lmt + 0.5) - 0.5 - lon / 360.0
    lmt_date = utc_from_jd(lmt).date()
    start = max(midnight, ephemeris.JD_MIN)
    sunrise = ephemeris.rise_set(start, lat, lon, alt, "sun", "rise", settings)
    if sunrise is not None and sunrise < midnight + 1.0 and jd < sunrise - _SECOND:
        lmt_date -= timedelta(days=1)
    return VAARS[lmt_date.weekday()]


def elements_at(jd_ut: float, lat: float, lon: float, alt: float, settings: Settings) -> PanchangAt:
    """Panchang elements prevailing at ``jd_ut``, each with the UTC time it ends.

    ``jd_ut`` must be in the supported range; end times may extend past it by
    ``ephemeris.DERIVED_MARGIN_DAYS``.
    """
    ephemeris.check_range(jd_ut)

    def sun(t: float) -> float:
        return ephemeris.body_longitude(t, Graha.SUN, settings, derived=True)

    def moon(t: float) -> float:
        return ephemeris.body_longitude(t, Graha.MOON, settings, derived=True)

    def elongation(t: float) -> float:
        return arc(sun(t), moon(t))

    def total(t: float) -> float:
        return norm(sun(t) + moon(t))

    su, mo = sun(jd_ut), moon(jd_ut)
    t, k, y = tithi(su, mo), karana(su, mo), yoga(su, mo)
    nak, pada = nak_of(mo)

    def ends(f: Callable[[float], float], span: float) -> datetime:
        return utc_from_jd(find_end(f, jd_ut, span))

    return PanchangAt(
        tithi=Element(TITHIS[t - 1], t, ends(elongation, TITHI_SPAN)),
        paksha=paksha(t),
        nakshatra=Element(NAKSHATRAS[nak], nak, ends(moon, NAK_SPAN)),
        pada=pada,
        yoga=Element(YOGAS[y - 1], y, ends(total, YOGA_SPAN)),
        karana=Element(karana_key(k), k, ends(elongation, KARANA_SPAN)),
        vaar=_vaar(jd_ut, lat, lon, alt, settings),
    )


_MAX_DST_GAP = timedelta(hours=3)


def day_start(day: date, tz: str) -> datetime:
    """UTC instant at which civil ``day`` begins in ``tz``.

    Local midnight, its first occurrence if repeated, or the end of a DST gap that swallows it.
    """
    local = datetime(day.year, day.month, day.day)
    step = timedelta(minutes=15)
    t = local
    while t - local <= _MAX_DST_GAP:
        try:
            return to_utc(t, tz, fold=0)
        except NonexistentTimeError:
            t += step
    raise InputError(f"no local midnight found for {day} in {tz}")


def _event_between(
    jd_a: float,
    jd_b: float,
    lat: float,
    lon: float,
    alt: float,
    body: Literal["sun", "moon"],
    event: Literal["rise", "set"],
    settings: Settings,
) -> float | None:
    """First rise/set in [jd_a, jd_b); the civil day may be 23, 24 or 25 hours long."""
    t = ephemeris.rise_set(jd_a, lat, lon, alt, body, event, settings)
    if t is None and jd_b - jd_a > 1.0:
        t = ephemeris.rise_set(jd_a + 1.0, lat, lon, alt, body, event, settings)
    return t if t is not None and t < jd_b else None


def day_panchang(
    day: date, tz: str, lat: float, lon: float, alt: float, settings: Settings
) -> DayPanchang:
    """Sunrise, sunset, moonrise, moonset of civil ``day`` in ``tz`` and the panchang at sunrise.

    Events are searched from local midnight to the next local midnight.
    """
    jd_a = jd_from_utc(day_start(day, tz))
    jd_b = jd_from_utc(day_start(day + timedelta(days=1), tz))

    def event(body: Literal["sun", "moon"], kind: Literal["rise", "set"]) -> float | None:
        return _event_between(jd_a, jd_b, lat, lon, alt, body, kind, settings)

    sunrise, sunset = event("sun", "rise"), event("sun", "set")
    if sunrise is None or sunset is None:
        raise InputError(f"the Sun does not rise or set on {day} at latitude {lat}")
    moonrise, moonset = event("moon", "rise"), event("moon", "set")
    return DayPanchang(
        date=day,
        sunrise_utc=utc_from_jd(sunrise),
        sunset_utc=utc_from_jd(sunset),
        moonrise_utc=None if moonrise is None else utc_from_jd(moonrise),
        moonset_utc=None if moonset is None else utc_from_jd(moonset),
        at_sunrise=elements_at(sunrise, lat, lon, alt, settings),
    )
