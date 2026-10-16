"""Build the golden birth charts in fixtures/golden/charts/ (dev-time only, needs network).

Run manually from backend/:  uv run python scripts/build_golden_charts.py
The JSON it writes is committed; tests never hit the network.

Every reference value is derived independently of the engine's Swiss Ephemeris planet and
house computations:

* Planets: apparent geocentric tropical longitude of date from NASA JPL Horizons (DE441,
  quantity 31, fetched with the same query as scripts/build_golden_horizons.py), shifted from
  the IAU 1976 to the IAU 2006 equinox of date (the difference of the two published general-
  precession polynomials, as in tests/golden/test_horizons.py), minus the engine's Lahiri
  ayanamsa, which tests/golden/test_horizons.py verifies against the Indian Astronomical
  Ephemeris to 1 arcsec.
* Lagna: tropical ascendant from sidereal time computed here (Meeus, Astronomical Algorithms,
  2nd ed.: GMST eq. 12.4, mean obliquity eq. 22.2, nutation by the ch. 22 short series, apparent
  sidereal time ch. 12, ascendant ch. 14 / 13.1), minus the same ayanamsa. Swiss Ephemeris is
  not used for it.
* Categorical values (lagna rashi, Moon nakshatra and pada, tithi, D9 lagna, first Vimshottari
  maha lord) follow from those longitudes by the spec 5.1 / 5.4 / 5.6 formulas written out
  here. Each chart records the margin of every categorical value from its nearest boundary, and
  the build refuses a chart whose margin is below the spec 7 tolerance of that quantity (the
  intended boundary charts keep a margin of 1-2 arcmin, still above it).

Civil time is converted to UT with the engine's timeutil (pinned tzdata); the UTC instant and
offset used are recorded in each fixture so a tz regression shows up in tests.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_golden_horizons as horizons

from vedic_engine import ephemeris
from vedic_engine.constants import NAKSHATRAS, RASHIS, TITHIS, VIMSHOTTARI_ORDER
from vedic_engine.models import Settings
from vedic_engine.timeutil import jd_from_utc, to_utc

BACKEND = Path(__file__).resolve().parent.parent
OUT_DIR = BACKEND / "fixtures" / "golden" / "charts"
JD_DECIMALS = 9  # Horizons TLIST precision (~0.1 ms)
J2000 = 2451545.0
NAK = 360.0 / 27.0
PADA = NAK / 4.0
NAVAMSA = 30.0 / 9.0

# Spec 7 tolerances (arcsec) below which a categorical margin is not trusted. The tithi
# elongation Moon - Sun carries both errors: Moon 2" + Sun 1".
MIN_MARGIN_ARCSEC = {"lagna": 60.0, "moon": 2.0, "tithi": 3.0}

KOLKATA, DELHI = "Asia/Kolkata", (28.6139, 77.2090)

# (id, local civil time, IANA tz, lat, lon, coverage tags, note)
CHARTS: tuple[tuple[str, str, str, float, float, tuple[str, ...], str], ...] = (
    ("london_1850", "1850-03-21T10:15:00", "Europe/London", 51.5074, -0.1278,
     ("year_1850", "west_longitude"), ""),
    ("paris_1875", "1875-07-04T03:10:00", "Europe/Paris", 48.8566, 2.3522,
     ("pre_sunrise",), "tzdb Paris LMT +0:09:21"),
    ("calcutta_1900", "1900-04-12T14:20:00", KOLKATA, 22.5726, 88.3639,
     ("pre_1947_india",),
     ("tzdb Asia/Kolkata gives +5:21:10 (Madras time) in 1900; Calcutta's local time "
      "(+5:53:20) is not representable as an IANA zone")),
    ("chicago_1920", "1920-11-02T08:45:00", "America/Chicago", 41.8781, -87.6298,
     ("west_longitude",), ""),
    ("bombay_1943", "1943-05-20T10:30:00", KOLKATA, 19.0760, 72.8777,
     ("pre_1947_india", "war_time", "dst"), "tzdb Asia/Kolkata war time +6:30 (1942-09-01..1945-10-15)"),
    ("new_delhi_1947", "1947-08-15T00:00:00", KOLKATA, *DELHI,
     ("pre_sunrise", "midnight"), "India independence; tithi changes 34 s after birth"),
    ("moscow_1961", "1961-04-12T09:07:00", "Europe/Moscow", 55.7558, 37.6173, (), ""),
    ("tokyo_1955", "1955-03-30T23:40:00", "Asia/Tokyo", 35.6762, 139.6503, (), ""),
    ("buenos_aires_1962", "1962-09-03T18:05:00", "America/Argentina/Buenos_Aires",
     -34.6037, -58.3816, ("southern_hemisphere", "west_longitude", "dst"), ""),
    ("new_york_1969_dst", "1969-07-20T22:56:00", "America/New_York", 40.7128, -74.0060,
     ("west_longitude", "dst"), ""),
    ("toronto_1971_moon_boundary", "1971-05-02T01:21:30", "America/Toronto", 43.6532, -79.3832,
     ("west_longitude", "dst", "pre_sunrise", "moon_boundary"),
     "Moon ~1 arcmin after the start of Ashlesha"),
    ("berlin_1975", "1975-10-05T17:30:00", "Europe/Berlin", 52.5200, 13.4050, (), ""),
    ("johannesburg_1978", "1978-02-11T12:01:00", "Africa/Johannesburg", -26.2041, 28.0473,
     ("southern_hemisphere",), ""),
    ("reykjavik_1980", "1980-12-21T13:00:00", "Atlantic/Reykjavik", 64.1466, -21.9426,
     ("west_longitude", "high_latitude"), ""),
    ("varanasi_1984_lagna_boundary", "1984-03-15T15:42:52", KOLKATA, 25.3176, 82.9739,
     ("lagna_boundary",), "lagna ~1.4 arcmin after the start of Simha"),
    ("sydney_1985_dst", "1985-01-15T16:20:00", "Australia/Sydney", -33.8688, 151.2093,
     ("southern_hemisphere", "dst"), ""),
    ("mexico_city_1985", "1985-09-19T07:17:00", "America/Mexico_City", 19.4326, -99.1332,
     ("west_longitude",), ""),
    ("los_angeles_1990_dst", "1990-08-15T04:30:00", "America/Los_Angeles", 34.0522, -118.2437,
     ("west_longitude", "dst", "pre_sunrise"), ""),
    ("kathmandu_1990", "1990-06-21T04:05:00", "Asia/Kathmandu", 27.7172, 85.3240,
     ("pre_sunrise",), "UTC+5:45"),
    ("sao_paulo_1995_dst", "1995-12-10T02:40:00", "America/Sao_Paulo", -23.5505, -46.6333,
     ("southern_hemisphere", "west_longitude", "dst", "pre_sunrise"), ""),
    ("honolulu_1999", "1999-09-09T09:09:00", "Pacific/Honolulu", 21.3069, -157.8583,
     ("west_longitude",), ""),
    ("chennai_2000", "2000-01-01T00:01:00", KOLKATA, 13.0827, 80.2707,
     ("pre_sunrise", "midnight"), ""),
    ("london_2005_lagna_boundary", "2005-11-05T20:45:22", "Europe/London", 51.5074, -0.1278,
     ("west_longitude", "lagna_boundary"), "lagna ~1.6 arcmin before the end of Mithuna"),
    ("auckland_2010_dst", "2010-02-14T03:15:00", "Pacific/Auckland", -36.8485, 174.7633,
     ("southern_hemisphere", "dst", "pre_sunrise"), ""),
    ("cairo_2015", "2015-05-01T05:10:00", "Africa/Cairo", 30.0444, 31.2357, ("pre_sunrise",), ""),
    ("kolkata_2018_moon_boundary", "2018-10-21T05:45:29", KOLKATA, 22.5726, 88.3639,
     ("moon_boundary",), "Moon ~1 arcmin before the end of Shatabhisha"),
    ("singapore_2024", "2024-03-08T21:30:00", "Asia/Singapore", 1.3521, 103.8198, (), ""),
    ("new_delhi_2030", "2030-06-01T11:11:00", KOLKATA, *DELHI, ("year_2030",), ""),
)  # fmt: skip

# Values the brief states for the 1947 chart; the build checks the references agree.
EXPECTED_1947 = {"lagna_rashi": "vrishabha", "moon_nakshatra": "pushya", "moon_pada": 1,
                 "first_maha_lord": "saturn"}  # fmt: skip


def _norm(deg: float) -> float:
    return deg % 360.0


def precession_iau1976_minus_iau2006_arcsec(jd: float) -> float:
    """p_A(IAU 1976, Lieske et al. 1977) - p_A(IAU 2006, Capitaine et al. 2003), arcsec."""
    t = (jd - J2000) / 36525.0
    p76 = 5029.0966 * t + 1.11113 * t**2 - 0.000006 * t**3
    p06 = (
        5028.796195 * t
        + 1.1054348 * t**2
        + 0.00007964 * t**3
        - 0.000023857 * t**4
        - 0.0000000383 * t**5
    )
    return p76 - p06


def nutation_deg(jd: float) -> tuple[float, float]:
    """(nutation in longitude, nutation in obliquity) in degrees; Meeus ch. 22 short series
    (accuracy 0.5" in longitude, 0.1" in obliquity)."""
    t = (jd - J2000) / 36525.0
    om = math.radians(125.04452 - 1934.136261 * t)
    ls = math.radians(280.4665 + 36000.7698 * t)
    lm = math.radians(218.3165 + 481267.8813 * t)
    dpsi = -17.20 * math.sin(om) - 1.32 * math.sin(2 * ls) - 0.23 * math.sin(2 * lm)
    dpsi += 0.21 * math.sin(2 * om)
    deps = 9.20 * math.cos(om) + 0.57 * math.cos(2 * ls) + 0.10 * math.cos(2 * lm)
    deps -= 0.09 * math.cos(2 * om)
    return dpsi / 3600.0, deps / 3600.0


def tropical_ascendant(jd_ut: float, lat: float, lon_east: float) -> dict[str, float]:
    """Tropical ascendant of date from apparent local sidereal time and true obliquity."""
    d = jd_ut - J2000
    t = d / 36525.0
    gmst = 280.46061837 + 360.98564736629 * d + 0.000387933 * t**2 - t**3 / 38710000.0
    eps0 = 23.0 + 26.0 / 60.0 + (21.448 - 46.8150 * t - 0.00059 * t**2 + 0.001813 * t**3) / 3600
    dpsi, deps = nutation_deg(jd_ut)
    eps = eps0 + deps
    gast = gmst + dpsi * math.cos(math.radians(eps))
    ramc = _norm(gast + lon_east)
    th, e, phi = math.radians(ramc), math.radians(eps), math.radians(lat)
    asc = math.degrees(
        math.atan2(math.cos(th), -(math.sin(th) * math.cos(e) + math.tan(phi) * math.sin(e)))
    )
    return {"gmst_deg": _norm(gmst), "gast_deg": _norm(gast), "ramc_deg": ramc,
            "true_obliquity_deg": eps, "ascendant_tropical": _norm(asc)}  # fmt: skip


def _margin_arcsec(lon: float, span: float) -> float:
    """Distance (arcsec) of ``lon`` from the nearest multiple of ``span``."""
    r = _norm(lon) % span
    return min(r, span - r) * 3600.0


def categorical(sid: dict[str, float]) -> tuple[dict[str, Any], dict[str, float]]:
    lagna, moon, sun = sid["lagna"], sid["moon"], sid["sun"]
    nak = int(moon // NAK)
    pada = int((moon - nak * NAK) // PADA) + 1
    elong = _norm(moon - sun)
    tithi = int(elong // 12.0) + 1
    expected = {
        "lagna_rashi": RASHIS[int(lagna // 30.0)],
        "moon_nakshatra": NAKSHATRAS[nak],
        "moon_pada": pada,
        "tithi": tithi,
        "tithi_key": TITHIS[tithi - 1],
        "d9_lagna": RASHIS[int(lagna // NAVAMSA) % 12],  # continuous D9 formula
        "first_maha_lord": VIMSHOTTARI_ORDER[nak % 9].value,
    }
    margins = {
        "lagna_arcsec": _margin_arcsec(lagna, 30.0),
        "d9_lagna_arcsec": _margin_arcsec(lagna, NAVAMSA),
        "moon_pada_arcsec": _margin_arcsec(moon, PADA),  # nakshatra edges are pada edges
        "moon_nakshatra_arcsec": _margin_arcsec(moon, NAK),
        "tithi_elongation_arcsec": _margin_arcsec(elong, 12.0),
    }
    return expected, margins


def _check_margins(cid: str, m: dict[str, float]) -> None:
    low = {
        "lagna_arcsec": m["lagna_arcsec"] < MIN_MARGIN_ARCSEC["lagna"],
        "d9_lagna_arcsec": m["d9_lagna_arcsec"] < MIN_MARGIN_ARCSEC["lagna"],
        "moon_pada_arcsec": m["moon_pada_arcsec"] < MIN_MARGIN_ARCSEC["moon"],
        "tithi_elongation_arcsec": m["tithi_elongation_arcsec"] < MIN_MARGIN_ARCSEC["tithi"],
    }
    bad = [k for k, v in low.items() if v]
    if bad:
        raise SystemExit(f"{cid}: categorical margin below tolerance: {bad} {m}")


def _fetch(jds: list[float]) -> dict[float, dict[str, float]]:
    out: dict[float, dict[str, float]] = {jd: {} for jd in jds}
    for graha, command in horizons.BODIES.items():
        table = horizons._parse(horizons._query(command, jds, JD_DECIMALS), JD_DECIMALS)
        for jd in jds:
            out[jd][graha] = table[jd]
    return out


def _tz_facts(local: datetime, tz: str, utc: datetime) -> dict[str, Any]:
    aware = local.replace(tzinfo=ZoneInfo(tz))
    dst = aware.dst()
    offset = local - utc.replace(tzinfo=None)
    return {
        "utc": utc.isoformat(),
        "utc_offset_seconds": int(offset.total_seconds()),
        "dst": bool(dst),
    }


def _before_sunrise(
    local: datetime, tz: str, lat: float, lon: float, jd: float, settings: Settings
) -> bool:
    """Born between local midnight and that civil day's sunrise (engine sunrise, Drik-verified)."""
    midnight = round(
        jd_from_utc(to_utc(datetime(local.year, local.month, local.day), tz)), JD_DECIMALS
    )
    sunrise = ephemeris.rise_set(midnight, lat, lon, 0.0, "sun", "rise", settings)
    return sunrise is not None and midnight <= jd < sunrise


