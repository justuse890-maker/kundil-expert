# Unified Vedic Kundli App — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** One app in `/Users/nitesh/vedic kundil`. FastAPI serves the user's UI (`frontend/index.html`) and the API. All astronomy comes from the verified engine. A new rule-based analysis engine produces chart-specific, cited life guidance.

**Supersedes:** the Next.js Phase 2 plan (`docs/plans/2026-10-17-phase2-kundli-portal.md`). The user supplied the finished UI, and the Next.js scaffold is archived on branch `archive/phase2-nextjs`.

**Architecture:** `backend/src/vedic_engine` (pure engine) → `backend/src/vedic_engine/analysis/` (new, pure, consumes `Kundli`) → `backend/src/api` (FastAPI routes; also serves `frontend/` at `/`) → `frontend/index.html` (user's design; its JS astronomy is replaced by `fetch` calls).

## Global constraints
- Phase 1 global constraints still apply (`docs/plans/2026-10-16-phase1-calculation-engine.md`), as do every ruling R1–R32 in `.superpowers/sdd/2026-10-16-phase1-calculation-engine/progress.md`.
- Repo root is `/Users/nitesh/vedic kundil`; the path contains a space, so quote it. Branch `main`. Python commands run from `backend/` via `uv run`.
- **Analysis honesty:**
  - Every analysis statement carries `why` (the chart facts it rests on) and `ref` (a classical source: BPHS chapter, Phaladeepika chapter, or a named traditional association table).
  - Strength is a computed `score` with `factors` (how many classical indicators agree); predictions never say "99%".
  - Text is templated from data files (`analysis/data/*.json`), not hard-coded prose.
  - The UI shows the line: "Traditional Jyotish interpretation — guidance, not certainty."
- **No astronomy in the frontend.** After T5, `index.html` contains no planetary, ascendant, dasha or panchang maths.
- The UI keeps the user's visual design: same sections, colours, fonts and layout.

## Task order
T1 (= Phase 1 T16) → T2 (API) → T3 → T4 → T5 (analysis engine) → T6 (wire UI) → T7 (accuracy/perf/run script) → final review.

---

### Task 1: Ayanamsa selector, Chandra kundli, fixed UTC offset
Implement Phase 1 Task 16 exactly as written in `docs/plans/2026-10-16-phase1-calculation-engine.md` ("Task 16"), plus ruling R29:
- `BirthInput.tz` may also be a fixed offset `"UTC+05:53:20"` / `"UTC-04:00"`.
- Add `BirthInput.lmt: bool = False`, which uses the offset lon/15 h.
- Tests:
  - `to_utc(1900-01-01 12:00, "UTC+05:53:20")` gives 06:06:40 UTC.
  - LMT at lon 88.3639 (Calcutta) gives offset +05:53:27.3.
  - A malformed offset raises InputError.

### Task 2: FastAPI service (= Phase 1 T13, as amended), serving the frontend
Implement Phase 1 Task 13 as written, with its "T13 amendments", and rulings R30 (inf → null, plus edge flags) and R31 (`*_utc` and `*_local` ISO strings; degrees as unrounded floats plus dms strings). In addition:
- Mount `frontend/` with StaticFiles at `/`, so `GET /` returns index.html, and keep the API under `/api/v1`.
- `KundliRequest` accepts exactly one of `tz` (IANA), `utc_offset` ("+05:30") or `lmt: true`. Any other combination returns 422.
- Response JSON keys are snake_case, and enums use their value strings.
- Add `test_root_serves_frontend` (200, contains "Vedic Kundli").

### Task 3: Analysis core — functional nature, planet strength, dasha judgement
**Files:** `analysis/__init__.py`, `analysis/functional.py`, `analysis/strength.py`, `analysis/dasha_judgement.py`, `analysis/data/houses.json`, `analysis/data/grahas.json`; tests `tests/unit/test_analysis_core.py`.

**Interfaces:**
- `functional_roles(lagna_sign: int) -> dict[Graha, Role]`, where `Role` is a StrEnum: YOGAKARAKA, BENEFIC, MALEFIC, NEUTRAL, MARAKA. Rules (BPHS Ch 34, "Yoga Karakas"):
  - Lords of trikonas 5 and 9 are benefic.
  - Lords of 3, 6 and 11 are malefic.
  - The lord of 8 is malefic unless it is also the lagna lord.
  - A natural benefic (Ju, Ve, Me, waxing Mo) that owns a kendra loses beneficence and becomes NEUTRAL (kendradhipati dosha).
  - A natural malefic owning a kendra becomes NEUTRAL.
  - A planet owning both a kendra and a trikona is YOGAKARAKA.
  - Lords of 2 and 7 are MARAKA, which is additional to the role above: return both roles in a `roles` tuple.
  - The lagna lord is always BENEFIC.
  - Rahu and Ketu are NEUTRAL, with a `node_note`.
  - Cite each rule's verse in `grahas.json`.
- `planet_strength(k: Kundli, g: Graha) -> Strength(score: int /*0-100*/, factors: tuple[Factor,...])`. Factors and weights are documented in the module:
  - dignity: exalted +25, moolatrikona +20, own +15, great friend +10, friend +5, enemy −5, great enemy −10, debilitated −20;
  - Shadbala ratio ≥ 1: +15, otherwise −10;
  - combust −15;
  - house: kendra or trikona +10; 6/8/12 −10;
  - vargottama +10;
  - D9 dignity exalted or own +10, debilitated −10.
  Start at 50 and clamp to 0–100. Each `Factor` carries `name`, `delta` and `ref`.
- `judge_period(k: Kundli, lords: tuple[Graha, ...]) -> PeriodJudgement(score: int /*-100..100*/, nature: "favourable"|"mixed"|"challenging", areas: tuple[int,...] /*houses activated*/, reasons: tuple[Reason,...])`.
  - **Activated areas:** the houses each lord rules and occupies.
  - **Score:** the functional role sets the base (yogakaraka +40, benefic +25, neutral 0, malefic −25, maraka −10 extra), scaled by strength: `(strength − 50) / 2`.
  - **For an antar pair:** the mutual position of the maha and antar lords counts. 6/8 or 2/12 from each other is −15; kendra or trikona from each other is +10. Source: BPHS Ch 46+ and Phaladeepika Ch 20.
  - **Nature thresholds:** above +20 is favourable; below −20 is challenging.
  - `houses.json` maps each house to its life areas in English and Hindi (e.g. 10: career, status, father's influence; 11: gains, income, network), cited to BPHS Ch 11 (Bhava results).

**Tests:**
- Karka lagna: Mars is YOGAKARAKA (lord of 5 and 10).
- Vrishabha lagna: Saturn is YOGAKARAKA (lord of 9 and 10).
- Mesha lagna: Mercury is MALEFIC (lord of 3 and 6).
- Mesha lagna: Venus is MARAKA (lord of 2 and 7).
- The Mesha lagna lord Mars is BENEFIC even though it also owns the 8th.
- Strength: an exalted, vargottama, kendra planet scores above 80, and a debilitated, combust, 8th-house planet scores below 20 (synthetic Kundli fixtures).
- `judge_period` for India 1947: the Saturn maha (Vrishabha lagna: Saturn yogakaraka, but combust in the 3rd) returns reasons listing yogakaraka, combust and the 3rd house, plus a deterministic score asserted literally.
- Every Reason has a non-empty `ref`.

### Task 4: Life areas, income sources, lucky elements
**Files:** `analysis/areas.py`, `analysis/data/{career.json, income.json, lucky.json, personality.json}`; tests `tests/unit/test_analysis_areas.py`.

**Interfaces:** `life_areas(k: Kundli) -> dict[str, AreaReading]` with keys `personality, career, income, marriage, health, wealth, children, education`.
`AreaReading(score: int, summary_key: str, statements: tuple[Statement,...])`, where `Statement(text_en: str, text_hi: str, why: tuple[str,...], ref: str)`.

- **Personality:**
  - lagna sign traits (element and modality);
  - lagna lord's house placement (e.g. lagna lord in 10th: self-identity through work);
  - Moon sign and nakshatra temperament;
  - Sun sign.
  Sources: BPHS Ch 12 (results of the lagna lord in houses) and Phaladeepika Ch 8–9.
- **Career:**
  - 10th lord: its sign, house and strength;
  - planets in the 10th;
  - the D10 lagna lord;
  - career fields from `career.json`, keyed by the 10th lord and planets in the 10th (traditional significations, cited);
  - 10th lord in house n (Phaladeepika Ch 15 / BPHS Ch 24 "lord of 10th in houses").
- **Income (major income sources):**
  - 2nd and 11th lords, with their houses and strength;
  - planets in the 2nd and 11th;
  - the 10th lord's house, which gives the source type (e.g. 10th lord in 7th: partnership or business; in 6th: service; in 11th: multiple income streams).
  Rank the sources by contributing planets' strength.
- **Marriage:**
  - 7th lord placement and strength;
  - Venus (for a male chart) or Jupiter (for a female chart), using the gender input;
  - the D9 7th lord;
  - Manglik level from the engine.
- **Health:** lagna lord strength, the 6th and 8th lords, planets in the 6th/8th/12th, and the Moon's strength.
- **Wealth:** 2nd, 11th, 9th and 5th lords, plus dhana combinations (any two of the lords of 1, 2, 5, 9 and 11 conjoined or in mutual aspect). BPHS Ch 41 (Dhana yogas).
- **Children:** the 5th lord and Jupiter.
- **Education:** the 4th and 5th lords and Mercury.
- **Lucky elements:** `lucky.json`, keyed by the lagna lord and the Moon-sign lord, with colour, gemstone, day, number, direction, deity and metal. Mark these as traditional associations and cite their source.
- Every statement's `why` lists concrete chart facts such as "10th lord Mercury in 11th (Karka)".

**Tests:**
- India 1947: the career `why` includes "10th lord Saturn"; the 10th from Vrishabha is Kumbha, lord Saturn.
- Income ranks are deterministic.
- All templates exist in both en and hi.
- No statement lacks `ref`.
- For synthetic charts, changing the 10th lord's house changes the income source type.

### Task 5: Timeline, today's guidance (colours, body language, decisions)
**Files:** `analysis/timeline.py`, `analysis/daily.py`, `analysis/data/{hora.json, transit.json, body_language.json, decisions.json}`; tests `tests/unit/test_analysis_timeline.py`.

**Interfaces:**
- `timeline(k, now_utc, months=24) -> tuple[TimelineItem,...]`. It contains every antar and pratyantar overlapping [now, now + 24 months], each judged with `judge_period`. Add transit overlays:
  - Saturn's sign from the Moon: Sade Sati and Dhaiya from the engine, plus Saturn gochara good in houses 3, 6 and 11 from the Moon;
  - Jupiter's sign from the Moon: good in 2, 5, 7, 9 and 11 (Phaladeepika Ch 26, Gochara).
  Use `transit.sign_ingresses` for exact dates. Output monthly ratings, plus `best_windows` and `challenging_windows` (top 3 of each, with reasons). Each item lists `areas` (life areas activated) and `advice_key`.
- `daily(k, date, tz, lat, lon) -> DailyGuidance`:
  - weekday lord (Vedic day from sunrise, via panchang `vaar`);
  - hora schedule: 24 planetary hours from sunrise, using day and night length from the engine's sunrise/sunset, in the Chaldean order Sa → Ju → Ma → Su → Ve → Me → Mo, with the first hora ruled by the vaar lord;
  - colours per hora lord from `hora.json` (Sun red/copper, Moon white/silver, Mars red/coral, Mercury green, Jupiter yellow/gold, Venus white/pastel/pink, Saturn black/dark blue), with the source cited;
  - `favourable_horas`: horas ruled by this chart's functional benefics and yogakaraka;
  - `avoid_horas`: horas ruled by functional malefics;
  - `colour_today` and `colour_avoid`;
  - `body_language`, from `body_language.json`, keyed by lagna sign element (fire, earth, air, water) and the current dasha lord (e.g. Saturn dasha: measured speech, punctuality; Mars: channel assertiveness, avoid aggression);
  - `decisions`, from `decisions.json`, by the current antar judgement and activated areas (good for: investments, marriage, career moves, travel; caution: …), each with `why`.

**Tests:**
- Hora sequence on a Sunday starts with Sun, then Venus, Mercury, Moon, Saturn, Jupiter, Mars.
- 24 horas cover sunrise to the next sunrise with no gaps.
- Timeline items are contiguous and sorted, and every item has `why` and `ref`.
- India 1947 at 2026-10-17: current maha Mars, antar Rahu (matches the engine's dasha).
- `best_windows` are deterministic.

### Task 6: Wire the UI to the API
**Files:** modify `frontend/index.html`; add `frontend/app.js` if splitting helps; tests `backend/tests/e2e/test_frontend.py` (Playwright Python, against the running API).

- Remove every client-side astronomy and analysis function: `getAyanamsa`, `toJD`, `sunLongitude`, `moonLongitude`, `planetLongitude`, `rahuLongitude`, `calcAscendant`, `computePositions`, `calcPanchang`, `calcVimshottariDasha`, `calcManglik`, `calcKaalSarpa`, `calcSadeSati`, `calcAshtakavarga`, and all the `get*Analysis` / `get*Guidance` functions.
- Replace them with `fetch('/api/v1/kundli')`, `fetch('/api/v1/analysis')` and `fetch('/api/v1/daily')`. Map responses to the existing render code, keeping the existing DOM and design.
- Add place search using `/api/v1/places`: typing a city auto-fills lat, lon and timezone (the IANA tz replaces the manual UTC offset select, which stays as an "advanced" fallback that sends `utc_offset`).
- Ayanamsa select sends `settings.ayanamsa`. Add a "Birth time unknown" checkbox that sends `time_known:false`.
- Show "why" chips and a source badge on each analysis statement, add the honesty line, and show the birth-time sensitivity banner when the API warns.
- Add loading and error states, and keep Hindi text where the API provides `text_hi` (EN/HI toggle).
- **E2E test:** start uvicorn and enter India 1947. Assert:
  - the lagna shows Vrishabha;
  - the Moon shows Pushya;
  - the first dasha shows Saturn;
  - the page contains no JS error;
  - a grep shows none of the removed function names remain in `frontend/`.

### Task 7: Accuracy report, performance, one-command run
- Phase 1 Task 14 as written (accuracy report, P95 latency), with Docker optional (ruling R5).
- Performance: `build_kundli` is ~0.4–0.6 s, 97% of it in the Sade Sati 1-day scan. Make the scan adaptive (Saturn moves at most about 0.13°/day: step 10 days when more than 2° from a sign boundary, then 1 day, then bisect) so P95 is under 200 ms. The existing Sade Sati tests must stay identical.
- `run.sh` at the repo root runs `cd backend && uv sync && uv run uvicorn api.main:app --port 8000`. A README section explains how to run and test.
- The full suite stays green.

## Exit criteria
- `./run.sh`, then open http://localhost:8000. Entering birth details shows the user's UI filled with engine-verified positions and cited, chart-specific analysis.
- Backend suite, E2E and accuracy report are all green. No astronomy remains in the frontend.
