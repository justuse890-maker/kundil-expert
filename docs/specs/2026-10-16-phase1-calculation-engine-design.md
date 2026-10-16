# Phase 1 — Vedic Calculation Engine & API (Design Spec)

- **Date:** 2026-10-16
- **Source PRD:** "ACT Web App PRD v2.1 — 99% Accurate North Indian Kundli Engine" (sections 4, 6.2 doshas, 6.3, 7, 8)
- **Status:** Draft for review
- **Phase in programme:** 1 of 4 (1 Engine+API → 2 Web UI → 3 Accounts/Scale → 4 Pandit Prediction Engine)

## 1. Intent

Build the calculation core of a public, commercial Vedic astrology product. Every number the
product shows later (charts, dashas, doshas, predictions) is derived from this engine, so it
must be **provably correct against independent references**, deterministic, and fast.

Success for Phase 1 = the regression suite proves calculation accuracy within the tolerances in
§7, and a single API call returns a complete kundli in < 200 ms server-side.

### Decisions already taken
| Topic | Decision |
|---|---|
| Location | New repo `~/vedic-astro` (separate from LiveSync) |
| Ephemeris | pyswisseph (Swiss Ephemeris), Lahiri / Chitra Paksha ayanamsa |
| Licence | Backend released under **AGPL-3.0** (open source). Frontend/brand (Phase 2) stays proprietary and talks to the backend only over HTTP. |
| Audience | Public product (accounts, cache, scale arrive in Phase 3) |
| Ground truth | NASA JPL Horizons (planets), published Lahiri values (ayanamsa), Drik Panchang (tithi/nakshatra/sunrise times, transcribed manually), Jagannath Hora exports added later |
| Architecture | Pure Python engine library + thin FastAPI layer |

### What "99% accuracy" means in this programme
- **Calculation** (this phase): measured as max error vs references, per field, with hard tolerances (§7). This is the claim we can prove.
- **Prediction** (Phase 4): measured as % agreement with VedAstro tags and pandit review. Reported as a measured number, never asserted as 99%.

### Corrections to the PRD (found during review)
1. **Shri Ram chart has no exact date/time** (PRD §6.5 says "symbolic test, not exact JD"), so it cannot validate ephemeris accuracy. It becomes a **fixed-placement fixture** testing dignity, varga and dasha-lord logic. Accuracy is proven by dated golden charts instead.
2. **Shri Ram placements:** Valmiki Ramayana (Bala Kanda 18.8–9) gives Karka lagna, Moon in Punarvasu with Jupiter in Karka, and five exalted planets: **Sun (Mesha), Mars (Makara), Jupiter (Karka), Venus (Meena), Saturn (Tula)**. The PRD's "Chandra in Vrishabha" is inconsistent with Moon in Punarvasu (Punarvasu spans Mithuna 20°00′ – Karka 3°20′).
3. **Dasha balance:** Moon in Punarvasu **pada 4** (Karka 0°–3°20′) means 75–100 % of the nakshatra is traversed, so Jupiter mahadasha balance is **0–4 years**, not the PRD's 10 years. The fixture asserts the formula, not the PRD figure.
4. **Name syllable:** the standard avakahada table gives Punarvasu = Ke, Ko, Ha, Hi. "Ra" belongs to Chitra pada 3. The engine uses the standard table; the PRD's "Ra from Punarvasu" is not asserted.
5. **Avastha:** "5 planets in Yuva = exalted" is not a rule. Baladi avastha depends on degree within sign, independent of exaltation. Engine implements BPHS Baladi avastha as defined in §5.7.
6. **Ephemeris files:** the needed files are `sepl_18.se1`, `semo_18.se1`, `seas_18.se1` (1800–2399 CE). `seplm18` is the BCE file and is not shipped.
7. **Ascendant:** computed with sidereal flag; house system is irrelevant for the ascendant degree, houses are whole-sign (PRD §4.3 agrees).

## 2. Scope

### In scope (Phase 1)
- Time & place: local civil time + IANA timezone → UT/JD; offline place search.
- Ephemeris: 9 grahas (Su Mo Ma Me Ju Ve Sa Ra Ke), sidereal Lahiri, speed, retrograde, Mean/True node toggle (default Mean).
- Lagna (sidereal ascendant), whole-sign bhavas.
- Panchang at birth moment and for a civil day (sunrise, sunset, moonrise, element end-times).
- Vargas: D1, D2, D3, D4, D7, D9, D10, D12, D16, D20, D24, D27, D30, D40, D45, D60 (Parashari).
- Dignity (exalted/debilitated/moolatrikona/own/friend/neutral/enemy), combustion, Baladi avastha.
- Vimshottari dasha, 5 levels; Yogini dasha.
- Doshas: Manglik (from Lagna, Moon, Venus), Kaal Sarpa, Sade Sati periods across life.
- Shadbala (6 components) and Ashtakavarga (BAV + SAV).
- Transit positions for any date; nakshatra-pada name syllables.
- Birth-time sensitivity warnings.
- FastAPI service, OpenAPI docs, Docker image.
- Regression suite + accuracy report.

