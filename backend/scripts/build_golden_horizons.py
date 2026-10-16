"""Fetch JPL Horizons reference longitudes into golden fixtures (dev-time only, needs network).

Run manually from backend/:  uv run python scripts/build_golden_horizons.py
The JSON it writes under fixtures/golden/horizons/ is committed; tests never hit the network.

Quantity 31 = observer-centred IAU76/80 ecliptic-of-date longitude/latitude of the target's
apparent position (light-time, gravitational deflection, stellar aberration), geocentric
(CENTER 500@399). Swiss Ephemeris ``calc_ut`` without extra flags computes the same thing
(apparent, geocentric, true ecliptic and equinox of date), so the two compare like with like.
"""

from __future__ import annotations

import json
import random
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
OUT_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "golden" / "horizons"

# Horizons COMMAND id per graha. Jupiter and Saturn use the system barycentres (5, 6):
# Swiss Ephemeris returns barycentres for Jupiter..Pluto unless FLG_CENTER_BODY is set, and
# Horizons has no body-centre (599/699) ephemeris after A.D. 2200 (satellite theory limit).
BODIES: dict[str, str] = {
    "sun": "10",
    "moon": "301",
    "mercury": "199",
    "venus": "299",
    "mars": "499",
    "jupiter": "5",
    "saturn": "6",
}


def gregorian_jd(year: int, month: int, day: int, hour: float = 0.0) -> float:
    """Julian day of a proleptic-Gregorian date (Meeus, Astronomical Algorithms, ch. 7)."""
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5 + hour / 24.0


JD_MIN = gregorian_jd(1800, 1, 1)
JD_MAX = gregorian_jd(2399, 12, 31, 24.0)

FIXED_EPOCHS: tuple[float, ...] = (
    gregorian_jd(1801, 1, 1),
    gregorian_jd(1850, 1, 1),
    gregorian_jd(1900, 1, 1),
    gregorian_jd(1947, 8, 15),
    gregorian_jd(1975, 1, 1),
    gregorian_jd(2000, 1, 1, 12.0),
    gregorian_jd(2024, 1, 1),
    gregorian_jd(2100, 1, 1),
    gregorian_jd(2200, 1, 1),
    gregorian_jd(2399, 1, 1),
)


def epochs() -> list[float]:
    rng = random.Random(42)
    spread = [round(rng.uniform(JD_MIN, JD_MAX), 5) for _ in range(20)]
    return [*FIXED_EPOCHS, *spread]


def _query(command: str, jds: list[float]) -> str:
    params = {
        "format": "json",
        "COMMAND": f"'{command}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",
        "QUANTITIES": "'31'",
        "TIME_TYPE": "'UT'",
        "ANG_FORMAT": "'DEG'",
        "CAL_FORMAT": "'JD'",
        "CSV_FORMAT": "'YES'",
        "TLIST_TYPE": "'JD'",
        "TLIST": "'" + " ".join(f"{jd:.5f}" for jd in jds) + "'",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as resp:
        payload = json.load(resp)
    if "error" in payload:
        raise RuntimeError(f"Horizons error for {command}: {payload['error']}")
    result: str = payload["result"]
    return result


def _parse(result: str) -> dict[float, float]:
    """Map JD (UT) -> ecliptic longitude from a CSV quantity-31 table."""
    if "IAU76/80 ecliptic-of-date" not in result or "apparent position" not in result:
        raise RuntimeError("unexpected Horizons column definition for quantity 31")
    body = result.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    out: dict[float, float] = {}
    for line in body.strip().splitlines():
        cols = [c.strip() for c in line.split(",")]
        # JDUT, (solar presence flag), (lunar presence flag), ObsEcLon, ObsEcLat, ''
        nums = [c for c in cols if c]
        out[round(float(nums[0]), 5)] = float(nums[-2])
    return out


def main() -> int:
    jds = epochs()
    retrieved = datetime.now(UTC).date().isoformat()
    lon: dict[float, dict[str, float]] = {round(jd, 5): {} for jd in jds}
    for graha, command in BODIES.items():
        table = _parse(_query(command, jds))
        for jd, by_graha in lon.items():
            by_graha[graha] = table[jd]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for i, jd in enumerate(sorted(lon)):
        fixture = {
            "jd_ut": jd,
            "source": "JPL Horizons",
            "retrieved": retrieved,
            "ephemeris": "DE441",
            "query": {
                "EPHEM_TYPE": "OBSERVER",
                "CENTER": "500@399",
                "QUANTITIES": "31",
                "TIME_TYPE": "UT",
                "ANG_FORMAT": "DEG",
            },
            "frame": (
                "geocentric apparent IAU76/80 ecliptic-of-date longitude "
                "(light-time, gravitational deflection, stellar aberration)"
            ),
            "lon": lon[jd],
        }
        path = OUT_DIR / f"epoch_{i:02d}_jd{jd:.5f}.json"
        path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(lon)} fixtures to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
