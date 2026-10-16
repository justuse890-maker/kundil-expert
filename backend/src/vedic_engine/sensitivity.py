"""Birth-time sensitivity (spec 5.11).

For the lagna, the Moon's nakshatra and pada, the D9 lagna and the D10 lagna: how many minutes
before birth the current value began and how many after birth it ends. Each side is searched
in 1-minute steps up to ``SEARCH_MINUTES``, then the change is bisected to 1 second. A side with
no change inside the window (or inside the supported ephemeris range) reports ``math.inf``.
"""

import math
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from functools import cache

from vedic_engine import ephemeris
from vedic_engine.angles import nak_of, sign_of
from vedic_engine.constants import Graha
from vedic_engine.models import BirthInput, EngineWarning, Settings
from vedic_engine.timeutil import jd_from_utc, to_utc
from vedic_engine.varga import varga_sign

SEARCH_MINUTES = 120
WARN_MINUTES = 5.0
_MINUTE = 1.0 / 1440.0
_SECOND = 1.0 / 86400.0


@dataclass(frozen=True, slots=True)
class SensitivityItem:
    item: str
    minutes_before: float
    minutes_after: float


def _first_change(f: Callable[[float], Hashable], jd: float, direction: int) -> float:
    """Minutes from ``jd`` to the first change of ``f`` in ``direction`` (+1 / -1), or inf."""
    v0 = f(jd)
    inside = jd
    for k in range(1, SEARCH_MINUTES + 1):
        t = jd + direction * k * _MINUTE
        if not ephemeris.JD_MIN <= t <= ephemeris.JD_MAX:
            return math.inf
        if f(t) != v0:
            outside = t
            while abs(outside - inside) > _SECOND:
                mid = (inside + outside) / 2.0
                if f(mid) == v0:
                    inside = mid
                else:
                    outside = mid
            return abs(outside - jd) * 1440.0
        inside = t
    return math.inf


def sensitivity(
    birth: BirthInput, settings: Settings
) -> tuple[tuple[SensitivityItem, ...], tuple[EngineWarning, ...]]:
    jd = jd_from_utc(to_utc(birth.local, birth.tz, birth.fold))

    @cache
    def asc(t: float) -> float:
        return ephemeris.ascendant(t, birth.lat, birth.lon)

    values: dict[str, Callable[[float], Hashable]] = {
        "lagna": lambda t: sign_of(asc(t)),
        "moon_nakshatra_pada": lambda t: nak_of(ephemeris.body_longitude(t, Graha.MOON, settings)),
        "d9_lagna": lambda t: varga_sign(asc(t), 9),
        "d10_lagna": lambda t: varga_sign(asc(t), 10),
    }
    items = tuple(
        SensitivityItem(name, _first_change(f, jd, -1), _first_change(f, jd, 1))
        for name, f in values.items()
    )
    near = [i.item for i in items if min(i.minutes_before, i.minutes_after) <= WARN_MINUTES]
    warnings: tuple[EngineWarning, ...] = ()
    if near:
        warnings = (
            EngineWarning(
                "birth_time_sensitive",
                f"{', '.join(near)} change(s) within {WARN_MINUTES:g} minutes of the birth time",
            ),
        )
    return items, warnings
