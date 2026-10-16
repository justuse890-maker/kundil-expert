"""Kundli orchestrator: composes the calculation modules; no formulas of its own (spec 3, 4).

``build_kundli`` is deterministic: the same ``BirthInput`` and ``Settings`` give the same result.
``warnings`` gathers every sub-module's warnings plus the orchestrator's own (spec 8), sorted
by code then message:

* ``birth_time_sensitive`` - sensitivity (spec 5.11);
* ``polar_latitude`` - |latitude| > 66.5 deg, where houses are unreliable;
* ``school_dependent`` - Rahu or Ketu exalted or debilitated, which depends on the
  NODE_DIGNITY_SCHOOL table (spec 5.5);
* ``range_clamped`` (Sade Sati), ``polar_sunrise`` / ``range_sunrise`` (Shadbala, Ruling R26).
"""

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from vedic_engine import __version__, ephemeris
from vedic_engine.angles import nak_of, sign_of
from vedic_engine.ashtakavarga import bav, sav
from vedic_engine.avastha import baladi
from vedic_engine.constants import SEVEN, Graha
from vedic_engine.dasha import DashaPeriod
from vedic_engine.dasha.vimshottari import balance, vimshottari
from vedic_engine.dasha.yogini import yogini
from vedic_engine.dignity import Dignity, dignity, is_combust
from vedic_engine.doshas import KaalSarpaResult, ManglikResult, SaturnPhase, kaal_sarpa
from vedic_engine.doshas import manglik as manglik_of
from vedic_engine.doshas import sade_sati as sade_sati_of
from vedic_engine.lagna import bhava_rashis
from vedic_engine.models import BirthInput, EngineWarning, GrahaPosition, Settings
from vedic_engine.names import syllable
from vedic_engine.panchang import PanchangAt, elements_at
from vedic_engine.sensitivity import SensitivityItem
from vedic_engine.sensitivity import sensitivity as sensitivity_of
from vedic_engine.shadbala import ShadbalaRow, shadbala_report
from vedic_engine.timeutil import jd_from_utc, to_utc
from vedic_engine.varga import VARGAS, varga_chart

POLAR_LATITUDE = 66.5
YOGINI_DEPTH = 3  # spec 5.6: Yogini has 3 levels


@dataclass(frozen=True, slots=True)
class Kundli:
    meta: dict[str, Any]
    grahas: dict[Graha, GrahaPosition]
    lagna_lon: float
    bhavas: tuple[int, ...]
    panchang: PanchangAt
    vargas: dict[int, dict[str, int]]
    dignity: dict[Graha, Dignity]
    combust: dict[Graha, bool]
    avastha: dict[Graha, str]
    vimshottari: tuple[DashaPeriod, ...]
    yogini: tuple[DashaPeriod, ...]
    manglik: ManglikResult
    kaal_sarpa: KaalSarpaResult | None
    sade_sati: tuple[SaturnPhase, ...]
    shadbala: dict[Graha, ShadbalaRow]
    ashtakavarga: dict[str, Any]
    sensitivity: tuple[SensitivityItem, ...]
    name_syllable: tuple[str, str]
    warnings: tuple[EngineWarning, ...]


@dataclass(frozen=True, slots=True)
class PartialKundli:
    """What fixed placements without a date allow (e.g. the Shri Ram fixture)."""

    dignity: dict[Graha, Dignity]
    vargas: dict[int, dict[str, int]]
    maha_lord: Graha
    balance_years: float
    nakshatra: int
    pada: int
    syllable: tuple[str, str]


def _vargas(
    lons: Mapping[Graha, float], lagna_lon: float, ns: Sequence[int]
) -> dict[int, dict[str, int]]:
    points = {**{g.value: lon for g, lon in lons.items()}, "lagna": lagna_lon}
    return {n: varga_chart(points, n) for n in ns}


def _dignities(lons: Mapping[Graha, float]) -> dict[Graha, Dignity]:
    return {g: dignity(g, lon, lons) for g, lon in lons.items()}


