"""Shared proportional-subdivision machinery for Vimshottari and Yogini dashas."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

_DAY = timedelta(days=1)
MAX_LEVEL = 5


@dataclass(frozen=True)
class DashaPeriod:
    """One dasha period.

    ``lord`` is the Graha value (Vimshottari) or yogini key (Yogini). ``level`` is
    1 (maha) .. 5 (prana). ``start_utc`` may be clipped to the birth instant for
    periods running at birth; ``nominal_start_utc`` is the unclipped start (defaults
    to ``start_utc``) and ``end_utc`` is always the true end. Sub-period boundaries
    are exact offsets from ``nominal_start_utc``, so expanding a clipped period
    reproduces the same boundaries as the full tree.
    """

    lord: str
    level: int
    start_utc: datetime
    end_utc: datetime
    children: tuple[DashaPeriod, ...] = ()
    nominal_start_utc: datetime | None = None

    def __post_init__(self) -> None:
        if self.nominal_start_utc is None:
            object.__setattr__(self, "nominal_start_utc", self.start_utc)


@dataclass(frozen=True)
class Scheme:
    order: Sequence[str]
    years: Mapping[str, int]
    total: int


def children_of(period: DashaPeriod, scheme: Scheme) -> tuple[DashaPeriod, ...]:
    """Direct children of ``period``, clipped to ``period.start_utc``."""
    nominal = period.nominal_start_utc
    assert nominal is not None
    parent_days = (period.end_utc - nominal) / _DAY
    i0 = list(scheme.order).index(period.lord)
    n = len(scheme.order)
    out: list[DashaPeriod] = []
    cum = 0
    prev = nominal
    for k in range(n):
        lord = scheme.order[(i0 + k) % n]
        cum += scheme.years[lord]
        end = (
            period.end_utc
            if k == n - 1
            else nominal + timedelta(days=parent_days * cum / scheme.total)
        )
        if end > period.start_utc:
            out.append(
                DashaPeriod(
                    lord,
                    period.level + 1,
                    max(prev, period.start_utc),
                    end,
                    nominal_start_utc=prev,
                )
            )
        prev = end
    return tuple(out)


def expand(period: DashaPeriod, scheme: Scheme, depth: int) -> DashaPeriod:
    """Return ``period`` with children expanded ``depth`` levels (capped at level 5)."""
    if depth <= 0 or period.level >= MAX_LEVEL:
        return replace(period, children=())
    kids = tuple(expand(c, scheme, depth - 1) for c in children_of(period, scheme))
    return replace(period, children=kids)


def check_depth(depth: int) -> None:
    if not 1 <= depth <= MAX_LEVEL:
        raise ValueError(f"depth must be between 1 and {MAX_LEVEL}, got {depth}")


def build_mahas(
    scheme: Scheme,
    start_lord: str,
    remaining_years: float,
    birth_utc: datetime,
    year_days: float,
    depth: int,
) -> tuple[DashaPeriod, ...]:
    """Maha periods from birth until the cumulative end is >= birth + 120 years."""
    check_depth(depth)
    horizon = birth_utc + timedelta(days=120 * year_days)
    n = len(scheme.order)
    i0 = list(scheme.order).index(start_lord)
    elapsed = scheme.years[start_lord] - remaining_years
    virtual_start = birth_utc - timedelta(days=elapsed * year_days)
    out: list[DashaPeriod] = []
    cum = 0
    prev = virtual_start
    k = 0
    while True:
        lord = scheme.order[(i0 + k) % n]
        cum += scheme.years[lord]
        end = virtual_start + timedelta(days=cum * year_days)
        if end > birth_utc:
            maha = DashaPeriod(lord, 1, max(prev, birth_utc), end, nominal_start_utc=prev)
            out.append(expand(maha, scheme, depth - 1))
        prev = end
        k += 1
        if end >= horizon:
            break
    return tuple(out)
