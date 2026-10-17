"""Accuracy report: engine vs every reference of spec section 7 -> reports/accuracy.md.

Run from backend/:  uv run python scripts/accuracy_report.py [--skip-perf] [--out PATH]

One table row per quantity: reference, number of cases, max and mean error, tolerance and
PASS/FAIL. Exit code 1 if any row fails. The checks reuse the helpers of the golden tests (the
same convention reconciliations, the same fixtures), so the report and the test suite cannot
drift apart; the tolerances come from tests/tolerances.py.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import swisseph as swe

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
for sub in ("tests", "tests/golden", "tests/unit", "tests/perf"):
    sys.path.insert(0, str(BACKEND / sub))

import test_ashtakavarga as t_av
import test_charts as t_charts
import test_drik as t_drik
import test_horizons as t_hor
import test_latency as t_lat
import test_shadbala_example as t_sb

import tolerances as tol
from chart_fixtures import CHART_PATHS, birth_of, load_chart
from vedic_engine import ephemeris, panchang
from vedic_engine.angles import sign_of
from vedic_engine.ashtakavarga import bav, sav
from vedic_engine.constants import NAKSHATRAS, RASHIS, SEVEN, Graha
from vedic_engine.kundli import build_kundli
from vedic_engine.models import Settings
from vedic_engine.shadbala import shadbala_from_inputs
from vedic_engine.timeutil import jd_from_utc, utc_from_jd
from vedic_engine.varga import VARGAS, varga_sign


@dataclass
class Row:
    quantity: str
    reference: str
    errors: list[float]
    tolerance: float
    unit: str
    exact: bool = False  # tolerance 0: errors count mismatches
    note: str = ""

    @property
    def n(self) -> int:
        return len(self.errors)

    @property
    def max_err(self) -> float:
        return max(self.errors) if self.errors else 0.0

    @property
    def mean_err(self) -> float:
        return statistics.fmean(self.errors) if self.errors else 0.0

    @property
    def passed(self) -> bool:
        return self.n > 0 and self.max_err <= self.tolerance


@dataclass
class Report:
    rows: list[Row] = field(default_factory=list)
    notes: dict[str, float] = field(default_factory=dict)


def _fmt(x: float, unit: str) -> str:
    return f"{x:.0f}" if unit == "mismatches" else f"{x:.4f} {unit}"


# --- JPL Horizons and IAE ------------------------------------------------------------------------


def horizons_rows() -> list[Row]:
    planet: list[float] = []
    moon: list[float] = []
    for path in t_hor.HORIZONS:
        data = t_hor._load(path)
        jd_ut = t_hor._engine_ut_for_horizons(data["jd_ut"])
        jd_tt = jd_ut + swe.deltat(jd_ut)
        shift = t_hor._iau1976_minus_iau2006_arcsec(jd_tt) / 3600.0
        for g in SEVEN:
            ours = ephemeris.tropical_longitude(jd_ut, g) + shift
            err = abs(t_hor._signed_arcsec(ours, data["lon"][g.value]))
            (moon if g is Graha.MOON else planet).append(err)
    ay = []
    for v in t_hor.AYANAMSA_VALUES:
        ours = ephemeris.ayanamsa(v["jd_ut"], Settings())
        ay.append(abs(ours - v["ayanamsa_deg"]) * 3600.0)
    return [
        Row("Planet tropical longitude (Sun, Mars, Mercury, Jupiter, Venus, Saturn)",
            "JPL Horizons DE441 (apparent, geocentric)", planet, tol.PLANET_ARCSEC, "arcsec"),
        Row("Moon tropical longitude", "JPL Horizons DE441 (apparent, geocentric)",
            moon, tol.MOON_ARCSEC, "arcsec"),
        Row("Lahiri true ayanamsa", "Indian Astronomical Ephemeris (published values)",
            ay, tol.AYANAMSA_ARCSEC, "arcsec"),
    ]  # fmt: skip


# --- Golden charts -------------------------------------------------------------------------------


# Vimshottari order and years (BPHS Ch 46), typed here independently of the engine tables.
_VIM = [("ketu", 7), ("venus", 20), ("sun", 6), ("moon", 10), ("mars", 7), ("rahu", 18),
        ("jupiter", 16), ("saturn", 19), ("mercury", 17)]  # fmt: skip
_NAK = 360.0 / 27


def _independent_dashas(moon_sid: float, birth: datetime, year_days: float):  # type: ignore[no-untyped-def]
    """(maha start, maha lord, [(antar start, antar lord)]) from the formula, unclipped.

    Balance = (1 - fraction of the nakshatra traversed) x lord years; each maha lasts
    years x year_days; antar k of a maha starts at cumulative antar-years / 120 of it.
    """
    nak = min(int((moon_sid % 360.0) // _NAK), 26)
    frac = ((moon_sid % 360.0) - nak * _NAK) / _NAK
    i0 = nak % 9
    start = birth - timedelta(days=frac * _VIM[i0][1] * year_days)
    out = []
    for k in range(10):  # 10 mahas cover birth + 120 years from any starting lord
        lord, years = _VIM[(i0 + k) % 9]
        antars = []
        cum = 0
        for j in range(9):
            a_lord, a_years = _VIM[((i0 + k) % 9 + j) % 9]
            antars.append((start + timedelta(days=years * year_days * cum / 120), a_lord))
            cum += a_years
        out.append((start, lord, antars))
        start += timedelta(days=years * year_days)
    return out


def chart_rows() -> list[Row]:
    planet: list[float] = []
    moon: list[float] = []
    lagna: list[float] = []
    cat_miss: list[float] = []
    cat_checked = 0
    dasha_err: list[float] = []
    seq_miss: list[float] = []
    varga_miss: list[float] = []
    for path in CHART_PATHS:
        c = load_chart(path)
        k = build_kundli(birth_of(c))
        sid = c["sidereal"]
        for g in SEVEN:
            err = t_charts._arcsec(k.grahas[g].lon, sid[g.value])
            (moon if g is Graha.MOON else planet).append(err)
        lagna.append(t_charts._arcsec(k.lagna_lon, sid["lagna"]) / 60.0)
        # Vargas of every chart point from the independent reference longitudes.
        ref_lon = {key: sid[key] for key in sid}
        for n in VARGAS:
            for key, lon_ref in ref_lon.items():
                want = varga_sign(lon_ref, n)
                got_sign = k.vargas[n].get(key)
                varga_miss.append(0.0 if got_sign == want else 1.0)
        # Vimshottari: starts from the reference Moon, lord sequence from the BPHS order.
        birth_utc = datetime.fromisoformat(c["time"]["utc"])
        ref = _independent_dashas(sid["moon"], birth_utc, Settings().dasha_year_days)
        mahas = k.vimshottari
        for (r_start, r_lord, r_antars), m in zip(ref, mahas, strict=False):
            seq_miss.append(0.0 if m.lord == r_lord else 1.0)
            dasha_err.append(abs((m.nominal_start_utc - r_start).total_seconds()) / 86400.0)
            # The engine drops antars that ended before birth; match the rest by position
            # from the end of the formula list (the sequence check covers the lords).
            skipped = len(r_antars) - len(m.children)
            seq_miss.append(0.0 if skipped >= 0 else 1.0)
            for (a_start, a_lord), a in zip(r_antars[max(skipped, 0) :], m.children, strict=True):
                seq_miss.append(0.0 if a.lord == a_lord else 1.0)
                if a.nominal_start_utc is not None:
                    dasha_err.append(abs((a.nominal_start_utc - a_start).total_seconds()) / 86400.0)
        exp = c["expected"]
        got = {
            "lagna_rashi": RASHIS[sign_of(k.lagna_lon)],
            "moon_nakshatra": NAKSHATRAS[k.panchang.nakshatra.index],
            "moon_pada": k.panchang.pada,
            "tithi": k.panchang.tithi.index,
            "tithi_key": k.panchang.tithi.key,
            "d9_lagna": RASHIS[k.vargas[9]["lagna"]],
            "first_maha_lord": k.vimshottari[0].lord,
        }
        for key, value in got.items():
            cat_checked += 1
            cat_miss.append(0.0 if value == exp[key] else 1.0)
    ref = "Golden charts: Horizons minus IAE-verified Lahiri (Jagannath Hora exports pending)"
    return [
        Row("Sidereal planet longitude (golden charts, 6 planets)", ref,
            planet, tol.PLANET_ARCSEC, "arcsec"),
        Row("Sidereal Moon longitude (golden charts)", ref, moon, tol.MOON_ARCSEC, "arcsec"),
        Row("Ascendant (lagna), sidereal",
            "Independent Meeus sidereal-time computation (no Swiss Ephemeris)",
            lagna, tol.LAGNA_ARCMIN, "arcmin"),
        Row(f"Categorical values ({cat_checked // len(CHART_PATHS)} per chart: lagna rashi, "
            "Moon nakshatra/pada, tithi, D9 lagna, first Maha lord)",
            "Golden chart fixtures", cat_miss, 0.0, "mismatches", exact=True),
        Row("Varga signs, all 16 vargas x lagna and 7 grahas",
            "Varga rules applied to the independent reference longitudes (checks the pipeline, "
            "not the rule tables; those are covered by unit tests)",
            varga_miss, 0.0, "mismatches", exact=True),
        Row("Vimshottari Maha and Antar start dates (all periods in 120 years)",
            "Independent formula from the reference Moon (nakshatra fraction, balance, "
            "cumulative years x dasha year of 365.25 d); JHora exports pending",
            dasha_err, tol.DASHA_DAYS, "days"),
        Row("Vimshottari Maha and Antar lord sequence",
            "BPHS Vimshottari order and years", seq_miss, 0.0, "mismatches", exact=True),
    ]  # fmt: skip


# --- Drik Panchang -------------------------------------------------------------------------------


def drik_rows() -> tuple[list[Row], dict[str, float]]:
    default = t_drik.DEFAULT
    sun_err: list[float] = []
    ends: dict[str, list[float]] = {"tithi": [], "nakshatra": [], "yoga": [], "karana": []}
    raw: dict[str, list[float]] = {"tithi": [], "karana": []}
    key_miss: list[float] = []
    for path in t_drik.DRIK:
        fx: dict[str, Any] = json.loads(path.read_text())
        loc = fx["location"]
        tz, lat, lon, alt = loc["tz"], loc["lat"], loc["lon"], float(loc["elevation_m"])
        day = date.fromisoformat(fx["date"])
        dp = panchang.day_panchang(day, tz, lat, lon, alt, default)
        nxt = panchang.day_panchang(day + timedelta(days=1), tz, lat, lon, alt, default)
        sun_err.append(t_drik._minutes(dp.sunrise_utc, t_drik._utc(fx["sunrise_local"], tz)))
        sun_err.append(t_drik._minutes(dp.sunset_utc, t_drik._utc(fx["sunset_local"], tz)))
        for name, rows in fx["elements"].items():
            at = getattr(dp.at_sunrise, name)
            prev_end = drik_prev_end = jd_from_utc(dp.sunrise_utc)
            for i, row in enumerate(rows):
                if i > 0:
                    at = getattr(
                        panchang.elements_at(prev_end + t_drik.SECOND, lat, lon, alt, default),
                        name,
                    )
                key_miss.append(0.0 if at.key == row["key"] else 1.0)
                if row["ends_local"] is None:
                    outlasts = at.ends_utc > nxt.sunrise_utc - timedelta(minutes=tol.TIME_MINUTES)
                    key_miss.append(0.0 if outlasts else 1.0)
                    break
                ref = t_drik._utc(row["ends_local"], tz)
                if name in t_drik.SPAN:
                    # raw: the engine's own end time, no Delta T convention applied
                    raw[name].append(t_drik._minutes(at.ends_utc, ref) * 60.0)
                    drik_prev_end = panchang.find_end(
                        t_drik._drik_elongation, drik_prev_end, t_drik.SPAN[name]
                    )
                    got = utc_from_jd(drik_prev_end)
                    drik_prev_end += t_drik.SECOND
                else:
                    got = at.ends_utc
                ends[name].append(t_drik._minutes(got, ref))
                prev_end = jd_from_utc(at.ends_utc)
    src = "Drik Panchang, New Delhi (transcribed)"
    rows_out = [
        Row("Sunrise and sunset (upper limb, refraction)", src, sun_err, tol.TIME_MINUTES, "min"),
        Row("Tithi end times (Drik Delta T convention, see note)", src,
            ends["tithi"], tol.TIME_MINUTES, "min"),
        Row("Karana end times (Drik Delta T convention, see note)", src,
            ends["karana"], tol.TIME_MINUTES, "min"),
        Row("Nakshatra end times", src, ends["nakshatra"], tol.TIME_MINUTES, "min"),
        Row("Yoga end times", src, ends["yoga"], tol.TIME_MINUTES, "min"),
        Row("Panchang element sequence per day (key at each Drik row, open-ended rows)", src,
            key_miss, 0.0, "mismatches", exact=True),
    ]  # fmt: skip
    notes = {
        "raw_max_s": max(raw["tithi"] + raw["karana"]),
        "raw_mean_s": statistics.fmean(raw["tithi"] + raw["karana"]),
        "raw_n": float(len(raw["tithi"] + raw["karana"])),
    }
    return rows_out, notes


# --- BPHS worked examples ------------------------------------------------------------------------


def ashtakavarga_rows() -> list[Row]:
    result = bav(t_av.EXAMPLE)
    exact_miss: list[float] = []
    for g, printed in t_av.PRINTED.items():
        want = t_av._by_rashi(printed)
        exact_miss += [float(a != b) for a, b in zip(result[g], want, strict=True)]
    variant_miss: list[float] = []
    for g, printed in t_av.PRINTED_DISPUTED.items():
        diff = tuple(a - b for a, b in zip(result[g], t_av._by_rashi(printed), strict=True))
        variant_miss += [float(a != b) for a, b in zip(diff, t_av.KNOWN_DEVIATION[g], strict=True)]
    src = "BPHS (Santhanam) Vol. 2 worked example, Ch 66-72"
    return [
        Row("Bhinnashtakavarga bindus per rashi (Sun, Mars, Jupiter, Venus, Saturn)", src,
            exact_miss, 0.0, "mismatches", exact=True),
        Row("Sarvashtakavarga total (337 for any chart)", src,
            [float(abs(sum(sav(result)) - 337))], 0.0, "mismatches", exact=True),
        Row("Moon and Mercury rows: deviation from the printed row equals the documented one",
            src + " (misprints, ruling R22, see below)",
            variant_miss, 0.0, "mismatches", exact=True),
    ]  # fmt: skip


def shadbala_rows() -> list[Row]:
    rows = shadbala_from_inputs(t_sb._inputs())
    ok: list[float] = []
    misprint: list[float] = []
    for g in SEVEN:
        for name in t_sb.TOP_LEVEL + t_sb.SUB:
            printed = t_sb.PRINTED[name]["values"][SEVEN.index(g)]
            err = abs(t_sb._value(rows[g], name) - printed)
            if g in t_sb.KNOWN_MISPRINT and name in t_sb._CARRIES_MISPRINT:
                diff = t_sb._value(rows[g], name) - printed
                misprint.append(abs(diff - t_sb.KNOWN_MISPRINT[g]))
            else:
                ok.append(err)
    src = "B. V. Raman, Graha and Bhava Balas, worked example (printed inputs, formulas only)"
    return [
        Row("Shadbala components (7 grahas)", src, ok, tol.SHADBALA_VIRUPA, "virupa"),
        Row("Shadbala rows carrying a documented book misprint (Mars, Saturn): "
            "deviation minus the documented one", src, misprint, tol.SHADBALA_VIRUPA, "virupa"),
    ]  # fmt: skip


def latency_row() -> Row:
    births = t_lat._births()
    for b in births[: t_lat.WARMUP]:
        build_kundli(b)
    import time

    ms: list[float] = []
    for b in births[t_lat.WARMUP :]:
        t0 = time.perf_counter()
        build_kundli(b)
        ms.append((time.perf_counter() - t0) * 1000.0)
    ms.sort()
    p95 = ms[int(0.95 * len(ms)) - 1]
    row = Row("build_kundli latency, P95 over 200 random births 1900-2100 (default args)",
              "Spec section 7 budget", [p95], float(tol.P95_MS) - 1e-9, "ms")  # fmt: skip
    row.note = f"median {statistics.median(ms):.1f} ms, max {ms[-1]:.1f} ms; machine-dependent"
    return row


# --- Rendering -----------------------------------------------------------------------------------


NOTES = """\
## Notes

