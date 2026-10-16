# Phase 1 — Vedic Calculation Engine & API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A pure-Python Vedic calculation engine (`vedic_engine`) plus a thin FastAPI service that returns a complete, reproducible kundli, with accuracy proven by a regression suite against independent references.

**Architecture:** `vedic_engine` is a library of pure functions. `ephemeris.py` is the only module that imports `swisseph`; every other module takes plain longitudes and Julian days. `kundli.py` is the single orchestrator. `api/` handles validation, serialisation and error mapping only.

**Tech Stack:** Python 3.12, uv, pyswisseph 2.10.x, FastAPI, Pydantic v2, pytest, hypothesis, ruff, mypy, Docker, GitHub Actions.

**Spec:** `docs/specs/2026-10-16-phase1-calculation-engine-design.md` (section numbers below refer to it, e.g. "§5.4").

## Global Constraints

- Repo root `~/vedic-astro`; all Python lives under `backend/`. Commands below run from `backend/` unless stated.
- Python 3.12 managed with `uv`; `mypy --strict` and `ruff` must pass on `src/vedic_engine`.
- Backend licence AGPL-3.0 (`LICENSE` at repo root). GeoNames CC-BY 4.0 and Swiss Ephemeris AGPL attribution in `NOTICE.md`.
- Ayanamsa Lahiri (`swe.SIDM_LAHIRI`); flags `FLG_SWIEPH | FLG_SIDEREAL | FLG_SPEED`. Node default MEAN. Dasha year default 365.25 days. Sunrise default upper limb with refraction.
- Shipped ephemeris files: `sepl_18.se1`, `semo_18.se1`, `seas_18.se1` only. Supported range 1800-01-01 to 2399-12-31 CE; outside it → `EphemerisRangeError`, never a silent Moshier fallback.
- Longitudes are sidereal degrees normalised to [0, 360). Sign/nakshatra indices are 0-based in the engine and 1-based in the API.
- API returns stable lowercase machine keys (`"karka"`, `"punarvasu"`, `"sun"`), never display strings.
- Same `BirthInput` + `Settings` ⇒ byte-identical JSON.
- Tolerances are exactly those in spec §7; tests reference them through `tests/tolerances.py`, never as inline magic numbers.

## Review Focus

