"""Kundli orchestrator: composes the calculation modules; no formulas of its own (spec 3, 4).

``build_kundli`` is deterministic: the same ``BirthInput`` and ``Settings`` give the same result.
``warnings`` gathers every sub-module's warnings plus the orchestrator's own (spec 8), sorted
by code then message:

* ``birth_time_sensitive`` - sensitivity (spec 5.11, thresholds per Ruling R28);
* ``polar_latitude`` - |latitude| > 66.5 deg, where houses are unreliable;
* ``school_dependent`` - Rahu or Ketu exalted or debilitated, which depends on the
  NODE_DIGNITY_SCHOOL table (spec 5.5);
* ``range_clamped`` (Sade Sati), ``polar_sunrise`` / ``range_sunrise`` (Shadbala, Ruling R26).

``bhavas_detail`` (bhava table with lord, occupants, aspects, karakas) and ``vargottama`` are
the House screen's facts (``vedic_engine.bhava``); they carry no warnings of their own.
"""

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from vedic_engine import __version__, ephemeris
from vedic_engine.angles import nak_of, sign_of
from vedic_engine.ashtakavarga import bav, sav
from vedic_engine.avastha import baladi
from vedic_engine.bhava import BhavaFact, bhava_facts
from vedic_engine.bhava import vargottama as vargottama_of
from vedic_engine.constants import NAKSHATRAS, SEVEN, Graha
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
from vedic_engine.panchang import PanchangAt, day_start, elements_at
from vedic_engine.sensitivity import SensitivityItem
from vedic_engine.sensitivity import sensitivity as sensitivity_of
from vedic_engine.shadbala import ShadbalaRow, shadbala_report
from vedic_engine.timeutil import effective_tz, jd_from_utc, to_utc
from vedic_engine.varga import VARGAS, varga_chart

POLAR_LATITUDE = 66.5
YOGINI_DEPTH = 3  # spec 5.6: Yogini has 3 levels
NOON_HOUR = 12
MOON_SAMPLE_MINUTES = 30  # a pada lasts >= ~5 h, so half-hour sampling cannot skip one


@dataclass(frozen=True, slots=True)
class Kundli:
    meta: dict[str, Any]
    grahas: dict[Graha, GrahaPosition]
    lagna_lon: float
    bhavas: tuple[int, ...]
    bhavas_detail: tuple[BhavaFact, ...]
    panchang: PanchangAt
    vargas: dict[int, dict[str, int]]
    vargottama: dict[Graha, bool]
    dignity: dict[Graha, Dignity]
    combust: dict[Graha, bool]
    avastha: dict[Graha, str]
    vimshottari: tuple[DashaPeriod, ...]
    yogini: tuple[DashaPeriod, ...]
    manglik: ManglikResult
    kaal_sarpa: KaalSarpaResult | None
    sade_sati: tuple[SaturnPhase, ...]
    shadbala: dict[Graha, ShadbalaRow] | None  # None when the birth time is unknown
    ashtakavarga: dict[str, Any]
    sensitivity: tuple[SensitivityItem, ...]
    name_syllable: tuple[str, str]
    warnings: tuple[EngineWarning, ...]


@dataclass(frozen=True, slots=True)
class PartialKundli:
    """What fixed placements without a date allow (e.g. the Shri Ram fixture)."""

    dignity: dict[Graha, Dignity]
    vargas: dict[int, dict[str, int]]
    bhavas_detail: tuple[BhavaFact, ...]
    vargottama: dict[Graha, bool]
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


def _moon_padas(birth: BirthInput, tz: str, settings: Settings) -> list[tuple[int, int]]:
    """Distinct (nakshatra, pada) the Moon occupies between local 00:00 and 23:59, in order."""
    day = birth.local.date()
    start = max(jd_from_utc(day_start(day, tz)), ephemeris.JD_MIN)
    end = min(jd_from_utc(day_start(day + timedelta(days=1), tz)) - 1.0 / 1440.0, ephemeris.JD_MAX)
    step = MOON_SAMPLE_MINUTES / 1440.0
    seen: list[tuple[int, int]] = []
    t = start
    while True:
        t = min(t, end)
        cell = nak_of(ephemeris.body_longitude(t, Graha.MOON, settings))
        if cell not in seen:
            seen.append(cell)
        if t >= end:
            return seen
        t += step