### Out of scope (later phases)
- UI, chart SVG, PDF, Hindi rendering → Phase 2 (engine returns language-neutral keys; Phase 2 localises).
- Accounts, saved kundlis, Redis, rate limiting, deploy at scale → Phase 3.
- Yogas (Raja, Dhana, Gaja Kesari …), predictions, psychology mapping, rule engine, Pandit panel, VedAstro validation → Phase 4.
- Manglik cancellation rules → Phase 4 (rule engine). Phase 1 reports raw presence only.
- Chara and Kaal Chakra dashas → Phase 4 or later.

## 3. Architecture

```
vedic-astro/
  LICENSE                      AGPL-3.0 (covers backend/)
  docs/specs/
  backend/
    pyproject.toml             Python 3.12, managed with uv
    ephe/                      sepl_18.se1 semo_18.se1 seas_18.se1
    data/cities.tsv            GeoNames cities15000 subset (CC-BY 4.0, attributed)
    src/vedic_engine/          PURE: no I/O except ephemeris files; no web, no DB
      constants.py             rashis, nakshatras, lords, vimshottari years, syllables
      models.py                frozen dataclasses / Pydantic models (shared types)
      timeutil.py              civil time + tz → UT, JD; ambiguity handling
      ephemeris.py             the ONLY module that imports swisseph
      lagna.py
      panchang.py
      varga.py
      dignity.py               dignity, combustion, relationships
      avastha.py
      dasha/vimshottari.py
      dasha/yogini.py
      doshas.py                manglik, kaal_sarpa, sade_sati
      shadbala.py
      ashtakavarga.py
      transit.py
      sensitivity.py
      kundli.py                orchestrator: build_kundli(BirthInput, Settings) -> Kundli
    src/api/
      main.py                  FastAPI app, routes, error mapping
      places.py                offline city search
    tests/
      unit/  property/  golden/  fixtures/  perf/
    fixtures/golden/*.json     reference charts with provenance
    scripts/
      build_golden_horizons.py fetch JPL Horizons values → fixtures (dev-time only)
      accuracy_report.py       writes reports/accuracy.md
```

**Boundaries.** `ephemeris.py` is the single adapter over Swiss Ephemeris; every other module
takes plain longitudes/JDs, so formulas are unit-testable without the C library. `kundli.py` is
the only orchestrator. The API layer does validation, serialisation and error mapping only.

**Determinism.** Same `BirthInput` + `Settings` ⇒ byte-identical JSON. `Settings` (ayanamsa,
node type, year length, sunrise definition) is part of the output so any result is reproducible.

## 4. Data flow

1. `BirthInput {date, time, tz (IANA), lat, lon, alt=0, name?}` and `Settings {ayanamsa="LAHIRI", node="MEAN", dasha_year_days=365.25, sunrise="UPPER_LIMB_REFRACTED"}`.
2. `timeutil.to_ut(...)` using `zoneinfo` (tzdb handles pre-1947 India: LMT, Bombay/Calcutta time, 1942–45 war time). A nonexistent or ambiguous local time is rejected unless `fold` is given.
3. `ephemeris.positions(jd_ut, settings)` → for each graha: sidereal longitude, latitude, speed, retrograde. Flags: `FLG_SWIEPH | FLG_SIDEREAL | FLG_SPEED`. Ketu = Rahu + 180°. Ayanamsa value is returned too.
4. `lagna.ascendant(jd_ut, lat, lon)` → sidereal ascendant via `houses_ex(..., flags=FLG_SIDEREAL)`; bhava n = rashi (lagna_rashi + n − 1) mod 12.
5. Derived modules consume positions: panchang, varga, dignity, avastha, dasha, doshas, shadbala, ashtakavarga, sensitivity.
6. `Kundli` returned with `meta {engine_version, settings, ayanamsa_deg, jd_ut, ephemeris_files}`.

## 5. Calculation definitions

All longitudes are sidereal degrees in [0, 360). Indices are 0-based internally and 1-based in the API.

