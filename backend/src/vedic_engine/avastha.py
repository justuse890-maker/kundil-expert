"""Baladi avastha (spec 5.7)."""

from typing import Literal

from vedic_engine.angles import deg_in_sign, sign_of

Baladi = Literal["bala", "kumara", "yuva", "vriddha", "mrita"]

_ORDER: tuple[Baladi, ...] = ("bala", "kumara", "yuva", "vriddha", "mrita")


def baladi(lon: float) -> Baladi:
    """Odd signs (0-based even index) run bala..mrita in 6-degree steps; even signs reversed."""
    idx = min(int(deg_in_sign(lon) // 6.0), 4)
    if sign_of(lon) % 2 == 1:
        idx = 4 - idx
    return _ORDER[idx]
