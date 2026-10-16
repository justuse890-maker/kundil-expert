"""Parashari divisional charts (BPHS Ch 6), D1-D60.

Sign index 0 is Mesha (an odd sign): odd sign means ``s % 2 == 0``.
Movable signs are ``s % 3 == 0``, fixed ``s % 3 == 1``, dual ``s % 3 == 2``.
A degree exactly on a division edge belongs to the upper part. Parts are computed as
``min(int(d / width + _EDGE_EPS), parts - 1)``. The epsilon is required: a test showed that
for D45 (width 2/3) the float edge ``7 * (30/45)`` divides to 6.999999999999999 and would land
in the lower part (also k = 14, 25, 28, 31). 1e-9 of a part is far below any input precision.
"""

from collections.abc import Callable, Mapping

from vedic_engine.angles import deg_in_sign, norm, sign_of

_EDGE_EPS = 1e-9  # in units of one part; see module docstring

SIMHA, KARKA, DHANU, TULA = 4, 3, 8, 6

# (s, p) -> sign, p being the 0-based part index within the sign.
Rule = Callable[[int, int], int]


def _is_odd(s: int) -> bool:
    return s % 2 == 0


def _by_modality(movable: int, fixed: int, dual: int) -> Rule:
    starts = (movable, fixed, dual)
    return lambda s, p: starts[s % 3] + p


# D30 (Trimsamsa): half-open (lo, hi, sign) degree ranges.
_D30_ODD = ((0.0, 5.0, 0), (5.0, 10.0, 10), (10.0, 18.0, 8), (18.0, 25.0, 2), (25.0, 30.0, 6))
_D30_EVEN = ((0.0, 5.0, 1), (5.0, 12.0, 5), (12.0, 20.0, 11), (20.0, 25.0, 9), (25.0, 30.0, 7))


def _d30(d: float, odd: bool) -> int:
    for lo, hi, sign in _D30_ODD if odd else _D30_EVEN:
        if lo <= d < hi:
            return sign
    return (_D30_ODD if odd else _D30_EVEN)[-1][2]  # d is within [0, 30); guard only


def _hora(s: int, d: float) -> int:
    first_half = d < 15.0
    return SIMHA if first_half == _is_odd(s) else KARKA


# n -> (parts per sign, rule(s, p) -> sign)
_TABLE: dict[int, tuple[int, Rule]] = {
    1: (1, lambda s, p: s),
    3: (3, lambda s, p: s + (0, 4, 8)[p]),
    4: (4, lambda s, p: s + (0, 3, 6, 9)[p]),
    7: (7, lambda s, p: s + p if _is_odd(s) else s + 6 + p),
    9: (9, lambda s, p: 9 * s + p),
    10: (10, lambda s, p: s + p if _is_odd(s) else s + 8 + p),
    12: (12, lambda s, p: s + p),
    16: (16, _by_modality(0, SIMHA, DHANU)),
    20: (20, _by_modality(0, DHANU, SIMHA)),
    24: (24, lambda s, p: (SIMHA if _is_odd(s) else KARKA) + p),
    27: (27, lambda s, p: 27 * s + p),
    40: (40, lambda s, p: (0 if _is_odd(s) else TULA) + p),
    45: (45, _by_modality(0, SIMHA, DHANU)),
    60: (60, lambda s, p: s + p),
}
# D2 and D30 are range based, not equal-division, so they have dedicated branches below.
VARGAS: tuple[int, ...] = (1, 2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60)


def varga_sign(lon: float, n: int) -> int:
    """Sign index 0-11 of ``lon`` in divisional chart D``n``."""
    if n not in VARGAS:
        raise ValueError(f"unsupported varga D{n}")
    lon = norm(lon)
    s, d = sign_of(lon), deg_in_sign(lon)
    if n == 2:
        return _hora(s, d)
    if n == 30:
        return _d30(d, _is_odd(s))
    parts, rule = _TABLE[n]
    p = min(int(d / (30.0 / parts) + _EDGE_EPS), parts - 1)
    return rule(s, p) % 12


def varga_chart(lons: Mapping[str, float], n: int) -> dict[str, int]:
    """Map each key (planet name, "lagna", ...) to its sign in D``n``."""
    return {k: varga_sign(v, n) for k, v in lons.items()}
