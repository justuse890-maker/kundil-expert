"""Lagna and whole-sign bhavas (spec section 5.3): house 1 is the lagna rashi in full."""

from vedic_engine.angles import sign_of


def bhava_rashis(asc_lon: float) -> tuple[int, ...]:
    """Rashi index (0-11) of each of the 12 houses, house 1 first."""
    first = sign_of(asc_lon)
    return tuple((first + i) % 12 for i in range(12))


def house_of(rashi: int, lagna_rashi: int) -> int:
    """Whole-sign house (1-12) occupied by ``rashi`` when the lagna is in ``lagna_rashi``."""
    return (rashi - lagna_rashi) % 12 + 1
