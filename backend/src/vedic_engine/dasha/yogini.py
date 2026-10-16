"""Yogini dasha: 36-year cycle, 8 yoginis."""

from __future__ import annotations

from datetime import datetime

from vedic_engine.angles import norm
from vedic_engine.constants import Graha
from vedic_engine.dasha._core import DashaPeriod, Scheme, build_mahas, check_depth
from vedic_engine.models import Settings

YOGINIS: tuple[str, ...] = (
    "mangala", "pingala", "dhanya", "bhramari", "bhadrika", "ulka", "siddha", "sankata",
)  # fmt: skip

# Metadata only (spec §5.6).
YOGINI_LORD: dict[str, Graha] = {
    "mangala": Graha.MOON,
    "pingala": Graha.SUN,
    "dhanya": Graha.JUPITER,
    "bhramari": Graha.MARS,
    "bhadrika": Graha.MERCURY,
    "ulka": Graha.SATURN,
    "siddha": Graha.VENUS,
    "sankata": Graha.RAHU,
}

SCHEME = Scheme(order=YOGINIS, years={y: i + 1 for i, y in enumerate(YOGINIS)}, total=36)
_NAK_SPAN = 360.0 / 27


def yogini(
    moon_lon: float, birth_utc: datetime, settings: Settings, depth: int = 3
) -> tuple[DashaPeriod, ...]:
    """Yogini maha periods covering birth to at least birth + 120 years."""
    check_depth(depth)
    n = norm(moon_lon)
    nak = min(int(n // _NAK_SPAN), 26)
    idx = ((nak + 1) + 3) % 8 or 8
    lord = YOGINIS[idx - 1]
    remaining = (1.0 - (n - nak * _NAK_SPAN) / _NAK_SPAN) * SCHEME.years[lord]
    return build_mahas(SCHEME, lord, remaining, birth_utc, settings.dasha_year_days, depth)