### 5.1 Panchang
- **Tithi** = ⌊((Mo − Su) mod 360) / 12⌋ + 1 (1–30); 1–15 Shukla, 16–30 Krishna.
- **Nakshatra** = ⌊Mo / (40/3)⌋ (27); **pada** = ⌊(Mo mod 40/3) / (10/3)⌋ + 1.
- **Yoga** = ⌊((Su + Mo) mod 360) / (40/3)⌋ + 1 (27, Vishkambha…Vaidhriti).
- **Karana** (60 half-tithis, k = ⌊((Mo − Su) mod 360) / 6⌋): k = 0 Kimstughna; k = 1…56 movable cycle (Bava, Balava, Kaulava, Taitila, Gara, Vanija, Vishti) by (k − 1) mod 7; k = 57 Shakuni, 58 Chatushpada, 59 Naga.
- **Vaar**: Vedic weekday runs sunrise to sunrise. A birth before local sunrise belongs to the previous vaar.
- **End times**: each element's end time is found by root-finding (bracket + bisection to 1 s) on the angular function.
- **Sunrise/sunset**: `rise_trans` with upper limb + atmospheric refraction (Drik Panchang convention). The definition is a Setting.

### 5.2 Grahas
Sun–Saturn via `calc_ut`; Rahu via MEAN_NODE (default) or TRUE_NODE; Ketu opposite. Retrograde if speed < 0 (Rahu/Ketu always reported as retrograde by convention, flagged `node: true`). Combustion orbs (degrees from Sun): Mo 12, Ma 17, Me 14 (12 if retro), Ju 11, Ve 10 (8 if retro), Sa 15.

### 5.3 Lagna & bhavas
Whole sign: house 1 = lagna rashi in full. The API also returns the lagna degree and nakshatra.

### 5.4 Vargas (BPHS Ch 6, Parashari)
Let s = sign index 0–11, d = degree in sign, odd sign = s even index (Mesha = odd).
| Varga | Rule |
|---|---|
| D2 Hora | odd: d < 15 → Simha, else Karka; even: d < 15 → Karka, else Simha |
| D3 | part p = ⌊d/10⌋ → s + {0, 4, 8}[p] |
| D4 | p = ⌊d/7.5⌋ → s + {0, 3, 6, 9}[p] |
| D7 | p = ⌊d/(30/7)⌋; odd: s + p; even: s + 6 + p |
| D9 | ⌊lon / (10/3)⌋ mod 12 (≡ movable from itself, fixed from 9th, dual from 5th) |
| D10 | p = ⌊d/3⌋; odd: s + p; even: s + 8 + p |
| D12 | p = ⌊d/2.5⌋ → s + p |
| D16 | p = ⌊d/(30/16)⌋; movable from Mesha, fixed from Simha, dual from Dhanu |
| D20 | p = ⌊d/1.5⌋; movable from Mesha, fixed from Dhanu, dual from Simha |
| D24 | p = ⌊d/1.25⌋; odd from Simha, even from Karka |
| D27 | ⌊lon / (30/27)⌋ mod 12 (fire Mesha, earth Karka, air Tula, water Makara) |
| D30 | odd: 0–5 Mesha, 5–10 Kumbha, 10–18 Dhanu, 18–25 Mithuna, 25–30 Tula; even: 0–5 Vrishabha, 5–12 Kanya, 12–20 Meena, 20–25 Makara, 25–30 Vrishchika |
| D40 | p = ⌊d/0.75⌋; odd from Mesha, even from Tula |
| D45 | p = ⌊d/(2/3)⌋; movable from Mesha, fixed from Simha, dual from Dhanu |
| D60 | p = ⌊d/0.5⌋ → s + p |
All results mod 12. Varga lagna uses the same rule on the ascendant longitude. Boundary values (d exactly on a division) belong to the upper part, consistently.

### 5.5 Dignity
Exaltation points: Su Mesha 10°, Mo Vrishabha 3°, Ma Makara 28°, Me Kanya 15°, Ju Karka 5°, Ve Meena 27°, Sa Tula 20°; debilitation is the opposite point. Moolatrikona (half-open ranges in degrees within sign): Su Simha [0, 20), Mo Vrishabha [3, 30) — degrees below 3 count as exaltation, Ma Mesha [0, 12), Me Kanya [15, 20) — degrees below 15 count as exaltation, Ju Dhanu [0, 10), Ve Tula [0, 15), Sa Kumbha [0, 20). Precedence: exalted/debilitated > moolatrikona > own > relationship. Own signs per BPHS. Rahu/Ketu dignity is school-dependent and set in a configurable table (default: Rahu exalted Vrishabha, Ketu exalted Vrishchika), flagged `school_dependent: true`. Natural relationships per BPHS Ch 3; compound (panchadha) relationship adds temporal friendship.

