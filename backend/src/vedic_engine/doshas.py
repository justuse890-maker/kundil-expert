"""Doshas (spec section 5.8): Manglik, Kaal Sarpa, Sade Sati / Dhaiya. No cancellations."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from vedic_engine import ephemeris
from vedic_engine.angles import arc, norm, sign_of
from vedic_engine.constants import SEVEN, Graha
from vedic_engine.lagna import house_of
from vedic_engine.models import EngineWarning, Settings
from vedic_engine.timeutil import utc_from_jd
from vedic_engine.transit import sign_ingresses

_MANGLIK_HOUSES = frozenset({1, 2, 4, 7, 8, 12})
_LEVELS: tuple[Literal["none", "low", "medium", "high"], ...] = ("none", "low", "medium", "high")


@dataclass(frozen=True, slots=True)
class ManglikResult:
    from_lagna: bool | None  # None when the lagna is the Moon (it would repeat from_moon)
    from_moon: bool
    from_venus: bool
    level: Literal["none", "low", "medium", "high"]


def manglik(
    mars_lon: float,
    lagna_lon: float,
    moon_lon: float,
    venus_lon: float,
    *,
    lagna_is_moon: bool = False,
) -> ManglikResult:
    """Mars in houses 1/2/4/7/8/12 (whole-sign) from the lagna, Moon and Venus.

    With ``lagna_is_moon`` (Chandra kundli) the lagna reference is dropped (``from_lagna`` is
    None) so the level counts only distinct references.
    """
    mars = sign_of(mars_lon)

    def hit(ref_lon: float) -> bool:
        return house_of(mars, sign_of(ref_lon)) in _MANGLIK_HOUSES

    lagna = None if lagna_is_moon else hit(lagna_lon)
    moon, venus = hit(moon_lon), hit(venus_lon)
    return ManglikResult(lagna, moon, venus, _LEVELS[sum((bool(lagna), moon, venus))])


KAAL_SARPA_NAMES: tuple[str, ...] = (
    "anant", "kulik", "vasuki", "shankhpal", "padma", "mahapadma",
    "takshak", "karkotak", "shankhachud", "ghatak", "vishdhar", "sheshnag",
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class KaalSarpaResult:
    kind: Literal["full", "partial"]
    name: str
    outside: tuple[Graha, ...]


def kaal_sarpa(positions: Mapping[Graha, float], lagna_lon: float) -> KaalSarpaResult | None:
    """Full if all seven planets lie strictly on one side of the Rahu-Ketu axis, partial if
    exactly one does not. A planet exactly on the axis counts as outside."""
    rahu = positions[Graha.RAHU]
    inside = [g for g in SEVEN if 0.0 < arc(rahu, positions[g]) < 180.0]
    beyond = [g for g in SEVEN if 180.0 < arc(rahu, positions[g]) < 360.0]
    majority = inside if len(inside) >= len(beyond) else beyond
    outside = tuple(g for g in SEVEN if g not in majority)
    if len(outside) > 1:
        return None
    name = KAAL_SARPA_NAMES[house_of(sign_of(rahu), sign_of(lagna_lon)) - 1]
    return KaalSarpaResult("full" if not outside else "partial", name, outside)


PhaseKind = Literal[
    "sade_sati_rising", "sade_sati_peak", "sade_sati_setting", "dhaiya_4th", "dhaiya_8th"
]
# Saturn's sign offset from the natal Moon sign -> phase.
_PHASE_BY_OFFSET: dict[int, PhaseKind] = {
    11: "sade_sati_rising",
    0: "sade_sati_peak",
    1: "sade_sati_setting",
    3: "dhaiya_4th",
    7: "dhaiya_8th",
}


@dataclass(frozen=True, slots=True)
class SaturnPhase:
    kind: PhaseKind
    start_utc: datetime
    end_utc: datetime


def sade_sati(
    natal_moon_lon: float, birth_jd: float, settings: Settings, years: int = 100
) -> tuple[tuple[SaturnPhase, ...], tuple[EngineWarning, ...]]:
    """Sade Sati and Dhaiya phases from birth to birth + ``years`` (clamped to JD_MAX).

    A phase active at birth starts at birth; one active at the end ends there. Retrograde
    re-entries give separate records. Phases are sorted by start and never overlap.
    """
    warnings: list[EngineWarning] = []
    end_jd = birth_jd + years * 365.25
    if end_jd > ephemeris.JD_MAX:
        end_jd = ephemeris.JD_MAX
        warnings.append(
            EngineWarning(
                "range_clamped",
                "Saturn phases end at the last supported date (2399-12-31); the "
                f"requested {years}-year window extends beyond the ephemeris range",
            )
        )
    moon_sign = sign_of(norm(natal_moon_lon))
    birth_sign = sign_of(ephemeris.body_longitude(birth_jd, Graha.SATURN, settings))
    segments = [(birth_jd, birth_sign)]
    segments += sign_ingresses(Graha.SATURN, birth_jd, end_jd, settings)
    phases: list[SaturnPhase] = []
    for i, (start, sign) in enumerate(segments):
        end = segments[i + 1][0] if i + 1 < len(segments) else end_jd
        kind = _PHASE_BY_OFFSET.get((sign - moon_sign) % 12)
        if kind is not None and end > start:
            phases.append(SaturnPhase(kind, utc_from_jd(start), utc_from_jd(end)))
    return tuple(phases), tuple(warnings)


__all__ = [
    "KAAL_SARPA_NAMES",
    "KaalSarpaResult",
    "ManglikResult",
    "SaturnPhase",
    "kaal_sarpa",
    "manglik",
    "sade_sati",
]