def _node_warning(dig: Mapping[Graha, Dignity]) -> tuple[EngineWarning, ...]:
    flagged = [
        f"{g.value} {dig[g].value}"
        for g in (Graha.RAHU, Graha.KETU)
        if dig.get(g) in (Dignity.EXALTED, Dignity.DEBILITATED)
    ]
    if not flagged:
        return ()
    return (
        EngineWarning(
            "school_dependent",
            f"{', '.join(flagged)}: node dignity depends on the school (NODE_DIGNITY_SCHOOL)",
        ),
    )


def build_kundli(
    birth: BirthInput,
    settings: Settings = Settings(),  # noqa: B008 - frozen dataclass, safe as a default
    vargas: Sequence[int] = VARGAS,
    dasha_depth: int = 3,
) -> Kundli:
    birth_utc = to_utc(birth.local, birth.tz, birth.fold)
    jd = jd_from_utc(birth_utc)
    grahas = ephemeris.positions(jd, settings)
    lons = {g: p.lon for g, p in grahas.items()}
    lagna_lon = ephemeris.ascendant(jd, birth.lat, birth.lon)
    moon = lons[Graha.MOON]

    dig = _dignities(lons)
    phases, sade_sati_warnings = sade_sati_of(moon, jd, settings)
    shadbala_rows, shadbala_warnings = shadbala_report(jd, birth.lat, birth.lon, settings)
    sens, sens_warnings = sensitivity_of(birth, settings)
    signs = {**{g.value: sign_of(lons[g]) for g in SEVEN}, "lagna": sign_of(lagna_lon)}
    bav_table = bav(signs)

    warnings: list[EngineWarning] = [
        *sade_sati_warnings,
        *shadbala_warnings,
        *sens_warnings,
        *_node_warning(dig),
    ]
    if abs(birth.lat) > POLAR_LATITUDE:
        warnings.append(
            EngineWarning(
                "polar_latitude",
                f"latitude {birth.lat} is beyond +/-{POLAR_LATITUDE} deg: houses are unreliable",
            )
        )

    return Kundli(
        meta={
            "engine_version": __version__,
            "settings": asdict(settings),
            "ayanamsa_deg": ephemeris.ayanamsa(jd, settings),
            "jd_ut": jd,
            "ephemeris_files": list(ephemeris.EPHE_FILES),
        },
        grahas=grahas,
        lagna_lon=lagna_lon,
        bhavas=bhava_rashis(lagna_lon),
        panchang=elements_at(jd, birth.lat, birth.lon, birth.alt, settings),
        vargas=_vargas(lons, lagna_lon, vargas),
        dignity=dig,
        combust={g: is_combust(g, p.lon, lons[Graha.SUN], p.retro) for g, p in grahas.items()},
        avastha={g: baladi(lon) for g, lon in lons.items()},
        vimshottari=vimshottari(moon, birth_utc, settings, dasha_depth),
        yogini=yogini(moon, birth_utc, settings, min(dasha_depth, YOGINI_DEPTH)),
        manglik=manglik_of(lons[Graha.MARS], lagna_lon, moon, lons[Graha.VENUS]),
        kaal_sarpa=kaal_sarpa(lons, lagna_lon),
        sade_sati=phases,
        shadbala=shadbala_rows,
        ashtakavarga={"bav": {g.value: v for g, v in bav_table.items()}, "sav": sav(bav_table)},
        sensitivity=sens,
        name_syllable=syllable(*nak_of(moon)),
        warnings=tuple(sorted(set(warnings), key=lambda w: (w.code, w.message))),
    )


def chart_from_placements(lagna_lon: float, lons: Mapping[Graha, float]) -> PartialKundli:
    """Dignity, vargas, birth dasha and syllable from fixed placements (no date needed).

    ``lons`` must include the Moon and every graha whose sign lord is consulted for dignity.
    """
    moon = lons[Graha.MOON]
    lord, years = balance(moon)
    nak, pada = nak_of(moon)
    return PartialKundli(
        dignity=_dignities(lons),
        vargas=_vargas(lons, lagna_lon, VARGAS),
        maha_lord=lord,
        balance_years=years,
        nakshatra=nak,
        pada=pada,
        syllable=syllable(nak, pada),
    )
