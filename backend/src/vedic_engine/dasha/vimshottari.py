"""Vimshottari dasha: 5 levels, 120-year cycle."""

from __future__ import annotations

from datetime import datetime

from vedic_engine.angles import norm
from vedic_engine.constants import VIMSHOTTARI_ORDER, VIMSHOTTARI_YEARS, Graha
from vedic_engine.dasha._core import DashaPeriod, Scheme, build_mahas, check_depth, expand
from vedic_engine.models import Settings

_NAK_SPAN = 360.0 / 27
SCHEME = Scheme(
    order=tuple(g.value for g in VIMSHOTTARI_ORDER),
    years={g.value: y for g, y in VIMSHOTTARI_YEARS.items()},
    total=120,
)


def balance(moon_lon: float) -> tuple[Graha, float]:
    """Lord of the birth maha and the remaining years of it."""
    n = norm(moon_lon)
    nak = min(int(n // _NAK_SPAN), 26)
    lord = VIMSHOTTARI_ORDER[nak % 9]
    traversed = (n - nak * _NAK_SPAN) / _NAK_SPAN
    return lord, (1.0 - traversed) * VIMSHOTTARI_YEARS[lord]


def vimshottari(
    moon_lon: float, birth_utc: datetime, settings: Settings, depth: int = 3
) -> tuple[DashaPeriod, ...]:
    """Maha periods covering birth to at least birth + 120 years, with ``depth`` levels."""
    check_depth(depth)
    lord, remaining = balance(moon_lon)
    return build_mahas(SCHEME, lord.value, remaining, birth_utc, settings.dasha_year_days, depth)


def subtree(period: DashaPeriod, settings: Settings, depth: int) -> DashaPeriod:
    """Expand ``period`` (Vimshottari or Yogini, chosen by its lord) ``depth`` levels below itself (capped at level 5).

    Uses ``period.nominal_start_utc`` so a clipped first maha gives the same
    boundaries as the full tree. ``settings`` is accepted for API symmetry; durations
    derive from the period itself.
    """
    check_depth(depth)
    from vedic_engine.dasha.yogini import SCHEME as YOGINI_SCHEME

    scheme = SCHEME if period.lord in SCHEME.years else YOGINI_SCHEME
    return expand(period, scheme, depth)