1. **Longitude at the 360°/0° wrap and on exact division edges** (e.g. 359.9999999°, 29.999999°, −1e-12 after a subtraction): a person expects Meena/Revati, not an index of 12 or 27 and not a crash. → Task 2 `test_wrap_and_edges`, Task 6 `test_varga_edges`.
2. **Birth before local sunrise**: the vaar must be the previous weekday (spec §5.1), while the date shown stays the civil date. → Task 5 `test_vaar_before_sunrise`.
3. **DST gaps and overlaps outside India** (e.g. `America/New_York` 2021-03-14 02:30 doesn't exist; 2021-11-07 01:30 occurs twice): a clear 422, never a silently shifted chart. → Task 3 `test_nonexistent_and_ambiguous`, Task 13 `test_api_ambiguous_time_422`.
4. **Birth at the very end of a nakshatra** (balance → 0): there must be no zero-length or negative first dasha period, and the periods must still add up to the full cycle. → Task 8 `test_balance_near_zero`.
5. **Searches that run past the ephemeris range** (a birth in 2350 plus a 100-year Sade Sati search): the search stops at 2399-12-31 and the result carries a warning instead of raising. → Task 9 `test_sade_sati_clamped_to_range`.

## File map

```
LICENSE  NOTICE.md  .github/workflows/ci.yml  Dockerfile  .gitignore
backend/pyproject.toml
backend/ephe/{sepl_18,semo_18,seas_18}.se1
backend/data/cities.tsv
backend/scripts/{fetch_ephe.sh, build_cities.py, build_golden_horizons.py, accuracy_report.py}
backend/src/vedic_engine/{__init__,constants,models,angles,timeutil,ephemeris,lagna,panchang,varga,dignity,avastha,doshas,transit,ashtakavarga,shadbala,sensitivity,names,kundli}.py
backend/src/vedic_engine/dasha/{__init__,vimshottari,yogini}.py
backend/src/vedic_engine/data/{ashtakavarga_bphs.json, i18n.json}
backend/src/api/{__init__,main,schemas,places}.py
backend/tests/{conftest.py, tolerances.py}
backend/tests/unit/test_*.py   backend/tests/property/test_*.py
backend/tests/golden/test_*.py backend/tests/perf/test_latency.py
backend/fixtures/golden/{horizons/*.json, drik/*.json, ayanamsa_iae.json, charts/*.json, shadbala_bphs_example.json, shri_ram.json}
```

---

### Task 1: Project scaffold, ephemeris files, CI

**Files:**
- Create: `LICENSE` (AGPL-3.0 full text), `NOTICE.md`, `.gitignore`, `backend/pyproject.toml`, `backend/scripts/fetch_ephe.sh`, `backend/src/vedic_engine/__init__.py`, `backend/tests/conftest.py`, `backend/tests/tolerances.py`, `.github/workflows/ci.yml`
- Test: `backend/tests/unit/test_smoke.py`

**Interfaces:**
- Produces: `vedic_engine.__version__ = "0.1.0"`; the pytest fixture `ephe_path -> Path` (in conftest) pointing at `backend/ephe`; constants in `tests/tolerances.py`: `PLANET_ARCSEC = 1.0`, `MOON_ARCSEC = 2.0`, `AYANAMSA_ARCSEC = 1.0`, `LAGNA_ARCMIN = 1.0`, `TIME_MINUTES = 1.0`, `DASHA_DAYS = 1.0`, `SHADBALA_VIRUPA = 1.0`, `P95_MS = 200`.

- [ ] **Step 1:** Install uv if missing (`brew install uv`), then run `uv init --package --name vedic-engine backend` and edit `pyproject.toml`: requires-python `>=3.12,<3.13`; deps `pyswisseph>=2.10.3,<2.11`, `fastapi>=0.115`, `uvicorn[standard]`, `pydantic>=2.8`; dev deps `pytest`, `pytest-xdist`, `hypothesis`, `ruff`, `mypy`, `httpx`. Packages: `src/vedic_engine` and `src/api`. Pytest markers: `golden`, `perf`, `network` (network is skipped by default).
- [ ] **Step 2:** `scripts/fetch_ephe.sh` downloads the three `.se1` files from `https://github.com/aloistr/swisseph/raw/master/ephe/` into `backend/ephe/`, then verifies they are non-empty. Commit the files (≈2 MB total), so the build never depends on the network.
- [ ] **Step 3: Write the failing test** `test_smoke.py::test_ephe_files_present` (all three files exist and are larger than 100 kB) and `test_swisseph_importable` (`swe.version` starts with `"2.10"`).
- [ ] **Step 4:** Run `uv run pytest tests/unit/test_smoke.py -v` → expect PASS after Steps 1–2. Run it once before Step 2 to see it fail.
- [ ] **Step 5:** CI workflow: on push/PR, `uv sync`, `uv run ruff check`, `uv run mypy --strict src/vedic_engine`, `uv run pytest -m "not network" -n auto`, then upload `reports/` as an artifact.
- [ ] **Step 6: Commit** `chore: scaffold backend, ephemeris files, CI`.

---

### Task 2: Constants, models, angle helpers

**Files:**
- Create: `src/vedic_engine/constants.py`, `models.py`, `angles.py`, `data/i18n.json`
- Test: `tests/unit/test_constants.py`, `tests/unit/test_angles.py`

**Interfaces:**
- Produces:
  - `class Graha(StrEnum)`: `SUN="sun", MOON="moon", MARS="mars", MERCURY="mercury", JUPITER="jupiter", VENUS="venus", SATURN="saturn", RAHU="rahu", KETU="ketu"`; `SEVEN: tuple[Graha, ...]` (Sun to Saturn).
  - `RASHIS: tuple[str, ...]` (12 keys: `mesha, vrishabha, mithuna, karka, simha, kanya, tula, vrishchika, dhanu, makara, kumbha, meena`); `RASHI_LORD: tuple[Graha, ...]`; `NAKSHATRAS: tuple[str, ...]` (27 keys, `ashwini` … `revati`); `VIMSHOTTARI_ORDER: tuple[Graha, ...]` and `VIMSHOTTARI_YEARS: dict[Graha, int]` (spec §5.6); `TITHIS`, `YOGAS` (27, `vishkambha` … `vaidhriti`), `KARANAS_MOVABLE` (7), `KARANAS_FIXED` (`kimstughna, shakuni, chatushpada, naga`); `VAARS` (7 keys indexed by Python `weekday()`: `soma, mangala, budha, guru, shukra, shani, ravi`).
  - `models.py` (all `@dataclass(frozen=True, slots=True)`):
    - `Settings(ayanamsa: str = "LAHIRI", node: Literal["MEAN","TRUE"] = "MEAN", dasha_year_days: float = 365.25, sunrise: Literal["UPPER_LIMB_REFRACTED","CENTER_NO_REFRACTION"] = "UPPER_LIMB_REFRACTED")`
    - `BirthInput(local: datetime /*naive*/, tz: str, lat: float, lon: float, alt: float = 0.0, fold: int | None = None, name: str | None = None)`
    - `GrahaPosition(graha: Graha, lon: float, lat: float, speed: float, retro: bool)`
    - `EngineWarning(code: str, message: str)`
    - exceptions `EngineError(Exception)`, `InputError(EngineError)`, `EphemerisRangeError(InputError)`.
  - `angles.py`: `norm(deg: float) -> float` (returns [0, 360), and folds results ≥ 360 caused by float rounding back to 0); `sign_of(lon) -> int`; `deg_in_sign(lon) -> float`; `nak_of(lon) -> tuple[int, int]` (nakshatra 0–26, pada 1–4); `arc(a, b) -> float` (forward distance a→b in [0, 360)); `dms(deg) -> tuple[int, int, float]`.
  - `data/i18n.json`: `{key: {"en": ..., "hi": ...}}` for every rashi, nakshatra, graha, tithi, yoga and karana key.

- [ ] **Step 1: Write failing tests:** `test_vimshottari_years_sum_120`; `test_nakshatra_lords_cycle` (`ashwini→ketu`, `punarvasu→jupiter`, `revati→mercury`); `test_i18n_covers_all_keys` (every key in the tuples has non-empty `en` and `hi`); `test_wrap_and_edges` (`norm(360.0)==0`, `norm(-1e-12)==0` and the result is < 360, `sign_of(359.9999999)==11`, `nak_of(359.9999999)==(26,4)`, `sign_of(29.999999999)==0`, `sign_of(30.0)==1`, `nak_of(40/3)==(1,1)`).
- [ ] **Step 2:** Run `uv run pytest tests/unit/test_constants.py tests/unit/test_angles.py -v` → FAIL (import errors).
- [ ] **Step 3:** Implement the modules. `sign_of`/`nak_of` must compute on `norm(lon)` and clamp the index to the maximum (11 or 26) to absorb float rounding.
- [ ] **Step 4:** Re-run → PASS. Run `uv run mypy --strict src/vedic_engine` → clean.
- [ ] **Step 5: Commit** `feat(engine): constants, models, angle helpers`.

---

### Task 3: Time conversion

**Files:** Create `src/vedic_engine/timeutil.py`; Test `tests/unit/test_timeutil.py`

**Interfaces:**
- Consumes: `InputError` (Task 2).
- Produces: `to_utc(local: datetime, tz: str, fold: int | None = None) -> datetime` (aware, UTC); `jd_from_utc(dt: datetime) -> float` (UT Julian day via `swe.julday` with fractional hour); `utc_from_jd(jd: float) -> datetime`; `to_local(dt_utc: datetime, tz: str) -> datetime`. Exceptions: `NonexistentTimeError(InputError)`, `AmbiguousTimeError(InputError)`, `UnknownTimezoneError(InputError)`.

- [ ] **Step 1: Write failing tests:**
  - `test_ist`: 2000-01-01 12:00 `Asia/Kolkata` → 06:30 UTC.
  - `test_india_war_time`: 1943-06-01 12:00 `Asia/Kolkata` → 05:30 UTC (+06:30).
  - `test_india_lmt`: 1850-01-01 12:00 `Asia/Kolkata` → offset +05:53:28 (tzdb LMT).
  - `test_nonexistent_and_ambiguous`: `America/New_York` 2021-03-14 02:30 raises `NonexistentTimeError`; 2021-11-07 01:30 with `fold=None` raises `AmbiguousTimeError`; with `fold=0` → 05:30 UTC, `fold=1` → 06:30 UTC.
  - `test_unknown_tz` raises `UnknownTimezoneError`.
  - `test_jd_roundtrip`: J2000 `2000-01-01 12:00 UTC` → `2451545.0`; the round trip is within 1 ms.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement with `zoneinfo`. Detect a nonexistent time by round-tripping (local → UTC → local differs). Detect an ambiguous time by comparing `fold=0` and `fold=1` offsets.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5: Commit** `feat(engine): civil time to UT/JD with DST safety`.

---

### Task 4: Ephemeris adapter + JPL Horizons golden check

**Files:**
- Create: `src/vedic_engine/ephemeris.py`, `scripts/build_golden_horizons.py`, `fixtures/golden/horizons/*.json`, `fixtures/golden/ayanamsa_iae.json`
- Test: `tests/unit/test_ephemeris.py`, `tests/golden/test_horizons.py`

**Interfaces:**
- Consumes: `Settings`, `Graha`, `GrahaPosition`, `EphemerisRangeError`, `norm`.
- Produces:
  - `init(ephe_path: Path) -> None` (calls `swe.set_ephe_path` and `swe.set_sid_mode(SIDM_LAHIRI)`; raises `EngineError` if any file is missing).
  - `JD_MIN = julday(1800,1,1)`, `JD_MAX = julday(2399,12,31,24)`; `check_range(jd) -> None`.
  - `ayanamsa(jd_ut: float, settings: Settings) -> float`.
  - `positions(jd_ut: float, settings: Settings) -> dict[Graha, GrahaPosition]` (all 9 grahas; Ketu = Rahu + 180 with the same speed; Rahu/Ketu `retro=True`).
  - `tropical_longitude(jd_ut: float, graha: Graha) -> float` (no sidereal flag; used only for the Horizons comparison).
  - `ascendant(jd_ut: float, lat: float, lon: float) -> float` (sidereal; `houses_ex(jd, lat, lon, b"W", FLG_SIDEREAL)[1][0]`).
  - `rise_set(jd_start: float, lat: float, lon: float, alt: float, body: Literal["sun","moon"], event: Literal["rise","set"], settings: Settings) -> float | None` (`None` when the body never rises or sets that day; uses `BIT_DISC_CENTER | BIT_NO_REFRACTION` for the `CENTER_NO_REFRACTION` setting).
  - `body_longitude(jd_ut: float, graha: Graha, settings: Settings) -> float` (a fast single-body call used by root-finders).
  - Module-level thread lock: every `swe.*` call is serialised, because pyswisseph keeps global state.

- [ ] **Step 1:** Write `scripts/build_golden_horizons.py` (marked `network`, run manually). It queries `https://ssd.jpl.nasa.gov/api/horizons.api` with `COMMAND` = 10/301/199/299/499/599/699, `CENTER='500@399'`, `EPHEM_TYPE='OBSERVER'`, `QUANTITIES='31'`, `TIME_TYPE='UT'`, `ANG_FORMAT='DEG'`, `TLIST=<jd>` for the 30 epochs listed in the script (1801, 1850, 1900, 1947-08-15, 1975, 2000-01-01 12:00, 2024, 2100, 2200, 2399, plus 20 spread with `random.Random(42)`). It writes one JSON per epoch: `{"jd_ut", "source": "JPL Horizons", "retrieved": ISO date, "lon": {graha: deg}}`. Run it once and commit the fixtures.
- [ ] **Step 2:** Create `ayanamsa_iae.json` with the Lahiri definition epoch `{"jd_ut": 2435553.5, "ayanamsa_deg": 23.250182778}`, plus at least 3 published Indian Astronomical Ephemeris / Rashtriya Panchang annual Lahiri values (from 2020 onwards), each with its source citation.
- [ ] **Step 3: Write failing tests:**
  - `test_horizons.py::test_tropical_longitudes_match_jpl` (parametrised over fixtures × 7 grahas): `abs(arc_diff) * 3600 <= PLANET_ARCSEC` (`MOON_ARCSEC` for the Moon).
  - `test_ayanamsa_matches_iae`: ≤ `AYANAMSA_ARCSEC`.
  - Unit tests: `test_sidereal_equals_tropical_minus_ayanamsa` (within 1e-6°); `test_ketu_opposite_rahu`; `test_true_vs_mean_node_differ` (difference < 2°); `test_retro_flag_from_speed` (Mercury at a known retrograde date, 2024-04-10 UTC, is `retro=True`); `test_out_of_range_raises` (JD for 1799-12-31 and 2400-01-02); `test_missing_ephe_fails_fast` (a tmp dir raises `EngineError`); `test_rise_set_polar_none` (Sun at lat 78.2, lon 15.6 on 2024-06-21 → rise is `None`).
- [ ] **Step 4:** Run `uv run pytest tests/unit/test_ephemeris.py tests/golden/test_horizons.py -v` → FAIL.
- [ ] **Step 5:** Implement. Call `swe.set_sid_mode` in `init` and re-assert it inside the lock before each sidereal call.
- [ ] **Step 6:** Run → PASS. If a Horizons comparison exceeds tolerance, stop and investigate (TT/UT handling, apparent vs true position). Never widen a tolerance.
- [ ] **Step 7: Commit** `feat(engine): Swiss Ephemeris adapter verified against JPL Horizons`.

---

### Task 5: Lagna, bhavas, panchang

**Files:** Create `lagna.py`, `panchang.py`, `fixtures/golden/drik/*.json`; Test `tests/unit/test_lagna.py`, `tests/unit/test_panchang.py`, `tests/property/test_panchang_props.py`, `tests/golden/test_drik.py`

**Interfaces:**
- Consumes: `ephemeris.positions`, `body_longitude`, `rise_set`, `ascendant`; `timeutil.*`; `angles.*`.
- Produces:
  - `lagna.bhava_rashis(asc_lon: float) -> tuple[int, ...]` (12 rashi indices, house 1 first); `lagna.house_of(rashi: int, lagna_rashi: int) -> int` (1–12).
  - `panchang.tithi(sun: float, moon: float) -> int` (1–30); `paksha(tithi: int) -> Literal["shukla","krishna"]`; `yoga(sun, moon) -> int` (1–27); `karana(sun, moon) -> int` (half-tithi index 0–59); `karana_key(k: int) -> str`.
  - `@dataclass Element(key: str, index: int, ends_utc: datetime)`; `@dataclass PanchangAt(tithi: Element, paksha: str, nakshatra: Element, pada: int, yoga: Element, karana: Element, vaar: str)`; `@dataclass DayPanchang(date: date, sunrise_utc, sunset_utc, moonrise_utc: datetime | None, moonset_utc: datetime | None, at_sunrise: PanchangAt)`.
  - `elements_at(jd_ut: float, lat: float, lon: float, alt: float, settings: Settings) -> PanchangAt`.
  - `day_panchang(day: date, tz: str, lat: float, lon: float, alt: float, settings: Settings) -> DayPanchang`.
  - `find_end(f: Callable[[float], float], jd: float, span_deg: float) -> float`: the JD at which the angular quantity f (degrees) next crosses a multiple of `span_deg`; bracket in 0.25-day steps, then bisect to 1 second.

- [ ] **Step 1:** Transcribe Drik Panchang for New Delhi (28.6139, 77.2090, `Asia/Kolkata`) for 10 dates (5 in 2024, 5 in 2025, including one Adhik-masa date and one date where a tithi is skipped/kshaya). For each date record sunrise, sunset, and tithi/nakshatra/yoga/karana names with end times, plus the retrieval date. Save to `fixtures/golden/drik/`.
- [ ] **Step 2: Write failing tests:**
  - `test_tithi_formula` (sun 10, moon 22 → 1; 10/190 → 16; 10/9.99 → 30).
  - `test_karana_fixed_and_movable` (k = 0 kimstughna, 1 bava, 7 vishti, 8 bava, 56 vishti, 57 shakuni, 59 naga).
  - `test_yoga_formula`.
  - `test_bhava_rashis_karka` (asc 95° → `(3,4,…,2)`).
  - `test_vaar_before_sunrise`: 2024-01-10 04:30 IST, Delhi, is a Wednesday by civil date, so the vaar is `"mangala"` (Tuesday).
  - Property tests: the half-tithi index k equals `2*tithi-2` or `2*tithi-1`; `find_end` result > `jd` and < `jd + 1.5` for the tithi.
  - Golden `test_drik_day`: sunrise/sunset within `TIME_MINUTES`; element keys exact; end times within `TIME_MINUTES`.
- [ ] **Step 3:** Run → FAIL.
- [ ] **Step 4:** Implement. Vaar = weekday of the most recent local sunrise ≤ the moment. Day panchang searches sunrise starting from local midnight.
- [ ] **Step 5:** Run → PASS.
- [ ] **Step 6: Commit** `feat(engine): lagna, bhavas, panchang with end times`.

---

### Task 6: Vargas

**Files:** Create `varga.py`; Test `tests/unit/test_varga.py`, `tests/property/test_varga_props.py`

**Interfaces:**
- Produces: `VARGAS: tuple[int, ...] = (1,2,3,4,7,9,10,12,16,20,24,27,30,40,45,60)`; `varga_sign(lon: float, n: int) -> int` (raises `ValueError` for an unsupported n); `varga_chart(lons: Mapping[str, float], n: int) -> dict[str, int]`.

- [ ] **Step 1: Write failing tests.** Table-driven, at least one case per row of the spec §5.4 table for each of: odd and even sign; movable, fixed and dual sign; and the first and last part. Examples:
  - D2: 5° Mesha → Simha(4); 20° Mesha → Karka(3); 5° Vrishabha → Karka; 20° Vrishabha → Simha.
  - D9: 0° Mesha → Mesha(0); Vrishabha is fixed, so it starts from the 9th: 1° Vrishabha → Makara(9), 4° Vrishabha → Kumbha(10); Mithuna is dual, so it starts from the 5th: 1° Mithuna → Tula(6).
  - D10: 1° Vrishabha (even) → 9th from Vrishabha = Makara(9).
  - D30: 3° Mesha → Mesha; 7° Mesha → Kumbha; 27° Vrishabha → Vrishchika.
  - D60: 0.25° Mesha → Mesha; 29.75° Mesha → Meena(11).
  - `test_varga_edges`: exactly 15.0° in D2 belongs to the upper part; 359.9999999 in every varga returns 0–11 without error.
  - Property: `varga_sign(lon, 1) == sign_of(lon)`; D9 equals `floor(lon/(10/3)) % 12`; D27 equals `floor(lon/(30/27)) % 12`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement as a dispatch table of small rule functions taking (s, d) and returning a sign. Compute the part index as `min(int(d / width), parts - 1)`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5: Commit** `feat(engine): Parashari vargas D1–D60`.

---

### Task 7: Dignity, relationships, combustion, avastha

**Files:** Create `dignity.py`, `avastha.py`; Test `tests/unit/test_dignity.py`, `tests/unit/test_avastha.py`

**Interfaces:**
- Produces:
  - `class Dignity(StrEnum)`: `EXALTED, DEBILITATED, MOOLATRIKONA, OWN, GREAT_FRIEND, FRIEND, NEUTRAL, ENEMY, GREAT_ENEMY`.
  - `dignity(graha: Graha, lon: float, positions: Mapping[Graha, float]) -> Dignity` (precedence per spec §5.5; the compound relationship uses the temporal relation from `positions`).
  - `natural_relation(a: Graha, b: Graha) -> Literal["friend","neutral","enemy"]` (BPHS Ch 3 table).
  - `temporal_relation(a_sign: int, b_sign: int) -> Literal["friend","enemy"]` (b in the 2nd, 3rd, 4th, 10th, 11th or 12th from a → friend).
  - `is_combust(graha: Graha, lon: float, sun_lon: float, retro: bool) -> bool` (orbs per spec §5.2; Sun, Rahu and Ketu → False).
  - `NODE_DIGNITY_SCHOOL = {"rahu": {"exalted": 1}, "ketu": {"exalted": 7}}` (school dependent).
  - `avastha.baladi(lon: float) -> Literal["bala","kumara","yuva","vriddha","mrita"]`.

- [ ] **Step 1: Write failing tests:**
  - Exaltation and debilitation for all 7 planets at their exact points.
  - Moon at Vrishabha 2.9° → EXALTED, 3.0° → MOOLATRIKONA.
  - Mercury at Kanya 15.0° → MOOLATRIKONA, 21° → OWN.
  - Sun at Simha 25° → OWN.
  - Natural relations: Sun–Moon friend, Sun–Saturn enemy, Mercury–Moon enemy (from Mercury's side), Moon–Mercury friend (from the Moon's side). This asymmetry must hold.
  - Combustion: Mercury 13° from the Sun, direct → True; retro → False.
  - Baladi: 13° Mesha → yuva; 13° Vrishabha → yuva; 2° Vrishabha → mrita; 29° Mesha → mrita.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5: Commit** `feat(engine): dignity, relationships, combustion, baladi avastha`.

---

### Task 8: Vimshottari and Yogini dashas

**Files:** Create `dasha/__init__.py`, `dasha/vimshottari.py`, `dasha/yogini.py`; Test `tests/unit/test_vimshottari.py`, `tests/unit/test_yogini.py`, `tests/property/test_dasha_props.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) DashaPeriod(lord: str, level: int, start_utc: datetime, end_utc: datetime, children: tuple["DashaPeriod", ...] = ())`.
  - `vimshottari(moon_lon: float, birth_utc: datetime, settings: Settings, depth: int = 3) -> tuple[DashaPeriod, ...]`: the maha periods from birth to birth + the remaining part of the 120-year cycle, plus the full cycle following it (so the list covers at least 120 years). The first maha starts at birth with the balance length. Its children are the sub-periods that would have elapsed before birth, clipped to start at birth.
  - `subtree(period: DashaPeriod, settings: Settings, depth: int) -> DashaPeriod`: expands the children of an arbitrary period (used by `/dasha`); depth ≤ 5.
  - `balance(moon_lon: float) -> tuple[Graha, float]` (lord and remaining years).
  - `yogini(moon_lon, birth_utc, settings, depth: int = 3) -> tuple[DashaPeriod, ...]` (lords are the yogini keys `mangala` … `sankata`; years 1–8; start rule from spec §5.6).

- [ ] **Step 1: Write failing tests:**
  - `test_balance_mid_punarvasu`: Moon at Mithuna 26°40′ (lon 86.6667, halfway through Punarvasu) → `(JUPITER, 8.0)`.
  - `test_first_antar_is_own_lord`.
  - `test_antar_length`: the Jupiter–Saturn antar = 16 × 19 / 120 years.
  - `test_depth_5_levels` (prana level exists, and prana periods sum to their parent within 1 second).
  - `test_balance_near_zero`: Moon at `40/3 - 1e-9` → there is no period with end ≤ start, and the next maha lord follows the order.
  - `test_yogini_ashwini_starts_bhramari`.
  - `test_yogini_cycle_36`.
  - Property tests: for random moon_lon, children sum exactly to their parent (within 1 s) at each level; the total span of 9 consecutive mahas after the first equals 120 years × `dasha_year_days`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement with durations in days as `float` and `timedelta(days=…)`. Clip pre-birth children by intersecting each child interval with `[birth, ∞)` and dropping empty intervals.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5: Commit** `feat(engine): Vimshottari 5-level and Yogini dashas`.

---

### Task 9: Transits and doshas

**Files:** Create `transit.py`, `doshas.py`; Test `tests/unit/test_transit.py`, `tests/unit/test_doshas.py`

**Interfaces:**
- Consumes: `ephemeris.body_longitude`, `ephemeris.JD_MAX`, `lagna.house_of`, `angles.arc`.
- Produces:
  - `transit.sign_ingresses(graha: Graha, jd_start: float, jd_end: float, settings: Settings) -> list[tuple[float, int]]` (JD of each sign change and the new sign, including retrograde re-entries; 1-day scan, then bisect to 1 minute).
  - `transit.positions_at(dt_utc: datetime, settings: Settings) -> dict[Graha, GrahaPosition]`.
  - `@dataclass ManglikResult(from_lagna: bool, from_moon: bool, from_venus: bool, level: Literal["none","low","medium","high"])`; `manglik(mars_lon: float, lagna_lon: float, moon_lon: float, venus_lon: float) -> ManglikResult`.
  - `@dataclass KaalSarpaResult(kind: Literal["full","partial"], name: str, outside: tuple[Graha, ...])`; `kaal_sarpa(positions: Mapping[Graha, float], lagna_lon: float) -> KaalSarpaResult | None`. Names by Rahu's house 1–12: `anant, kulik, vasuki, shankhpal, padma, mahapadma, takshak, karkotak, shankhachud, ghatak, vishdhar, sheshnag`.
  - `@dataclass SaturnPhase(kind: Literal["sade_sati_rising","sade_sati_peak","sade_sati_setting","dhaiya_4th","dhaiya_8th"], start_utc: datetime, end_utc: datetime)`; `sade_sati(natal_moon_lon: float, birth_jd: float, settings: Settings, years: int = 100) -> tuple[tuple[SaturnPhase, ...], tuple[EngineWarning, ...]]`.

- [ ] **Step 1: Write failing tests:**
  - Manglik: Mars in the 7th from the lagna only → level `low`; in the 1st from all three references → `high`; in the 3rd → `none`.
  - Kaal Sarpa: all seven planets within Rahu→Ketu → `full`; one outside → `partial`; two outside → `None`; a planet exactly on the node axis counts as outside.
  - `test_saturn_ingress_known`: Saturn's sidereal ingress into Kumbha in 2023 falls on 2023-01-17 UTC (±1 day), and the 2022 re-entry into Makara (July) is detected.
  - `test_sade_sati_phases_ordered` (rising → peak → setting; no overlaps; phases may repeat on retrograde re-entries).
  - `test_sade_sati_clamped_to_range`: birth in 2350 returns phases ending ≤ `JD_MAX` and a `EngineWarning(code="range_clamped")`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5: Commit** `feat(engine): transits, Manglik, Kaal Sarpa, Sade Sati`.

---

### Task 10: Ashtakavarga

**Files:** Create `ashtakavarga.py`, `data/ashtakavarga_bphs.json`; Test `tests/unit/test_ashtakavarga.py`, `tests/property/test_ashtakavarga_props.py`

**Interfaces:**
- Produces: `bav(signs: Mapping[str, int]) -> dict[Graha, tuple[int, ...]]` (`signs` keys: the 7 graha values plus `"lagna"`; each value is a 12-tuple of bindus by rashi); `sav(bav_table) -> tuple[int, ...]`.

- [ ] **Step 1:** Transcribe the BPHS Ch 66 benefic-place tables (Santhanam translation) into `ashtakavarga_bphs.json` as `{target_graha: {contributor: [houses 1-12]}}`, citing the page for each target.
- [ ] **Step 2: Write failing tests:**
  - `test_contributor_counts`: the Sun's BAV contributor counts are Sun 8, Moon 4, Mars 8, Mercury 7, Jupiter 4, Venus 3, Saturn 8, Lagna 6.
  - `test_bav_totals` (per-planet sums 48, 49, 39, 54, 56, 52, 39).
  - Property `test_sav_337` (any random sign assignment → SAV sums to 337).
  - `test_bphs_example` (a worked example chart from the same chapter matches its printed BAV rows exactly).
- [ ] **Step 3:** Run → FAIL. **Step 4:** Implement. **Step 5:** Run → PASS.
- [ ] **Step 6: Commit** `feat(engine): Ashtakavarga BAV/SAV`.

---

### Task 11: Shadbala

**Files:** Create `shadbala.py`, `fixtures/golden/shadbala_bphs_example.json`; Test `tests/unit/test_shadbala.py`, `tests/golden/test_shadbala_example.py`

**Interfaces:**
- Consumes: positions (sidereal), `ascendant`, sunrise/sunset JDs (from `ephemeris.rise_set`), birth JD, `varga_sign`, `dignity` relations.
- Produces: `@dataclass ShadbalaRow(sthana: float, dig: float, kaala: float, cheshta: float, naisargika: float, drik: float, total_virupa: float, total_rupa: float, required_rupa: float, ratio: float, components: dict[str, float])`; `shadbala(jd_ut: float, lat: float, lon: float, settings: Settings) -> dict[Graha, ShadbalaRow]` (Sun to Saturn only).

- [ ] **Step 1:** Transcribe the BPHS Ch 27 worked-example chart (Santhanam) with its input positions and printed component values into the fixture, with page references. Use the printed positions as inputs so the test checks formulas, not the ephemeris.
- [ ] **Step 2: Write failing tests:**
  - `test_naisargika_constants` (Sun 60.0, Moon 51.43, Venus 42.86, Jupiter 34.29, Mercury 25.71, Mars 17.14, Saturn 8.57 virupa).
  - `test_uchcha_bala_exalted_is_60` and `_debilitated_is_0`.
  - `test_dig_bala_max`: Jupiter/Mercury on the ascendant degree → 60; Sun/Mars on the 10th cusp → 60.
  - `test_required_rupa` (Sun 6.5, Moon 6, Mars 5, Mercury 7, Jupiter 6.5, Venus 5.5, Saturn 5).
  - Golden `test_bphs_example_components`: every component within `SHADBALA_VIRUPA`.
- [ ] **Step 3:** Run → FAIL.
- [ ] **Step 4:** Implement one private function per component (`_uchcha`, `_saptavargaja`, `_ojhayugma`, `_kendradi`, `_drekkana`, `_dig`, `_natonnata`, `_paksha`, `_tribhaga`, `_abda`, `_masa`, `_vara`, `_hora`, `_ayana`, `_yuddha`, `_cheshta`, `_drik`). Each one cites its BPHS shloka in its docstring.
- [ ] **Step 5:** Run → PASS. If a component misses tolerance, use superpowers:systematic-debugging. Do not adjust the fixture.
- [ ] **Step 6: Commit** `feat(engine): Shadbala per BPHS Ch 27-28`.

---

### Task 12: Sensitivity, name syllables, kundli orchestrator, Shri Ram fixture

**Files:** Create `sensitivity.py`, `names.py`, `kundli.py`, `fixtures/golden/shri_ram.json`, `fixtures/golden/charts/*.json`; Test `tests/unit/test_names.py`, `tests/unit/test_sensitivity.py`, `tests/unit/test_kundli.py`, `tests/golden/test_shri_ram.py`, `tests/golden/test_charts.py`

**Interfaces:**
- Produces:
  - `names.syllable(nak: int, pada: int) -> tuple[str, str]` (Latin, Devanagari; 108-entry table).
  - `@dataclass SensitivityItem(item: str, minutes_before: float, minutes_after: float)`; `sensitivity(birth: BirthInput, settings: Settings) -> tuple[tuple[SensitivityItem, ...], tuple[EngineWarning, ...]]` (items: `lagna`, `moon_nakshatra_pada`, `d9_lagna`, `d10_lagna`; search ±120 min in 1-minute steps, then bisect; warning `birth_time_sensitive` if any value is within 5 min).
  - `@dataclass Kundli(meta: dict[str, Any], grahas: dict[Graha, GrahaPosition], lagna_lon: float, bhavas: tuple[int, ...], panchang: PanchangAt, vargas: dict[int, dict[str, int]], dignity: dict[Graha, Dignity], combust: dict[Graha, bool], avastha: dict[Graha, str], vimshottari: tuple[DashaPeriod, ...], yogini: tuple[DashaPeriod, ...], manglik: ManglikResult, kaal_sarpa: KaalSarpaResult | None, sade_sati: tuple[SaturnPhase, ...], shadbala: dict[Graha, ShadbalaRow], ashtakavarga: dict[str, Any], sensitivity: tuple[SensitivityItem, ...], name_syllable: tuple[str, str], warnings: tuple[EngineWarning, ...])`.
  - `build_kundli(birth: BirthInput, settings: Settings = Settings(), vargas: Sequence[int] = VARGAS, dasha_depth: int = 3) -> Kundli`.
  - `chart_from_placements(lagna_lon: float, lons: Mapping[Graha, float]) -> PartialKundli` where `@dataclass PartialKundli(dignity: dict[Graha, Dignity], vargas: dict[int, dict[str, int]], maha_lord: Graha, balance_years: float, nakshatra: int, pada: int, syllable: tuple[str, str])` (used by the Shri Ram fixture, which has no date).

- [ ] **Step 1:** Build ≥ 25 golden charts in `fixtures/golden/charts/`. Each has birth input, expected categorical values (lagna rashi, Moon nakshatra/pada, tithi, D9 lagna, first maha lord) and sidereal longitudes. Derive the longitudes from the Horizons tropical values minus the IAE-verified ayanamsa, and the lagna from an independent sidereal-time computation in the build script. Coverage must include: 1850–2030; southern hemisphere (Sydney, São Paulo); western longitudes (New York, Los Angeles); DST births; pre-1947 India (Calcutta 1900, Bombay 1943 war time); births between midnight and sunrise; and charts where the lagna or Moon is within 2′ of a boundary. Each fixture records `"source"` and `"verified_by"`.
- [ ] **Step 2:** Create `shri_ram.json` with fixed placements from spec §1:
  - Lagna: Karka 10°
  - Moon: Karka 1° (Punarvasu pada 4)
  - Jupiter: Karka 5°
  - Sun: Mesha 10°
  - Mars: Makara 28°
  - Venus: Meena 27°
  - Saturn: Tula 20°
  - Mercury: Vrishabha 15° (commonly cited; not asserted)
- [ ] **Step 3: Write failing tests:**
  - `test_syllables` (Punarvasu pada 4 → "Hi"; Chitra pada 3 → "Ra"; Ashwini pada 1 → "Chu").
  - `test_shri_ram`: exactly Sun, Mars, Jupiter, Venus and Saturn are EXALTED; Moon in Karka is OWN; Moon and Jupiter share a sign; the first maha lord is JUPITER with balance in (0, 4] years; the syllable is "Hi".
  - `test_charts` (parametrised): categorical values exact; longitudes within tolerance.
  - `test_sensitivity_flags_boundary_chart`.
  - `test_kundli_deterministic` (two builds serialised with sorted keys are identical).
  - `test_polar_warning` (lat 70 → `EngineWarning(code="polar_latitude")`).
  - `test_node_dignity_flagged` (when Rahu is exalted, a `school_dependent` warning is present).
- [ ] **Step 4:** Run → FAIL.
- [ ] **Step 5:** Implement `kundli.py` by composing the earlier tasks only. No new formulas here. Put `meta = {engine_version, settings, ayanamsa_deg, jd_ut, ephemeris_files}` in the result.
- [ ] **Step 6:** Run the full suite with `uv run pytest -n auto` → PASS.
- [ ] **Step 7: Commit** `feat(engine): kundli orchestrator, sensitivity, golden charts, Shri Ram fixture`.

---

### Task 13: FastAPI service and offline place search

**Files:** Create `src/api/main.py`, `src/api/schemas.py`, `src/api/places.py`, `scripts/build_cities.py`, `data/cities.tsv`; Test `tests/unit/test_api.py`, `tests/unit/test_places.py`

**Interfaces:**
- Consumes: `build_kundli`, `day_panchang`, `subtree`, `transit.positions_at`, `ephemeris.init`.
- Produces the HTTP API in spec §6.
  - Request schemas: `KundliRequest {date: "YYYY-MM-DD", time: "HH:MM[:SS]", tz, lat ∈ [-90,90], lon ∈ [-180,180], alt=0, fold?, name?, settings?, vargas?, dasha_depth ∈ [1,5] = 3}`; `PanchangRequest {date, tz, lat, lon, alt}`; `DashaRequest {kundli: KundliRequest, path: list[str], depth ∈ [1,5]}`; `TransitRequest {datetime_utc, natal?: KundliRequest}`.
  - Responses: 1-based indices plus keys (`{"rashi": 4, "rashi_key": "karka"}`), degrees as floats plus a `dms` string.
  - `places.search(q: str, limit: int = 10) -> list[Place]` with `Place(name, admin1, country, lat, lon, tz, population)`; case- and diacritic-insensitive prefix match, ranked by population.

- [ ] **Step 1:** `build_cities.py` downloads GeoNames `cities15000.zip` (marked `network`), keeps name/asciiname/admin1/country/lat/lon/population/timezone, and writes `data/cities.tsv`. Run it once and commit the file. Add the attribution to NOTICE.md.
- [ ] **Step 2: Write failing tests** (with FastAPI `TestClient`):
  - `test_kundli_ok` (the golden chart 0 request → 200; lagna key matches the fixture).
  - `test_api_ambiguous_time_422` (New York 2021-11-07 01:30, no fold → 422 with `fold` named in the detail).
  - `test_out_of_range_422`.
  - `test_bad_tz_422`.
  - `test_lat_out_of_range_422`.
  - `test_panchang_ok`.
  - `test_dasha_subtree_depth5`.
  - `test_transit_ok`.
  - `test_places_varanasi` (`q="varan"` → first result Varanasi, tz `Asia/Kolkata`).
  - `test_places_accent_insensitive` (`"sao paulo"` finds São Paulo).
  - `test_health_reports_ephe`.
  - `test_openapi_snapshot` (the schema matches the committed `tests/snapshots/openapi.json`; regenerate it deliberately with `--update-snapshot`).
  - `test_response_deterministic`.
- [ ] **Step 3:** Run → FAIL.
- [ ] **Step 4:** Implement. Call `ephemeris.init` in the app lifespan; refuse to start if it raises. Map `InputError` → 422, any other `EngineError` → 500 with an error id. Never return a stack trace.
- [ ] **Step 5:** Run → PASS. Start the service with `uv run uvicorn api.main:app` and check `/docs` renders.
- [ ] **Step 6: Commit** `feat(api): FastAPI v1 endpoints and offline place search`.

---

### Task 14: Accuracy report, performance gate, Docker

**Files:** Create `scripts/accuracy_report.py`, `tests/perf/test_latency.py`, `Dockerfile`; Modify `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: all fixtures and `build_kundli`.
- Produces: `reports/accuracy.md` (one table row per quantity in spec §7: reference, n cases, max error, mean error, tolerance, PASS/FAIL); exit code 1 on any FAIL.

- [ ] **Step 1: Write failing test** `test_latency.py::test_p95_under_200ms` (marked `perf`): 200 random births 1900–2100 (`random.Random(7)`), default arguments, warm-up of 5 → P95 < `P95_MS`.
- [ ] **Step 2:** Run `uv run pytest -m perf -v`. If it fails, profile with `python -m cProfile` and optimise (the usual suspects are Sade Sati scanning and the sensitivity search). Never relax the threshold.
- [ ] **Step 3:** Implement `accuracy_report.py` and run `uv run python scripts/accuracy_report.py` → every row PASS.
- [ ] **Step 4:** Dockerfile: `python:3.12-slim`, copy `backend/`, `uv sync --frozen --no-dev`, run as a non-root user, `CMD uvicorn api.main:app --host 0.0.0.0 --port 8000`. Verify with `docker build -t vedic-astro-api . && docker run --rm -p 8000:8000 vedic-astro-api` and `curl localhost:8000/health` → `{"status":"ok",…}`.
- [ ] **Step 5:** CI: add `pytest -m perf` and the accuracy report step (failing the job on FAIL); upload `reports/accuracy.md`.
- [ ] **Step 6: Commit** `chore: accuracy report, latency gate, Docker image`.

---

## Phase 1 exit criteria (regression gate for later phases)
- `uv run pytest -n auto -m "not network"` is green: unit, property, golden and perf tests.
- `reports/accuracy.md` is all PASS against JPL Horizons, IAE ayanamsa, Drik Panchang and the BPHS worked examples.
- `docker run` serves `/api/v1/kundli` and `/docs`.
- Jagannath Hora exports, when supplied, drop into `fixtures/golden/jhora/` and run through `test_charts.py` with no code change.

---

## Amendment 2026-10-17 — engine additions for the UI PRD (ruling R27)

Execution order becomes **T12 → T15 → T16 → T13 → T14**. T13's request and response schemas include the T15 and T16 fields.

### Task 15: House facts (bhava table), drishti, karakas, vargottama

**Files:** Create `src/vedic_engine/bhava.py`, `src/vedic_engine/data/karakas.json`. Modify `kundli.py` (add `bhavas_detail: tuple[BhavaFact, ...]` and `vargottama: dict[Graha, bool]` to `Kundli`). Test: `tests/unit/test_bhava.py`.

**Interfaces:**
- Consumes: `RASHI_LORD`, `lagna.house_of`, `angles.sign_of`, `varga_sign`.
- Produces:
  - `drishti(graha: Graha, from_sign: int) -> tuple[int, ...]`: the signs aspected, using whole-sign Parashari graha drishti. Every graha aspects the 7th sign. Mars also aspects the 4th and 8th, Jupiter the 5th and 9th, Saturn the 3rd and 10th. Rahu and Ketu aspect nothing by default; `NODE_ASPECTS_SCHOOL = "none"` is a module constant, and the alternative "5-7-9" is behind a flag that is off by default.
  - `@dataclass(frozen=True) BhavaFact(house: int, rashi: int, lord: Graha, lord_house: int, occupants: tuple[Graha, ...], aspected_by: tuple[Graha, ...], karakas: tuple[Graha, ...])`.
  - `bhava_facts(lagna_lon: float, lons: Mapping[Graha, float]) -> tuple[BhavaFact, ...]` (12 entries).
  - `vargottama(lons) -> dict[Graha, bool]`, true when the D1 sign equals the D9 sign.
  - `karakas.json` holds the natural bhava-karaka table. Transcribe it from a cited source (BPHS Ch 32 or Phaladeepika, edition and page) under ruling R4, with no transcription from memory. Record any variant (e.g. the 10th-house karakas) in `_note`.

- [ ] **Step 1: Write failing tests:**
  - Mars in Mesha aspects (Karka, Tula, Vrishchika).
  - Jupiter in Mesha aspects (Simha, Tula, Dhanu).
  - Saturn in Mesha aspects (Mithuna, Tula, Makara).
  - Sun in Mesha aspects only Tula.
  - India 1947: house 1 = Vrishabha, lord Venus, lord_house 3, occupants (Rahu,). House 3's occupants are the 5 planets in Karka.
  - Vargottama is true exactly when `varga_sign(lon, 1) == varga_sign(lon, 9)`, checked with a property test.
  - Every house has ≥ 1 karaka, and the table matches the cited source literally.
- [ ] **Step 2:** Run FAIL, implement, run PASS. Wire the result into `build_kundli` and extend the determinism test.
- [ ] **Step 3: Commit** `feat(engine): house facts, graha drishti, karakas, vargottama`.

### Task 16: Ayanamsa selector and Chandra kundli (unknown birth time)

**Files:** Modify `models.py` (`Settings.ayanamsa: Literal["LAHIRI","RAMAN","KP","FAGAN_BRADLEY"]`, `BirthInput.time_known: bool = True`), `ephemeris.py` (map each to `swe.SIDM_LAHIRI`, `SIDM_RAMAN`, `SIDM_KRISHNAMURTI`, `SIDM_FAGAN_BRADLEY`, and re-assert the mode chosen by settings instead of hard-coded Lahiri), `kundli.py`. Tests: `tests/unit/test_ayanamsa_modes.py`, `tests/unit/test_chandra_kundli.py`.

**Interfaces:**
- `ephemeris.ayanamsa(jd, settings)`, `positions` and `ascendant` honour `settings.ayanamsa`. `ascendant` gains a `settings` parameter; update every caller.
- With `time_known=False`, `build_kundli`:
  - computes positions at **local noon** of the birth date;
  - sets the lagna to the Moon's longitude (Chandra lagna, so bhavas are counted from the Moon's sign);
  - omits time-dependent outputs (shadbala → `None`, sensitivity → `()`, panchang uses noon);
  - adds `EngineWarning("time_unknown", …)` and `EngineWarning("moon_nakshatra_uncertain", …)`. The second lists every nakshatra-pada the Moon occupies between local 00:00 and 23:59, and is added whenever that set has more than one entry;
  - still computes Vimshottari from the noon Moon and flags it as approximate in the warning text.
- `Kundli.meta["time_known"]` and `Kundli.meta["lagna_basis"]` (`"ascendant"` or `"moon"`).

- [ ] **Step 1: Write failing tests:**
  - Lahiri unchanged: all existing golden tests still pass.
  - At J2000: `ayanamsa(KP) − ayanamsa(LAHIRI)` is within the range implied by Swiss Ephemeris' documented constants. Compute the expected value in the test from those t0/ayan_t0 constants with linear precession, and record the source.
  - `RAMAN` and `FAGAN_BRADLEY` likewise.
  - Changing the ayanamsa changes sidereal longitudes by exactly the ayanamsa difference (within 1e-6°).
  - Chandra kundli for 1947-08-15 with time unknown: lagna sign = Karka (the Moon's sign), `meta.lagna_basis == "moon"`, shadbala is `None`, and the `time_unknown` warning is present.
  - A date when the Moon changes nakshatra during the day carries `moon_nakshatra_uncertain` listing both nakshatras.
- [ ] **Step 2:** Run FAIL, implement, run PASS. Run the full suite to confirm the Lahiri results are unchanged.
- [ ] **Step 3: Commit** `feat(engine): ayanamsa selector and Chandra kundli for unknown birth time`.

### T13 amendments

- `KundliRequest` gains `time_known: bool = true` (when false, `time` may be omitted) and `settings.ayanamsa` taking one of the four values.
- The response includes `bhavas_detail`, `vargottama` and `meta.lagna_basis`.
- Add API tests `test_kundli_time_unknown` and `test_kundli_ayanamsa_kp`.
