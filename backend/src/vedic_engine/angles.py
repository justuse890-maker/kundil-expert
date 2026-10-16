"""Angle helpers operating on sidereal degrees."""

_NAK_SPAN = 360.0 / 27
_PADA_SPAN = _NAK_SPAN / 4
# Values within this distance below 360 are float-rounding residue of 0 (~3.6 micro-arcsec).
_WRAP_EPS = 1e-9


def norm(deg: float) -> float:
    """Normalise to [0, 360); 360.0 and rounding residue just below it (e.g. -1e-12) fold to 0."""
    r = deg % 360.0
    return 0.0 if r >= 360.0 - _WRAP_EPS else r


def sign_of(lon: float) -> int:
    return min(int(norm(lon) // 30.0), 11)


def deg_in_sign(lon: float) -> float:
    n = norm(lon)
    return n - sign_of(n) * 30.0


def nak_of(lon: float) -> tuple[int, int]:
    """Return (nakshatra 0-26, pada 1-4)."""
    n = norm(lon)
    nak = min(int(n // _NAK_SPAN), 26)
    pada = min(int((n - nak * _NAK_SPAN) // _PADA_SPAN), 3) + 1
    return nak, pada


def arc(a: float, b: float) -> float:
    """Forward distance from a to b in [0, 360)."""
    return norm(b - a)


def dms(deg: float) -> tuple[int, int, float]:
    d = int(deg)
    m_full = (deg - d) * 60.0
    m = int(m_full)
    return d, m, (m_full - m) * 60.0
