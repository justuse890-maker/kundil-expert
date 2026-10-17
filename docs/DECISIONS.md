# Decisions made during the build

Every judgement call taken while building the engine and app, in the order made, with what it costs if wrong. Generated from the build ledgers on 2026-10-17.

## Engine (Phase 1)
- | T1 ↔ controller | T1 creates .gitignore; controller already committed .gitignore with `.superpowers/` | conflict → Ruling R1 |
- | T4 self | needs network for Horizons build script | Ruling R2 |
- | T5 self | Drik transcription requires web source | Ruling R3 |
- | T10 self | BPHS table transcription source | Ruling R4 |
- | T11 self | BPHS Shadbala worked example source | Ruling R4 |
- | T13 self | GeoNames network download | Ruling R2 |
- | T14 self | Docker may be unavailable locally | Ruling R5 |
- ## Rulings
- Ruling R1: T1 must keep `.superpowers/` in .gitignore when it writes the file — the SDD workspace must stay untracked — cost if wrong: workspace files committed (easy to remove).
- Ruling R2: network fetch scripts (Horizons, ephe files, GeoNames) are run once by the implementer; outputs committed — reproducibility over live fetch — cost if wrong: none, scripts remain.
- Ruling R3: if Drik Panchang pages cannot be fetched, implementer may use another named published panchang (e.g. Prokerala/ Rashtriya Panchang) and record the source per fixture; tolerance unchanged — cost if wrong: reference convention differs slightly (sunrise def), surfaced by test failure, not hidden.
- Ruling R4: BPHS tables/example: implementer must source from an accessible published BPHS translation (archive.org Santhanam preferred) or B.V. Raman "Graha and Bhava Balas" worked example for Shadbala, citing edition+page; transcribing from memory alone is NOT allowed; if no source reachable → BLOCKED — cost if wrong: weaker verification.
- Ruling R5: if Docker is not installed locally, T14 writes the Dockerfile and verifies it via CI only, noting it in the report — cost if wrong: image unverified until CI runs.
- Ruling R6: norm() folds values >= 360-1e-9 to 0 (needed so norm(-1e-12)==0) — 1e-9° (3.6 µas) is far below any tolerance — cost if wrong: none measurable.
- Ruling R7: zoneinfo must use the pinned tzdata package only (zoneinfo.reset_tzpath(to=()) in timeutil, or equivalent) — global constraint: same input => identical output across OS — cost if wrong: tzdata package lags OS by a release (we pin + update deliberately).
- Ruling R8: tests import tolerances via pytest `pythonpath = ["tests"]` (`from tolerances import ...`) — tests/ is not a package — cost if wrong: trivial import style change.
- Ruling R9 (T4 concern 3): supported range starts 1800-01-01 06:00 UT (sepl_18 light-time margin) instead of 0h — spec intent is "1800 onwards"; 6 hours lost — cost if wrong: births in first 6h of 1800 rejected.
- Ruling R10 (T4 concern 2): Jupiter/Saturn compared as system barycentres (Horizons 5/6), matching SE default — offset from body centre ≲0.05″ — cost if wrong: sub-tolerance bias, revisit if JHora exports disagree.
- Ruling R11 (T4 concern 5): spec says only ephemeris.py imports swisseph; timeutil's julday/revjul use violates it → to be fixed (pure-Python Gregorian JD in timeutil) — cost if wrong: none.
- Ruling R12 (T4 minors 4/5 → T5): Task 5 owns day bounds: sunrise search uses local midnight→next local midnight (handles 23/25h DST days); range check for rise_set should only reject instants actually outside the range; atemp choice (0 vs 10 °C) is a Settings-level decision to be stated & tested against Drik — carry into T5 dispatch.
- Ruling R13 (T5 c1): plan example tithi(10,22)→1 is wrong; spec formula governs (elongation 12° → tithi 2) — cost if wrong: none, spec formula is standard.
- Ruling R14 (T5 c2): DERIVED_MARGIN_DAYS=2.0 — derived end times/rise-set may read up to 2 days past JD_MAX (still SE files); inputs stay strict — cost if wrong: end-times on 2399-12-31 rely on file tail.
- Ruling R15 (T5 c3): Drik tithi/karana end times differ from JPL-correct engine by ≤96 s because Drik's Sun/Moon ≈ ours at UT+ΔT (ΔT double-count) and its ayanamsa ≈ +24.6″; golden test compares at Drik's convention (ΔT added for tithi/karana, documented, unfitted); the raw difference must be surfaced in the accuracy report (T14) and to the user — engine stays physically correct per JPL — cost if wrong: users comparing with Drik see up to ~1.5 min differences in tithi end; JHora exports will arbitrate.
- Ruling R16 (T5 c4/c5): Adhik date 2023-08-01 (no Adhik in 2024–25); moonrise/set not golden-tested (Drik ignores lunar parallax; spec tolerance covers sunrise/sunset only) — cost if wrong: moonrise unverified ±5 min.
- Ruling R17: Drik golden uses Drik's own Delhi coordinates (28.635556, 77.224444, 212 m) instead of plan's — like-with-like reference location — cost if wrong: none.
- Ruling R18 (T6): part index uses int(d/width + 1e-9) — float edges (D45 2/3) otherwise fall to lower part; 1e-9 part ≤ 3e-8° — cost if wrong: none measurable. D9/D27 raw-formula properties limited to lon ≤ 360−1e-6 due to R6 fold.
- Ruling R19 (T7): Moon at exactly 3° Vrishabha and Mercury at exactly 15° Kanya are MOOLATRIKONA (spec §5.5 half-open ranges override plan's 'exact points → EXALTED for all 7') — cost if wrong: two single-degree-point classifications.
- Ruling R20 (T8): dasha/_core.py added (shared DashaPeriod + subdivision) — avoids duplication between vimshottari/yogini — cost if wrong: one extra file.
- Ruling R21 (T10): Jupiter's own BAV includes houses 1 & 4 (Sanskrit + book's rekha chart; English v.53 omission) — total 56 per spec — cost if wrong: none (spec total).
- Ruling R22 (T10): Santhanam worked example — Su/Ma/Ju/Sa rows match exactly; printed Mo (sum 51), Me (sum 56), Ve (Leo/Virgo swap) contradict the book's own tables and invariants → pinned as documented known misprints in the test, not forced — cost if wrong: 3 rows lack an external example check (invariants still enforce totals).
- Ruling R22 amended: Venus 'misprint' withdrawn — was transcription error (venus.mars); Moon/Mercury pins to be recomputed after table fix.
- Ruling R23 (T10): where Santhanam's BPHS is internally inconsistent, use the standard Parashari table used by Jagannath Hora/B.V. Raman (PRD defines accuracy as matching JHora): venus.mars=[3,5,6,9,11,12] (book's own worked example p.892 agrees; verse/chart say 4), moon.jupiter=[1,4,7,8,10,11,12] (book's house table says 12; verse says 2). Record both text variants in JSON _note — cost if wrong: one bindu each in Venus/Moon BAV vs the BPHS verse reading; re-check against JHora exports when supplied.
- Ruling R24 (T10): Santhanam BPHS consistently gives Moon-from-Moon 9th (verse, rekha chart, house table; its example row fits it better), standard Raman/JHora gives Mars 9th. Kept JHora/standard per R23 — USER MUST VERIFY against a real JHora export (Moon BAV row) — cost if wrong: 1 bindu moved between contributors for Moon BAV in some charts (Moon BAV row differs in 1–2 rashis).
- Ruling R25 (T11): Raman p.22 printed Saptavargaja for Mars (112.5) and Saturn (82.5) contradict the book's own rules (Mars trimsamsa, Saturn saptamsa entries) → pinned as strict xfail + exact-gap test; all other components ≤1 virupa — cost if wrong: Mars/Saturn sthana bala unverified by external example (formula verified by rule).
- Ruling R26: T12 must call shadbala.shadbala_report (not shadbala()) so polar/range warnings reach Kundli.warnings.
- Ruling R27 (user choice 2026-10-17): add engine tasks before API — T15 house facts (bhava lords, lord placement, graha drishti incl. special aspects, karakas), T16 ayanamsa selector (Lahiri/Raman/KP/Fagan) + Chandra kundli for unknown birth time. Order: T12 → T15 → T16 → T13 → T14.
- Ruling R28 (T12 c1): birth_time_sensitive fires on 28/28 charts with spec §5.11 ±5 min for all items (D9/D10 lagna change every ~13 min) — warning becomes: D1 lagna or Moon nakshatra-pada or tithi within ±5 min, OR D9/D10 lagna within ±1 min. Sensitivity list keeps all items with minutes (UI shows them). Add `tithi` to sensitivity items — cost if wrong: fewer warnings; users still see minutes per item.
- Ruling R29 (T12 c4): tzdb Asia/Kolkata pre-1906 = Madras time, 1942–45 = war time; astrologers often record local time. T16 adds fixed-offset support in timeutil (`tz` may be "UTC+05:53:20"-style or `lmt=True` → offset = lon/15 h) and T13 exposes `utc_offset` / `lmt` alternatives to IANA tz — cost if wrong: extra input options only.
- Ruling R30 (T12 c5): sensitivity "no change within window" serialised as null in API (T13), not Infinity.
- Ruling R31 (from P2 review): T13 responses carry both *_utc and *_local (ISO with offset in the birth tz) for birth instant, dasha boundaries, panchang end/rise times; numeric degrees unrounded floats + dms strings (avoid 30.0 rounding).
- Ruling R32 (T15 c1): bhava karakas = union of BPHS (Santhanam p.325) and Phaladeepika (Ch XV sl.17 p.159), BPHS karaka first then additions in Graha order; JSON records per-karaka source so UI can show provenance — matches PRD's '10th karaka = Shani + Surya' and common practice — cost if wrong: extra karakas shown for houses 4/6/9/10.

## Unified app
- Ruling U1 (T1 c2): moon_nakshatra_uncertain fires only when the Moon's NAKSHATRA changes during the day (pada list still included in the message/data) — pada changes every ~6h so per-pada rule always fires — cost if wrong: fewer warnings. U2 (c3): nonexistent local noon (DST gap at 12:00) → use 13:00 local, note it.
- Ruling U3 (T3 c1–c5): accept FunctionalRole(.role,.roles) + moon_is_waxing; Sun/Moon exempt from 8th-lordship evil (BPHS Ch34 vv2–7, Phaladeepika Ch20 v41); lagna lord never maraka; multi-lord score = mean + pairwise mutual-position terms (document in module); private _EXALT_SIGN import → make public in dignity.py (tiny engine change allowed).
- Ruling U4 (T3 c6): add moolatrikona precedence — when a planet owns a trikona/kendra AND a dusthana (6/8/12) or 3/11, the house of its moolatrikona sign dominates its functional role (e.g. Saturn for Kanya: MT Kumbha = 6th → leans MALEFIC with a note "also 5th lord"). Nodes yogakaraka-by-association and Mercury-by-association stay deferred (documented).
- Ruling U5 (T3 review I1/I2, supersedes U4): functional roles come from BPHS Ch 34's explicit per-lagna lists (benefics, malefics, yogakaraka, maraka for each of 12 lagnas), transcribed from the Santhanam scan with verse/page per lagna. The generic rules stay only to generate `why` text (houses owned, kendradhipati, MT) and a test reports where rules and table differ. Table wins, incl. lagna-lord cases (e.g. Mars for Vrishchika) — cost if wrong: roles differ from other modern tables for a few lagnas; source is cited.
- Ruling U6 (T2): revert dev dep httpx2 → httpx (official Starlette TestClient dependency); silence the deprecation via pytest filterwarnings. Unverified package names are not added — supply-chain caution — cost if wrong: one filtered warning.
- Ruling U7 (T2): wrong method on real API path → JSON 404 (not 405) accepted — cost: slightly less precise status.
- Ruling U8 (T4): accept areas.json (5th data file); lagna-lord-in-houses = BPHS Ch 24 vv1–12 (not Ch 12); 10th lord in houses = BPHS Ch 24 vv109–120 + Phaladeepika Ch 5; dhana combination cited as later tradition (chapter-level); income-type & modern career tables labelled "interpretive"; Kuja dosha as later tradition. lagna_is_moon arrives at merge.
- Ruling U9 (T4 I2): one income source per planet; type from highest-priority role 10th>11th>2nd>occupant>foreign; ties by role priority then Graha order.
- Ruling U10: T5 also replaces the 501 placeholders: POST /api/v1/analysis and /api/v1/daily on feat/analysis (shapes per T6a contract in task-6 dispatch).
- Ruling U11: /daily body = /kundli body + today (YYYY-MM-DD) + optional current_lat/current_lon/current_tz.
- Ruling U12 (T5 c1–c5): accept Timeline object, calendar-month windows, interpretive transit weights (label them), vargas ignored by /analysis. Response size: timeline items carry top 3 reasons by |delta| unless `detail: "full"` in the body; target < 80 KB for India 1947.
- Ruling U13 (T5 fix c1/c2): accept id-based reasons tables; size test budget becomes < 100 KB (80 KB was the target; 79.5 KB margin too thin to be stable) — not an accuracy tolerance — cost: slightly larger responses allowed.
- Controller walkthrough (live app, India 1947): kundli correct (Vrishabha 7°44′, Karka Moon, Pushya, Hu, Mars MD, houses). Polish needed → Ruling U14: (a) user-facing text must not show internal debug strings ("(65 - 50) / 2", "lordship rule: ... -> neutral; decided by: bphs_lagna") — keep them under a collapsible "Details" per statement; (b) capitalise planet/sign names in why chips; (c) soften alarming wording ("maraka (death-inflicting)" → "maraka houses — traditionally sensitive for health; read with care"), en+hi; (d) income sources shown once (ranked list only, remove duplicate statements in the Income card or vice-versa); (e) capitalise income type labels.

## Open items for the owner
- R24 (OPEN): verify the Moon Ashtakavarga row (9th-house bindu) against a real Jagannath Hora export.
- Karaka union (R32): work in progress kept in `git stash`; karakas are currently BPHS-only.
- run.sh: `uv run --frozen` should also pass `--no-dev` (local runs install dev tools on first start; Render is unaffected).
- Moon-based (time-unknown) charts: the chart-centre caption still says '<Sign> Lagna'.