### 5.6 Dasha
- **Vimshottari** order and years: Ke 7, Ve 20, Su 6, Mo 10, Ma 7, Ra 18, Ju 16, Sa 19, Me 17 (=120). Nakshatra n lord = order[n mod 9]. Balance = (1 − fraction of nakshatra traversed) × lord years. Sub-period length = parent length × sub-lord years / 120, starting from the parent's own lord. 5 levels (Maha, Antar, Pratyantar, Sookshma, Prana). Year length is a Setting (default 365.25 days); dates are returned in UT and in the input timezone.
- **Yogini**: Mangala 1 (Mo), Pingala 2 (Su), Dhanya 3 (Ju), Bhramari 4 (Ma), Bhadrika 5 (Me), Ulka 6 (Sa), Siddha 7 (Ve), Sankata 8 (Ra); cycle 36 years. Starting yogini = (nakshatra number(1-based) + 3) mod 8, with 0 → 8. Balance as for Vimshottari. 3 levels.

### 5.7 Baladi avastha
Odd signs: 0–6 Bala, 6–12 Kumara, 12–18 Yuva, 18–24 Vriddha, 24–30 Mrita. Even signs: reversed.

### 5.8 Doshas
- **Manglik**: Mars in houses 1, 2, 4, 7, 8, 12 counted from Lagna, Moon and Venus separately. Output per reference point plus overall level (none / low = 1 reference / medium = 2 / high = 3). No cancellations in Phase 1.
- **Kaal Sarpa**: all seven Su–Sa strictly within the arc travelling forward from Rahu to Ketu, or all within Ketu → Rahu. Output `full`, or `partial` if exactly one planet lies outside, with the type name from Rahu's house (Anant … Sheshnag, 12 types).
- **Sade Sati**: Saturn's sidereal transit through the 12th, 1st and 2nd signs from natal Moon sign. Engine searches Saturn sign ingresses from birth to birth + 100 years, including retrograde re-entries, and returns phases (rising/peak/setting) with start/end dates. Also returns Dhaiya/Kantaka (4th and 8th from Moon).

### 5.9 Shadbala (BPHS Ch 27–28)
Sthana (Uchcha, Saptavargaja, Ojhayugma, Kendradi, Drekkana), Dig, Kaala (Natonnata, Paksha, Tribhaga, Abda, Masa, Vara, Hora, Ayana, Yuddha), Cheshta, Naisargika, Drik. Results are in virupas and rupas, plus the ratio to BPHS minimum required strength. Verified against the worked example in BPHS (Santhanam translation) to ±1 virupa per component.

### 5.10 Ashtakavarga (BPHS Ch 66–72)
Bhinnashtakavarga for Su–Sa from 8 contributors (7 planets + Lagna) using BPHS bindu tables; Sarvashtakavarga = sum. Invariants: per-planet BAV totals are Su 48, Mo 49, Ma 39, Me 54, Ju 56, Ve 52, Sa 39; SAV total = 337.

### 5.11 Birth-time sensitivity (amended by ruling R28, 2026-10-17)
Items: lagna, Moon nakshatra/pada, tithi, D9 lagna, D10 lagna. For each item the engine reports the minutes until the value changes, backwards and forwards (search ±120 min), plus `edge_before`/`edge_after` flags when the search hit the supported range limit. No change in the window is reported as infinity in the engine and as null in the API.
The `birth_time_sensitive` warning fires when lagna, Moon nakshatra/pada or tithi changes within ±5 min, or when D9 or D10 lagna changes within ±1 min (inclusive). D9 and D10 change about every 13 minutes, so a ±5 min rule for them would flag almost every chart. Consumers use the structured `sensitive_items`, not the message text.

### 5.12 Name syllables
Standard 108-entry nakshatra-pada → syllable table (Devanagari + Latin).

## 6. API (v1)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/kundli` | Full kundli: meta, grahas, lagna, bhavas, panchang, vargas (requested list, default all), dignity, avastha, vimshottari (default depth 3, max 5), yogini, doshas, shadbala, ashtakavarga, sensitivity, warnings |
| POST | `/api/v1/panchang` | Panchang for a date + place: sunrise/sunset/moonrise, elements with end times |
| POST | `/api/v1/dasha` | Dasha subtree on demand (lord path + depth) |
| POST | `/api/v1/transit` | Graha positions at a datetime, optionally relative to a natal Moon/Lagna |
| GET | `/api/v1/places?q=` | Offline city search → name, country, lat, lon, IANA tz |
| GET | `/health`, `/version` | Liveness, engine and ephemeris versions |