def _time_unknown_warnings(birth: BirthInput, tz: str, settings: Settings) -> list[EngineWarning]:
    out = [
        EngineWarning(
            "time_unknown",
            "birth time unknown: Chandra kundli from positions at local noon, with the Moon's "
            "sign as lagna; ascendant, shadbala and birth-time sensitivity are omitted and the "
            "Vimshottari dasha (from the noon Moon) is approximate",
        )
    ]
    padas = _moon_padas(birth, tz, settings)
    if len(padas) > 1:
        listed = ", ".join(f"{NAKSHATRAS[n]} pada {p}" for n, p in padas)
        out.append(
            EngineWarning(
                "moon_nakshatra_uncertain",
                f"the Moon occupies {listed} during the day: the noon Moon nakshatra-pada and "
                "the Vimshottari dasha from it (approximate) may differ at the true birth time",
            )
        )
    return out


def build_kundli(
    birth: BirthInput,
    settings: Settings = Settings(),  # noqa: B008 - frozen dataclass, safe as a default
    vargas: Sequence[int] = VARGAS,
    dasha_depth: int = 3,
) -> Kundli:
    tz = effective_tz(birth)
    if birth.time_known:
        birth_utc = to_utc(birth.local, tz, birth.fold)
    else:  # Chandra kundli: positions at local noon of the birth date
        noon = datetime.combine(birth.local.date(), datetime.min.time()).replace(hour=NOON_HOUR)
        birth_utc = to_utc(noon, tz, 0)
    jd = jd_from_utc(birth_utc)
    grahas = ephemeris.positions(jd, settings)
    lons = {g: p.lon for g, p in grahas.items()}
    moon = lons[Graha.MOON]
    lagna_lon = (
        ephemeris.ascendant(jd, birth.lat, birth.lon, settings) if birth.time_known else moon
    )

    dig = _dignities(lons)
    phases, sade_sati_warnings = sade_sati_of(moon, jd, settings)
    shadbala_rows: dict[Graha, ShadbalaRow] | None = None
    shadbala_warnings: tuple[EngineWarning, ...] = ()
    sens: tuple[SensitivityItem, ...] = ()
    sens_warnings: tuple[EngineWarning, ...] = ()
    unknown_warnings: list[EngineWarning] = []
    if birth.time_known:
        shadbala_rows, shadbala_warnings = shadbala_report(jd, birth.lat, birth.lon, settings)
        sens, sens_warnings = sensitivity_of(birth, settings)
    else:
        unknown_warnings = _time_unknown_warnings(birth, tz, settings)
    signs = {**{g.value: sign_of(lons[g]) for g in SEVEN}, "lagna": sign_of(lagna_lon)}
    bav_table = bav(signs)

    warnings: list[EngineWarning] = [
        *sade_sati_warnings,
        *shadbala_warnings,
        *sens_warnings,
        *_node_warning(dig),
        *unknown_warnings,
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
            "time_known": birth.time_known,
            "lagna_basis": "ascendant" if birth.time_known else "moon",
            "ephemeris_files": list(ephemeris.EPHE_FILES),
        },
        grahas=grahas,
        lagna_lon=lagna_lon,
        bhavas=bhava_rashis(lagna_lon),
        bhavas_detail=bhava_facts(lagna_lon, lons),
        panchang=elements_at(jd, birth.lat, birth.lon, birth.alt, settings),
        vargas=_vargas(lons, lagna_lon, vargas),
        vargottama=vargottama_of(lons),
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
    """Dignity, vargas, house facts, birth dasha and syllable from fixed placements (no date).

    ``lons`` must include the Moon and the seven classical grahas (every house lord is looked up
    for the bhava table); Rahu and Ketu are optional.
    """
    moon = lons[Graha.MOON]
    lord, years = balance(moon)
    nak, pada = nak_of(moon)
    return PartialKundli(
        dignity=_dignities(lons),
        vargas=_vargas(lons, lagna_lon, VARGAS),
        bhavas_detail=bhava_facts(lagna_lon, lons),
        vargottama=vargottama_of(lons),
        maha_lord=lord,
        balance_years=years,
        nakshatra=nak,
        pada=pada,
        syllable=syllable(nak, pada),
    )
