"""Golden checks: day panchang for New Delhi vs Drik Panchang (fixtures/golden/drik).

The fixtures are Drik's own displayed values (see scripts/build_golden_drik.py): sunrise,
sunset and each element's "upto" time, at minute resolution. Drik's default sunrise is the
upper limb ("Edge") with refraction and without elevation dip, which is the engine default.

Each fixture lists every element in display order. The first prevails at sunrise; each next one
is checked by evaluating the engine one second after the previous end, so a tithi that begins
and ends between two sunrises (kshaya) is checked too. A row without an end time continues
past the next sunrise.

One documented convention difference is reconciled for tithi and karana end times (like with
like, as in test_horizons; the tolerance is untouched). Drik's Sun and Moon are those of the
engine evaluated about Delta T (~69 s) later: comparing Drik's own sidereal-positions page with
the engine (JPL-verified to 1-2") on 2023-02-01, 2024-01-10 and 2026-10-16 gives a time offset
of 70.8 / 65.6 / 68.2 s, i.e. Delta T counted twice. That shifts every tithi and karana end
~1 min early. Elongation (Moon - Sun) does not depend on the ayanamsa, so for these two
elements the time base is the only difference, and they are compared against the engine's
elongation at UT + Delta T. Nakshatra and yoga also carry Drik's ayanamsa offset (which
partly cancels the time shift); they are compared directly and pass.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import swisseph as swe

from tolerances import TIME_MINUTES
from vedic_engine import ephemeris, panchang
from vedic_engine.angles import arc
from vedic_engine.constants import Graha
from vedic_engine.models import Settings
from vedic_engine.timeutil import jd_from_utc, to_utc, utc_from_jd

pytestmark = pytest.mark.golden

GOLDEN = Path(__file__).resolve().parent.parent.parent / "fixtures" / "golden"
DRIK = sorted((GOLDEN / "drik").glob("*.json"))
DEFAULT = Settings()
SECOND = 1.0 / 86400.0


@pytest.fixture(autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


def _utc(local_iso: str, tz: str) -> datetime:
    return to_utc(datetime.fromisoformat(local_iso), tz)


def _drik_elongation(jd: float) -> float:
    """Moon - Sun as Drik computes it: the engine's positions at UT + Delta T."""
    t = jd + swe.deltat(jd)
    sun = ephemeris.body_longitude(t, Graha.SUN, DEFAULT, derived=True)
    moon = ephemeris.body_longitude(t, Graha.MOON, DEFAULT, derived=True)
    return arc(sun, moon)


SPAN = {"tithi": panchang.TITHI_SPAN, "karana": panchang.KARANA_SPAN}


def _minutes(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds()) / 60.0


def test_fixture_set() -> None:
    fixtures = [json.loads(p.read_text()) for p in DRIK]
    assert len(fixtures) == 11
    # One Adhik masa date, and one day on which a whole tithi lies between two sunrises
    # (two tithis end before the next sunrise: kshaya).
    assert sum("Adhik" in fx["chandramasa"]["amanta"] for fx in fixtures) == 1
    ends = [sum(r["ends_local"] is not None for r in fx["elements"]["tithi"]) for fx in fixtures]
    assert max(ends) >= 2


@pytest.mark.parametrize("path", DRIK, ids=[p.stem for p in DRIK])
def test_drik_day(path: Path) -> None:
    fx: dict[str, Any] = json.loads(path.read_text())
    loc = fx["location"]
    tz, lat, lon, alt = loc["tz"], loc["lat"], loc["lon"], float(loc["elevation_m"])
    day = date.fromisoformat(fx["date"])
    dp = panchang.day_panchang(day, tz, lat, lon, alt, DEFAULT)
    nxt = panchang.day_panchang(day + timedelta(days=1), tz, lat, lon, alt, DEFAULT)

    assert _minutes(dp.sunrise_utc, _utc(fx["sunrise_local"], tz)) <= TIME_MINUTES
    assert _minutes(dp.sunset_utc, _utc(fx["sunset_local"], tz)) <= TIME_MINUTES

    for name, rows in fx["elements"].items():
        at = getattr(dp.at_sunrise, name)
        prev_end = drik_prev_end = jd_from_utc(dp.sunrise_utc)
        for i, row in enumerate(rows):
            if i > 0:
                at = getattr(panchang.elements_at(prev_end + SECOND, lat, lon, alt, DEFAULT), name)
            assert at.key == row["key"], f"{name} row {i}"
            if row["ends_local"] is None:
                # Drik shows no end: the element outlasts the next sunrise.
                assert at.ends_utc > nxt.sunrise_utc - timedelta(minutes=TIME_MINUTES)
                break
            ref = _utc(row["ends_local"], tz)
            if name in SPAN:
                drik_prev_end = panchang.find_end(_drik_elongation, drik_prev_end, SPAN[name])
                ends = utc_from_jd(drik_prev_end)
                drik_prev_end += SECOND
            else:
                ends = at.ends_utc
            assert _minutes(ends, ref) <= TIME_MINUTES, f"{name} {row['key']} end"
            prev_end = jd_from_utc(at.ends_utc)