### Conventions reconciled before comparing (tolerances untouched)

* **Horizons time scale.** After the last leap second Horizons' "UT" tag means TT = UT + 69.184 s,
  so the engine is evaluated at the same TT instant. **Horizons frame.** Quantity 31 uses the
  IAU 1976/80 ecliptic of date; the engine's IAU 2006 longitude is shifted by the difference of
  the two published general-precession polynomials (up to ~1.2" by 2399). Sidereal output is
  unaffected (the ayanamsa carries the same precession). See `tests/golden/test_horizons.py`.
* **Drik Panchang Delta T convention (ruling R15).** Drik's Sun and Moon are the engine's
  positions evaluated about Delta T (~69 s) later: Drik's own sidereal-positions page against
  the engine (JPL-verified to 1-2") on 2023-02-01, 2024-01-10 and 2026-10-16 gives a time offset
  of 70.8 / 65.6 / 68.2 s, i.e. Delta T counted twice. This shifts every tithi and karana end
  about one minute early. The *raw* difference, engine end time against the Drik figure with no
  correction, is at most **{raw_max:.0f} s** (mean {raw_mean:.0f} s over {raw_n:.0f} tithi/karana
  end times). That raw gap is a minute-scale convention offset, not an engine error, and the
  1-minute tolerance is applied only after like-with-like evaluation (elongation at UT + Delta T;
  Moon - Sun does not depend on the ayanamsa, so the time base is the only difference).
  Nakshatra and yoga carry Drik's ayanamsa offset, which partly cancels the time shift; they are
  compared directly and pass. See `tests/golden/test_drik.py`.

### Known source variants and open rulings

Where a reference disagrees with itself or with the standard practice, the engine's choice and
its cost if wrong are recorded as a ruling. None of these is a tolerance relaxation.

* **R15 (Drik Delta T convention).** Drik tithi/karana end times differ from the engine by up to
  96 s raw; explained above. The engine stays physically correct against JPL; users comparing
  with Drik will see up to about 1.5 minutes in a tithi end.
* **R22 (BPHS worked example, Moon and Mercury rows).** The printed rows (Santhanam pp. 886, 889)
  sum to 51 and 56, against 49 and 54 from the book's own per-house rekha columns and the BPHS
  totals. They are treated as misprints and pinned: the engine's difference from the printed rows
  is fixed exactly (Moon: Taurus -1, Capricorn +1, Aquarius -1, Pisces -1; Mercury: Libra -1,
  Capricorn -1) and checked by the third ashtakavarga row above. The Sun, Mars, Jupiter, Venus and
  Saturn rows match exactly.
* **R23 (standard table where Santhanam is inconsistent).** The benefic-house table follows the
  standard Parashari table of Jagannath Hora and B. V. Raman where the BPHS text contradicts
  itself (`src/vedic_engine/data/ashtakavarga_bphs.json`, `_note`): `venus.mars` is
  [3,5,6,9,11,12] (verses and rekha chart give 4 instead of 5; the book's worked example, p. 892,
  agrees with 5) and `moon.jupiter` is [1,4,7,8,10,11,12] (verses 46-48 put Jupiter in house 2 and
  none in 12; the house table has 12). Cost if wrong: one bindu in the Venus or Moon BAV.
* **R24 (OPEN, needs user verification).** Santhanam's BPHS consistently places the Moon BAV
  9th-house bindu under Moon-from-Moon (verse, rekha chart and house table); JHora and Raman place
  it under Mars-from-Moon. The engine follows JHora (`moon.moon` [1,3,6,7,10,11],
  `moon.mars` [2,3,5,6,9,10,11]). **Verify against a real Jagannath Hora export (the Moon BAV
  row).** If the engine is wrong, one bindu moves between contributors, so the Moon BAV row
  differs in 1-2 rashis.
* **R25 (Raman p. 22 Saptavargaja, Mars and Saturn).** The printed Saptavargaja for Mars (112.5)
  and Saturn (82.5) contradict the book's own rules (Mars trimsamsa entry, Saturn saptamsa entry).
  They are pinned as strict xfails with an exact-gap test; Sthana and the totals carry the same
  difference. The "documented book misprint" shadbala row above checks the pinned gap.
* Also noted in the JSON: Jupiter-from-Jupiter houses 1 and 4 are omitted from the English text of
  verse 53 but are in the Sanskrit and in the printed count chart (total 56).

### Not covered yet

* Jagannath Hora exports (spec section 7): drop them into `fixtures/golden/jhora/`; no code change
  is needed to run them through `tests/golden/test_charts.py`.
* Dasha start dates (1-day tolerance) have no external reference yet; Vimshottari is covered by
  the first-Maha-lord check above and the property tests (sub-periods sum exactly, 120-year cycle).
* Shadbala from engine-computed inputs is not compared with an external source; the example
  checks the formulas on the book's printed inputs.
"""


def render(report: Report, generated: str) -> str:
    lines = [
        "# Accuracy report",
        "",
        (
            f"Generated {generated} by `backend/scripts/accuracy_report.py` "
            f"(engine `{_engine_version()}`). Tolerances are those of spec section 7 "
            "(`backend/tests/tolerances.py`)."
        ),
        "",
        "| Quantity | Reference | n | Max error | Mean error | Tolerance | Result |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for r in report.rows:
        tol_txt = "exact" if r.exact else f"{r.tolerance:g} {r.unit}"
        if r.unit == "ms":
            tol_txt = f"< {tol.P95_MS} ms"
        lines.append(
            f"| {r.quantity} | {r.reference} | {r.n} | {_fmt(r.max_err, r.unit)} | "
            f"{_fmt(r.mean_err, r.unit)} | {tol_txt} | {'PASS' if r.passed else 'FAIL'} |"
        )
    extra = [f"* {r.quantity}: {r.note}" for r in report.rows if r.note]
    if extra:
        lines += ["", *extra]
    lines += ["", NOTES.format(
        raw_max=report.notes["raw_max_s"],
        raw_mean=report.notes["raw_mean_s"],
        raw_n=report.notes["raw_n"],
    )]  # fmt: skip
    return "\n".join(lines)


def _engine_version() -> str:
    from vedic_engine import __version__

    return __version__


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=REPO / "reports" / "accuracy.md")
    ap.add_argument("--skip-perf", action="store_true", help="omit the latency row")
    args = ap.parse_args(argv)

    ephemeris.init(BACKEND / "ephe")
    report = Report()
    steps: list[Callable[[], list[Row]]] = [
        horizons_rows, chart_rows, ashtakavarga_rows, shadbala_rows,
    ]  # fmt: skip
    for step in steps:
        report.rows += step()
    drik, report.notes = drik_rows()
    report.rows += drik
    if not args.skip_perf:
        report.rows.append(latency_row())

    text = render(report, datetime.now().astimezone().strftime("%Y-%m-%d"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    failed = [r for r in report.rows if not r.passed]
    for r in report.rows:
        print(
            f"{'PASS' if r.passed else 'FAIL'}  {r.quantity}  n={r.n}  max={_fmt(r.max_err, r.unit)}"
        )
    print(f"wrote {args.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