Responses use stable machine keys (e.g. `"rashi": "karka"`, `"nakshatra": "punarvasu"`). Display names in Hindi and English live in a separate i18n table exported by the engine for Phase 2.

## 7. Accuracy targets & tolerances

| Quantity | Reference | Tolerance |
|---|---|---|
| Planet tropical longitude | JPL Horizons (apparent, geocentric) | ≤ 1″ (Moon ≤ 2″) |
| Lahiri ayanamsa | Published Indian Astronomical Ephemeris values | ≤ 1″ |
| Sidereal longitudes | Jagannath Hora exports (added later) | ≤ 1″ planets, ≤ 1′ lagna |
| Ascendant | Independent computation (sidereal time formula) + JHora | ≤ 1′ |
| Sunrise / sunset | Drik Panchang (transcribed) | ≤ 1 min |
| Tithi / nakshatra / yoga / karana end times | Drik Panchang | ≤ 1 min |
| Categorical values (rashi, nakshatra, pada, tithi, vargas, dasha lords) | Golden fixtures | exact |
| Dasha start dates | Formula + JHora (same year length) | ≤ 1 day for Maha/Antar |
| Ashtakavarga | BPHS invariants + worked example | exact |
| Shadbala | BPHS worked example | ≤ 1 virupa per component |
| Kundli latency | — | P95 < 200 ms server-side (depth-3 dasha, all vargas) |

## 8. Error handling
- Invalid input (bad tz, lat/lon out of range, nonexistent local time) → 422 with field-level messages.
- Ambiguous DST time → 422 asking for `fold` (0 = first, 1 = second occurrence).
- Date outside shipped ephemeris range (1800–2399 CE) → 422 with the supported range. No silent Moshier fallback.
- Missing ephemeris files at startup → service refuses to start (fail fast), `/health` reports why.
- Every `Kundli` carries `warnings[]` (birth-time sensitivity, polar latitude where houses are unreliable above ±66.5°, school-dependent node dignity).

## 9. Testing strategy (regression)

1. **Unit tests**: one per formula row in §5, including boundary degrees (0°, 29.9999°, exact division edges) and every varga for every sign parity/modality.
2. **Property tests** (Hypothesis): nakshatra spans 13°20′; tithi/karana consistency (karana index = 2·tithi − 2 or 2·tithi − 1); Vimshottari sub-periods sum exactly to the parent; full cycle = 120 y; D9 of a longitude is idempotent with the continuous formula; SAV = 337 for any chart; Ketu = Rahu + 180°.
3. **Golden charts** (≥ 25, stored as JSON with source + retrieval date): mix of years 1850–2030, both hemispheres, east/west longitudes, DST zones, pre-1947 India, midnight and pre-sunrise births, lagna/nakshatra within 2′ of a boundary.
4. **Shri Ram fixture** (fixed placements, §1 corrections): asserts 5 exalted planets, Moon + Jupiter in Karka, Jupiter mahadasha at birth, balance in (0, 4] years, Punarvasu pada 4 syllable = "Hi".
5. **API contract tests**: schema snapshot; determinism (same input ⇒ identical JSON).
6. **Performance test**: 200 random charts, P95 < 200 ms.
7. **Accuracy report**: `scripts/accuracy_report.py` writes `reports/accuracy.md` with max/mean error per quantity vs each reference. CI fails if any tolerance is exceeded.

Every later phase re-runs this whole suite; it is the regression gate.

## 10. Tooling & delivery
- Python 3.12 via `uv`; `ruff` + `mypy --strict` on `vedic_engine`; `pytest`, `hypothesis`.
- Dockerfile (python:3.12-slim with ephemeris files baked in).
- GitHub Actions CI: lint, types, tests, accuracy report artifact.
- Attribution file for GeoNames (CC-BY 4.0) and Swiss Ephemeris (AGPL).

## 11. Open items (do not block Phase 1)
- Jagannath Hora exports: user/pandit to provide later; slot into `fixtures/golden/jhora/`.
- Default dasha year length (365.25 vs 365.2425 vs savana 360) to be confirmed against JHora exports; default 365.25 until then.
- Rahu/Ketu exaltation school: default as in §5.5, revisit with the Pandit team in Phase 4.
