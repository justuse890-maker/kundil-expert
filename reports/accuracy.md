# Accuracy report

Generated 2026-10-17 by `backend/scripts/accuracy_report.py` (engine `0.1.0`). Tolerances are those of spec section 7 (`backend/tests/tolerances.py`).

| Quantity | Reference | n | Max error | Mean error | Tolerance | Result |
|---|---|---:|---:|---:|---:|---|
| Planet tropical longitude (Sun, Mars, Mercury, Jupiter, Venus, Saturn) | JPL Horizons DE441 (apparent, geocentric) | 180 | 0.1316 arcsec | 0.0853 arcsec | 1 arcsec | PASS |
| Moon tropical longitude | JPL Horizons DE441 (apparent, geocentric) | 30 | 0.4676 arcsec | 0.1121 arcsec | 2 arcsec | PASS |
| Lahiri true ayanamsa | Indian Astronomical Ephemeris (published values) | 9 | 0.1384 arcsec | 0.0323 arcsec | 1 arcsec | PASS |
| Sidereal planet longitude (golden charts, 6 planets) | Golden charts: Horizons minus IAE-verified Lahiri (Jagannath Hora exports pending) | 168 | 0.1445 arcsec | 0.0529 arcsec | 1 arcsec | PASS |
| Sidereal Moon longitude (golden charts) | Golden charts: Horizons minus IAE-verified Lahiri (Jagannath Hora exports pending) | 28 | 0.4302 arcsec | 0.1370 arcsec | 2 arcsec | PASS |
| Ascendant (lagna), sidereal | Independent Meeus sidereal-time computation (no Swiss Ephemeris) | 28 | 0.0134 arcmin | 0.0026 arcmin | 1 arcmin | PASS |
| Categorical values (7 per chart: lagna rashi, Moon nakshatra/pada, tithi, D9 lagna, first Maha lord) | Golden chart fixtures | 196 | 0 | 0 | exact | PASS |
| Varga signs, all 16 vargas x lagna and 7 grahas | Varga rules applied to the independent reference longitudes (checks the pipeline, not the rule tables; those are covered by unit tests) | 3584 | 0 | 0 | exact | PASS |
| Vimshottari Maha and Antar start dates (all periods in 120 years) | Independent formula from the reference Moon (nakshatra fraction, balance, cumulative years x dasha year of 365.25 d); JHora exports pending | 2699 | 0.0462 days | 0.0146 days | 1 days | PASS |
| Vimshottari Maha and Antar lord sequence | BPHS Vimshottari order and years | 2979 | 0 | 0 | exact | PASS |
| Bhinnashtakavarga bindus per rashi (Sun, Mars, Jupiter, Venus, Saturn) | BPHS (Santhanam) Vol. 2 worked example, Ch 66-72 | 60 | 0 | 0 | exact | PASS |
| Sarvashtakavarga total (337 for any chart) | BPHS (Santhanam) Vol. 2 worked example, Ch 66-72 | 1 | 0 | 0 | exact | PASS |
| Moon and Mercury rows: deviation from the printed row equals the documented one | BPHS (Santhanam) Vol. 2 worked example, Ch 66-72 (misprints, ruling R22, see below) | 24 | 0 | 0 | exact | PASS |
| Shadbala components (7 grahas) | B. V. Raman, Graha and Bhava Balas, worked example (printed inputs, formulas only) | 141 | 0.5257 virupa | 0.0257 virupa | 1 virupa | PASS |
| Shadbala rows carrying a documented book misprint (Mars, Saturn): deviation minus the documented one | B. V. Raman, Graha and Bhava Balas, worked example (printed inputs, formulas only) | 6 | 0.5648 virupa | 0.1319 virupa | 1 virupa | PASS |
| Sunrise and sunset (upper limb, refraction) | Drik Panchang, New Delhi (transcribed) | 22 | 0.5122 min | 0.2589 min | 1 min | PASS |
| Tithi end times (Drik Delta T convention, see note) | Drik Panchang, New Delhi (transcribed) | 12 | 0.6370 min | 0.3129 min | 1 min | PASS |
| Karana end times (Drik Delta T convention, see note) | Drik Panchang, New Delhi (transcribed) | 24 | 0.6370 min | 0.2916 min | 1 min | PASS |
| Nakshatra end times | Drik Panchang, New Delhi (transcribed) | 11 | 0.6253 min | 0.2913 min | 1 min | PASS |
| Yoga end times | Drik Panchang, New Delhi (transcribed) | 12 | 0.7748 min | 0.4475 min | 1 min | PASS |
| Panchang element sequence per day (key at each Drik row, open-ended rows) | Drik Panchang, New Delhi (transcribed) | 147 | 0 | 0 | exact | PASS |
| build_kundli latency, P95 over 200 random births 1900-2100 (default args) | Spec section 7 budget | 1 | 145.2589 ms | 145.2589 ms | < 200 ms | PASS |

* build_kundli latency, P95 over 200 random births 1900-2100 (default args): median 136.3 ms, max 592.9 ms; machine-dependent

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
  correction, is at most **96 s** (mean 63 s over 36 tithi/karana
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
