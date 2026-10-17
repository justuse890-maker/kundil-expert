"""Birth-time sensitivity (spec 5.11, Ruling R28).

For the lagna, the Moon's nakshatra and pada, the tithi, the D9 lagna and the D10 lagna: how
many minutes before birth the current value began and how many after birth it ends. Each side
is searched in 1-minute steps up to ``SEARCH_MINUTES``, then the change is bisected to 1 second.
A side with no change found reports ``math.inf``; ``edge_before`` / ``edge_after`` is True when
that search was cut short by the supported ephemeris range rather than running the whole window.

The ``birth_time_sensitive`` warning (R28) fires when the lagna, the Moon's nakshatra/pada or
the tithi changes within ``SENSITIVE_MINUTES_PRIMARY`` of birth, or the D9 or D10 lagna within
``SENSITIVE_MINUTES_VARGA``: D9 and D10 lagnas last only ~12-13 minutes, so a 5-minute window
would flag almost every chart. Every item is still reported with its minutes.
"""

import math
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from functools import cache

from vedic_engine import ephemeris
from vedic_engine.angles import nak_of, sign_of
from vedic_engine.constants import Graha
from vedic_engine.models import BirthInput, EngineWarning, Settings
from vedic_engine.panchang import tithi
from vedic_engine.timeutil import birth_utc, jd_from_utc
from vedic_engine.varga import varga_sign

SEARCH_MINUTES = 120
SENSITIVE_MINUTES_PRIMARY = 5
SENSITIVE_MINUTES_VARGA = 1
ITEMS: tuple[str, ...] = ("lagna", "moon_nakshatra_pada", "tithi", "d9_lagna", "d10_lagna")
THRESHOLD_MINUTES: dict[str, int] = {
    "lagna": SENSITIVE_MINUTES_PRIMARY,
    "moon_nakshatra_pada": SENSITIVE_MINUTES_PRIMARY,
    "tithi": SENSITIVE_MINUTES_PRIMARY,
    "d9_lagna": SENSITIVE_MINUTES_VARGA,
    "d10_lagna": SENSITIVE_MINUTES_VARGA,
}
_MINUTE = 1.0 / 1440.0
_SECOND = 1.0 / 86400.0


@dataclass(frozen=True, slots=True)
class SensitivityItem:
    item: str
    minutes_before: float
    minutes_after: float
    edge_before: bool = False  # search reached the supported-range start, no change found
    edge_after: bool = False  # search reached the supported-range end, no change found


def _first_change(f: Callable[[float], Hashable], jd: float, direction: int) -> tuple[float, bool]:
    """(minutes from ``jd`` to the first change of ``f`` in ``direction`` (+1 / -1), edge).

    No change gives ``math.inf``; ``edge`` is True when the supported range ended the search.
    """
    v0 = f(jd)
    inside = jd
    for k in range(1, SEARCH_MINUTES + 1):
        t = jd + direction * k * _MINUTE
        if not ephemeris.JD_MIN <= t <= ephemeris.JD_MAX:
            return math.inf, True
        if f(t) != v0:
            outside = t
            while abs(outside - inside) > _SECOND:
                mid = (inside + outside) / 2.0
                if f(mid) == v0:
                    inside = mid
                else:
                    outside = mid
            return abs(outside - jd) * 1440.0, False
        inside = t
    return math.inf, False


DISPLAY: dict[str, str] = {
    "lagna": "Lagna (ascendant)",
    "moon_nakshatra_pada": "The Moon's nakshatra pada",
    "tithi": "Tithi",
    "d9_lagna": "Navamsa (D9) lagna",
    "d10_lagna": "Dasamsa (D10) lagna",
}


def _span(minutes: float) -> str:
    seconds = round(minutes * 60.0)
    if seconds < 120:
        return f"{seconds} second{'' if seconds == 1 else 's'}"
    return f"{minutes:.1f} minutes"


def _sensitive_message(i: SensitivityItem) -> str:
    """Exactly which item changes, how long after/before the given time (structured items stay)."""
    side, m = ("before", i.minutes_before)
    if i.minutes_after < i.minutes_before:
        side, m = "after", i.minutes_after
    return (
        f"{DISPLAY[i.item]} changes {_span(m)} {side} the given birth time"
        " \u2014 confirm the exact time."
    )


def sensitive_items(items: Iterable[SensitivityItem]) -> tuple[str, ...]:
    """Names of the items that make a birth time sensitive under Ruling R28, in item order."""
    return tuple(
        i.item for i in items if min(i.minutes_before, i.minutes_after) <= THRESHOLD_MINUTES[i.item]
    )


def sensitivity(
    birth: BirthInput, settings: Settings
) -> tuple[tuple[SensitivityItem, ...], tuple[EngineWarning, ...]]:
    jd = jd_from_utc(birth_utc(birth))

    @cache
    def asc(t: float) -> float:
        return ephemeris.ascendant(t, birth.lat, birth.lon, settings)

    @cache
    def moon(t: float) -> float:
        return ephemeris.body_longitude(t, Graha.MOON, settings)

    def sun(t: float) -> float:
        return ephemeris.body_longitude(t, Graha.SUN, settings)

    values: dict[str, Callable[[float], Hashable]] = {
        "lagna": lambda t: sign_of(asc(t)),
        "moon_nakshatra_pada": lambda t: nak_of(moon(t)),
        "tithi": lambda t: tithi(sun(t), moon(t)),
        "d9_lagna": lambda t: varga_sign(asc(t), 9),
        "d10_lagna": lambda t: varga_sign(asc(t), 10),
    }
    items = []
    for name in ITEMS:
        before, edge_before = _first_change(values[name], jd, -1)
        after, edge_after = _first_change(values[name], jd, 1)
        items.append(SensitivityItem(name, before, after, edge_before, edge_after))
    by_name = {i.item: i for i in items}
    warnings = tuple(
        EngineWarning("birth_time_sensitive", _sensitive_message(by_name[name]))
        for name in sensitive_items(items)
    )
    return tuple(items), warnings