def main() -> int:
    ephemeris.init(BACKEND / "ephe")
    settings = Settings()
    retrieved = datetime.now(UTC).date().isoformat()
    births = []
    for cid, local_s, tz, lat, lon, tags, note in CHARTS:
        local = datetime.fromisoformat(local_s)
        utc = to_utc(local, tz)
        jd = round(jd_from_utc(utc), JD_DECIMALS)
        tz_facts = _tz_facts(local, tz, utc)
        if ("dst" in tags) != tz_facts["dst"]:
            raise SystemExit(f"{cid}: dst tag {('dst' in tags)} but tzdb dst {tz_facts['dst']}")
        if ("pre_sunrise" in tags) != _before_sunrise(local, tz, lat, lon, jd, settings):
            raise SystemExit(f"{cid}: pre_sunrise tag disagrees with the local sunrise")
        births.append((cid, local, tz, lat, lon, tags, note, tz_facts, jd))
    tropical = _fetch([b[-1] for b in births])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for cid, local, tz, lat, lon, tags, note, tz_facts, jd in births:
        aya = ephemeris.ayanamsa(jd, settings)
        shift = precession_iau1976_minus_iau2006_arcsec(jd)
        sid = {g: _norm(v - shift / 3600.0 - aya) for g, v in tropical[jd].items()}
        asc = tropical_ascendant(jd, lat, lon)
        sid["lagna"] = _norm(asc["ascendant_tropical"] - aya)
        expected, margins = categorical(sid)
        _check_margins(cid, margins)
        if cid == "new_delhi_1947":
            got = {k: expected[k] for k in EXPECTED_1947}
            if got != EXPECTED_1947:
                raise SystemExit(f"1947 chart disagrees with the brief: {got}")
        fixture = {
            "id": cid,
            "coverage": sorted(tags),
            "note": note,
            "birth": {
                "local": local.isoformat(),
                "tz": tz,
                "lat": lat,
                "lon": lon,
                "alt": 0.0,
                "fold": None,
            },
            "time": {**tz_facts, "jd_ut": jd},
            "source": {
                "planets": "JPL Horizons DE441, quantity 31 (apparent geocentric IAU76/80 "
                "ecliptic of date), CENTER 500@399, TIME_TYPE UT",
                "planet_frame_shift": "IAU1976 -> IAU2006 equinox: minus p_A(1976) - p_A(2006) "
                "(Lieske et al. 1977; Capitaine et al. 2003)",
                "ayanamsa": "engine Lahiri true ayanamsa (verified against the Indian "
                "Astronomical Ephemeris, tests/golden/test_horizons.py)",
                "lagna": "Meeus GMST (12.4) + nutation (ch. 22) -> apparent sidereal time, "
                "true obliquity (22.2), ascendant (ch. 14), minus ayanamsa; no Swiss Ephemeris",
                "timezone": "IANA tzdb via the pinned tzdata package",
            },
            "verified_by": "scripts/build_golden_charts.py: categorical values derived from "
            "the reference longitudes with spec 5.1/5.4/5.6 formulas; every categorical "
            "margin checked above the spec 7 tolerance",
            "retrieved": retrieved,
            "reference": {
                "tropical_horizons": tropical[jd],
                "precession_shift_arcsec": shift,
                "ayanamsa_deg": aya,
                **asc,
            },
            "sidereal": sid,
            "expected": expected,
            "margins": margins,
        }
        path = OUT_DIR / f"{cid}.json"
        path.write_text(json.dumps(fixture, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        print(f"{cid}: {expected}  margins { ({k: round(v, 1) for k, v in margins.items()}) }")
    print(f"wrote {len(births)} charts to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
