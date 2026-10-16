# Phase 2 — Kundli Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public Next.js kundli website that renders the Phase 1 engine's real results (charts, planets, dashas, doshas, strength, panchang) in Hindi and English, with saved charts and a PDF report.

**Architecture:** `web/` is a Next.js App Router app. The browser talks only to a same-origin proxy route (`/api/engine/*`) that forwards to the FastAPI engine unchanged. Response types are generated from the backend OpenAPI snapshot. The web layer formats and visualises only and never computes astrology.

**Tech Stack:** Node 22 LTS, pnpm, Next.js 15 (App Router), React 19, TypeScript strict, Tailwind CSS 4, Zustand, next-intl, idb, @react-pdf/renderer, Serwist, openapi-typescript, Vitest + Testing Library, Playwright, @axe-core/playwright, Lighthouse CI.

**Spec:** `docs/specs/2026-10-17-phase2-kundli-portal-design.md`. Section numbers below refer to it.

**Prerequisite:** Phase 1 Task 13 (API) merged on the working branch, with `backend/tests/snapshots/openapi.json` present.

## Global Constraints

- **Honesty rule:** every astrological value shown comes from the API response. The web may format values (dms, dates, localisation) and group them for display (Sade Sati cycles), but must never compute positions, signs, dashas or doshas. Reviewers treat any astrology computation in `web/` as Critical.
- `web/` is proprietary, with `web/LICENSE` reading "All rights reserved". It communicates with the AGPL backend only over HTTP.
- TypeScript `strict: true` and `noUncheckedIndexedAccess: true`. eslint and `tsc --noEmit` must be clean.
- Locales are `en` and `hi`, both complete. Engine keys are displayed through `public/i18n/engine.json`, copied from `backend/src/vedic_engine/data/i18n.json` by `pnpm sync:i18n` (run in `prebuild` and `pretest`).
- Times are always shown in the birth place's IANA timezone, never the browser's, with the zone name visible.
- Layout works from 320 px wide. WCAG 2.1 AA. `prefers-reduced-motion` and `prefers-color-scheme` are respected. Colours exist only as CSS tokens.
- The person's name never goes to the API. Birth data is never put in analytics or logs.
- Engine base URL is the server-only env var `ENGINE_URL` (default `http://127.0.0.1:8000`).
- Fonts: Instrument Serif, Inter, Noto Sans Devanagari, Tiro Devanagari Hindi, IBM Plex Mono, all self-hosted via `next/font`.

## Review Focus

1. **Browser timezone differs from the birth timezone** (a New York visitor viewing a Delhi chart): every time must still be shown in Asia/Kolkata. → Task 13 `e2e: browser in America/New_York shows IST times`; Task 1 `formatInZone` unit tests.
2. **Hand-edited or stale URL query** (`/kundli?date=2023-02-30&lat=999`): the user gets the form with field errors, never a crash or blank page. → Task 4 `parseKundliQuery rejects invalid values`; Task 13 e2e `bad query shows form errors`.
3. **Devanagari in the PDF and long Hindi labels:** glyphs render (no tofu boxes) and the layout doesn't overflow at 320 px. → Task 11 `pdf hindi contains Devanagari lagna text`; Task 13 visual snapshot in `hi`.
4. **A saved chart from an older engine version:** opening it recomputes and marks it "updated"; it never shows stale numbers silently. → Task 10 `saved chart with old engine_version is recomputed`.
5. **Deep dasha expansion** (prana level, over 6,000 nodes if expanded fully): children load lazily per level and the page stays responsive. → Task 7 `expands only the clicked node via /dasha`.

## File map

```
web/LICENSE  web/package.json  web/next.config.ts  web/tsconfig.json  web/eslint.config.mjs
web/vitest.config.ts  web/playwright.config.ts  web/lighthouserc.json  web/Dockerfile
docker-compose.yml   .github/workflows/web.yml
web/scripts/{sync-i18n.mjs, gen-types.mjs}
web/app/[locale]/{layout.tsx, page.tsx, kundli/page.tsx, saved/page.tsx, panchang/[city]/[date]/page.tsx}
web/app/api/engine/[...path]/route.ts
web/app/{manifest.ts, sw.ts, sitemap.ts, robots.ts}
web/components/ui/*            Button, Card, Tabs, Field, Banner, ThemeToggle, LocaleToggle
web/components/chart/{geometry.ts, NorthIndianChart.tsx, SouthIndianChart.tsx, ChartTable.tsx}
web/components/form/{BirthForm.tsx, PlaceSearch.tsx}
web/components/kundli/{KundliHeader.tsx, SensitivityBanner.tsx, OverviewTab.tsx, ChartsTab.tsx, PlanetsTab.tsx,
                        DashaTab.tsx, DoshasTab.tsx, StrengthTab.tsx, BirthPanchangTab.tsx}
web/components/panchang/PanchangCard.tsx
web/lib/api/{types.ts (generated), client.ts, engine.ts}
web/lib/{format.ts, query.ts, cycles.ts, store.ts, saved.ts, i18n-engine.ts}
web/lib/pdf/{Report.tsx, fonts.ts}
web/messages/{en.json, hi.json}
web/tests/unit/*.test.ts(x)   web/e2e/*.spec.ts   web/e2e/fixtures/ (golden requests from backend fixtures)
```

---

### Task 1: Web scaffold, tooling, formatting helpers, compose, CI

**Files:** all scaffold files above plus `lib/format.ts`; test `tests/unit/format.test.ts`

**Interfaces — Produces:**
- `formatDms(deg: number): string` gives `"7°43′56″"`. Degrees are within a sign (0–30) and the seconds must not round up to 60.
- `formatInZone(isoUtc: string, tz: string, locale: "en"|"hi", style: "date"|"datetime"|"time"): string`, built on `Intl.DateTimeFormat` with `timeZone`.
- `zoneLabel(tz: string): string` gives `"IST (Asia/Kolkata)"`.

- [ ] **Step 1:** `pnpm create next-app web --ts --app --tailwind --eslint --src-dir=false --import-alias "@/*"`. Pin Node 22 in `.nvmrc` and `engines`. Add Vitest, Testing Library, Playwright and the rest of the dependency list. Write `web/LICENSE` ("Copyright … All rights reserved."). Set tsconfig strict and noUncheckedIndexedAccess.
- [ ] **Step 2: Write failing tests:**
  - `formatDms(7.7322)` gives `"7°43′56″"`.
  - `formatDms(29.999999)` gives `"29°59′59″"`, never 60″.
  - `formatInZone("1947-08-14T18:30:00Z","Asia/Kolkata","en","datetime")` contains `"15 Aug 1947"` and `"00:00"`.
  - The same instant with `"America/New_York"` contains `"14 Aug 1947"`.
  - Hindi locale output contains Devanagari month text.
- [ ] **Step 3:** Run `pnpm vitest run tests/unit/format.test.ts` and expect it to FAIL. Implement, then expect PASS.
- [ ] **Step 4:** Root `docker-compose.yml` defines service `api` (build `./`, the Phase 1 Dockerfile, port 8000) and service `web` (build `./web`, port 3000, `ENGINE_URL=http://api:8000`). `web/Dockerfile` uses a Next standalone build.
- [ ] **Step 5:** `.github/workflows/web.yml` runs pnpm install, `sync:i18n`, lint, `tsc --noEmit` and vitest. E2E is added in Task 13.
- [ ] **Step 6: Commit** `chore(web): scaffold Next.js portal, formatting helpers, compose, CI`.

---

### Task 2: API contract, typed client, proxy route

**Files:** `scripts/gen-types.mjs`, `lib/api/types.ts`, `lib/api/client.ts`, `lib/api/engine.ts`, `app/api/engine/[...path]/route.ts`; tests `tests/unit/client.test.ts`, `tests/unit/proxy.test.ts`

**Interfaces — Produces:**
- Type aliases, all derived from generated `paths`:
  - `KundliRequest = paths["/api/v1/kundli"]["post"]["requestBody"]["content"]["application/json"]`
  - `Kundli = paths["/api/v1/kundli"]["post"]["responses"]["200"]["content"]["application/json"]`
  - the same pattern for `PanchangRequest`/`DayPanchang`, `DashaRequest`/`DashaNode`, `Place` (from `/api/v1/places`), and `Health`.
- `class EngineError extends Error { status: number; fieldErrors: Record<string,string> }`.
- `engine.kundli(req): Promise<Kundli>`, `engine.panchang(req)`, `engine.dasha(req)`, `engine.places(q, signal?)`, `engine.health()`. Each calls `/api/engine/...` in the browser, and calls `ENGINE_URL` directly on the server (for SSR pages).
- Route handler: `GET` and `POST` forward path, query and body to `${ENGINE_URL}/api/v1/${path}`, return status and body unchanged, use a 10 s timeout, and return 502 `{detail:"engine_unreachable"}` on network failure. Only the paths `kundli|panchang|dasha|transit|places|health|version` are allowed; anything else returns 404.

- [ ] **Step 1:** `gen-types.mjs` runs openapi-typescript on `../backend/tests/snapshots/openapi.json` and writes `lib/api/types.ts`. Add the script `pnpm gen:types` and a CI step that regenerates and fails on `git diff --exit-code lib/api/types.ts`.
- [ ] **Step 2: Write failing tests:**
  - `client.test.ts` (fetch mocked):
    - A 422 body `{detail:[{loc:["body","lat"],msg:"…"}]}` becomes `EngineError` with `fieldErrors.lat`.
    - A 422 that mentions `fold` sets `fieldErrors.fold`.
  - `proxy.test.ts`:
    - An unknown path returns 404.
    - A forwarded body is byte-identical to the input.
    - An upstream connection refusal returns 502 `engine_unreachable`.
- [ ] **Step 3:** Run, see FAIL. Implement. Run, see PASS.
- [ ] **Step 4: Commit** `feat(web): typed engine client and proxy`.

---

### Task 3: Design system, layout shell, locales, engine i18n

**Files:** `app/[locale]/layout.tsx`, `components/ui/*`, `app/globals.css` (tokens), `messages/{en,hi}.json`, `scripts/sync-i18n.mjs`, `lib/i18n-engine.ts`, middleware for locale; tests `tests/unit/i18n-engine.test.ts`, `tests/unit/ui.test.tsx`

**Interfaces — Produces:**
- `engineLabel(key: string, locale: "en"|"hi"): string` returns the engine i18n value, falling back to the key with a console warning in dev.
- UI components: `<Card title>`, `<Tabs items=[{id,label,content}] urlParam="tab">` (the selected tab is mirrored to the URL), `<Banner tone="warn"|"info">`, `<Field label error>`, `<ThemeToggle/>` (system/light/dark, stored in localStorage inside try/catch), `<LocaleToggle/>`.

- [ ] **Step 1:** Tokens in `globals.css` per spec §5. Dark is the night-sky indigo `--bg:#0B1026`, `--accent:#F59E0B`, gold `--gold:#E8C26A`, ivory `--ink:#F5EFE3`. Light is ivory `--bg:#FBF7EF` with indigo ink `--ink:#141A33`. Theme follows `prefers-color-scheme`, overridable via `data-theme`. Every text/background pair must meet AA; write a contrast unit test that parses the token values.
- [ ] **Step 2: Write failing tests:**
  - `engineLabel("karka","hi")` gives `"कर्क"`, the exact value from the synced file.
  - `engineLabel("unknown","en")` gives `"unknown"`.
  - Tabs: clicking updates the `?tab=` param, and arrow keys move focus (roving tabindex).
  - Contrast: every token pair is ≥ 4.5:1.
  - `messages/en.json` and `hi.json` have identical key sets.
- [ ] **Step 3:** Run FAIL, implement, run PASS.
- [ ] **Step 4:** Layout has a header (wordmark "Kundli", nav Home/Panchang/Saved, theme toggle, locale toggle), a footer with the engine version from `/health`, the self-hosted fonts and a skip link.
- [ ] **Step 5: Commit** `feat(web): design tokens, layout shell, en/hi locales`.

---

### Task 4: Birth form, place search, URL query contract

**Files:** `components/form/{BirthForm,PlaceSearch}.tsx`, `lib/query.ts`, `app/[locale]/page.tsx`; tests `tests/unit/query.test.ts`, `tests/unit/birthform.test.tsx`

**Interfaces — Produces:**
- `KundliQuery = {date:"YYYY-MM-DD", time:"HH:MM", tz, lat, lon, place, fold?, style:"north"|"south", node:"MEAN"|"TRUE"}`. The name is NOT part of the query; it lives only in local state and saved charts.
- `toSearchParams(q): URLSearchParams`.
- `parseKundliQuery(sp): {ok:true, value:KundliQuery} | {ok:false, errors:Record<string,string>}`.
- `toKundliRequest(q): KundliRequest`.

- [ ] **Step 1: Write failing tests:**
  - query round trip: parse(toSearchParams(q)) deep-equals q;
  - `parseKundliQuery rejects invalid values`: date 2023-02-30, lat 999, lon −181, time 25:00, missing tz;
  - BirthForm (engine mocked):
    - typing "varan" shows Varanasi with its tz;
    - submit navigates to `/kundli?…`;
    - a 422 nonexistent-time error shows under the time field;
    - an ambiguous-time error shows a first/second occurrence choice that resubmits with `fold`;
  - PlaceSearch debounces 250 ms and aborts the stale request.
- [ ] **Step 2:** Run FAIL, implement, run PASS.
- [ ] **Step 3:** Home page shows a hero with the form, plus a `PanchangCard` placeholder slot that Task 9 fills.
- [ ] **Step 4: Commit** `feat(web): birth form, place search, shareable kundli URL`.

---

### Task 5: Chart components (North and South Indian)

**Files:** `components/chart/{geometry.ts, NorthIndianChart.tsx, SouthIndianChart.tsx, ChartTable.tsx}`; tests `tests/unit/chart.test.tsx`

**Interfaces — Produces:**
- `ChartPlanet = {key: string /*graha key*/, rashi: number /*1-12*/, degInSign?: number, retro?: boolean, combust?: boolean}`.
- `<NorthIndianChart lagnaRashi={1..12} planets={ChartPlanet[]} title showDegrees locale/>` and `<SouthIndianChart …same props/>`.
- `NORTH_HOUSES: Record<1..12, [number,number][]>` holds polygons on a 400×400 box: house 1 is the top-centre kite `(200,0),(300,100),(200,200),(100,100)`, with houses running anticlockwise as in spec §4.6.
- `NORTH_ANCHORS: Record<1..12,{planets:[x,y], rashi:[x,y]}>`.
- `SOUTH_CELLS: Record<1..12 /*rashi*/, {x,y}>` places Meena at the top-left corner and runs clockwise: Meena, Mesha, Vrishabha, Mithuna along the top row.
- Short planet labels come from messages (`Su Mo Ma Me Ju Ve Sa Ra Ke` / `सू चं मं बु गु शु श रा के`). Retrograde is shown with the `ᴿ` suffix, combust with an underline.

- [ ] **Step 1: Write failing tests:**
  - For every lagna 1–12, the North house h shows rashi number `((lagna+h-2) mod 12)+1`.
  - A planet with rashi r lands in North house `((r-lagna+12) mod 12)+1`.
  - South places a planet in the cell of its rashi regardless of lagna, and marks the lagna cell with a diagonal line and "Asc".
  - For the India 1947 data, North house 3 contains Su, Mo, Me, Ve and Sa.
  - The chart has `role="img"` plus an aria-label, and ChartTable renders the same data as a visually hidden table.
  - A snapshot of the SVG geometry.
- [ ] **Step 2:** Run FAIL, implement, run PASS.
- [ ] **Step 3: Commit** `feat(web): North and South Indian chart components`.

---

### Task 6: Kundli page — header, sensitivity banner, Overview, Planets, Panchang-at-birth

**Files:** `app/[locale]/kundli/page.tsx`, `components/kundli/{KundliHeader,SensitivityBanner,OverviewTab,PlanetsTab,BirthPanchangTab}.tsx`, `lib/store.ts`; tests `tests/unit/kundli-page.test.tsx`

**Interfaces — Consumes:** `parseKundliQuery`, `engine.kundli`, `engineLabel`, `formatDms`, `formatInZone`. **Produces:** the Zustand store `useKundli()` with `{query, data: Kundli|null, status: "idle"|"loading"|"error"|"ready", error}` and `load(query)`.

- [ ] **Step 1: Write failing tests** (engine mocked with the India 1947 API response, captured by running the Phase 1 API and committed as `tests/fixtures/india1947.json`):
  - The header shows lagna "Vrishabha 7°43′56″", Moon nakshatra "Pushya 1", and syllable.
  - The sensitivity banner appears exactly when `warnings` contains `birth_time_sensitive`.
  - The planets table has 9 rows whose values equal the fixture (iterate the fixture, not literals).
  - The Panchang tab shows vaar "Guru" and the tithi end time in IST.
  - An invalid query renders the form with errors (Review Focus 2).
  - The loading state shows a skeleton, and the error state shows retry.
- [ ] **Step 2:** Run FAIL, implement, run PASS.
- [ ] **Step 3: Commit** `feat(web): kundli page core tabs`.

---

### Task 7: Charts tab and Dasha tab

**Files:** `components/kundli/{ChartsTab,DashaTab}.tsx`; tests `tests/unit/charts-tab.test.tsx`, `tests/unit/dasha-tab.test.tsx`

**Interfaces — Consumes:** chart components, `engine.dasha`, the `Kundli.vargas`, `Kundli.vimshottari` and `Kundli.yogini` shapes.

- [ ] **Step 1: Write failing tests:**
  - The varga selector lists the 16 vargas, and selecting D10 renders D10 signs from `data.vargas["10"]`.
  - The style toggle switches North/South and persists in the query.
  - Dasha shows mahas with start/end in the birth tz.
  - The current period (the one containing "now", with the clock mocked) is highlighted down to the deepest loaded level.
  - `expands only the clicked node via /dasha`: clicking an antar issues one `/dasha` call with that path and depth 1, and renders the pratyantars.
  - The Yogini sub-tab renders.
- [ ] **Step 2:** Run FAIL, implement, run PASS.
- [ ] **Step 3: Commit** `feat(web): charts and dasha tabs`.

---

### Task 8: Doshas tab and Strength tab

**Files:** `components/kundli/{DoshasTab,StrengthTab}.tsx`, `lib/cycles.ts`; tests `tests/unit/cycles.test.ts`, `tests/unit/doshas-strength.test.tsx`

**Interfaces — Produces:** `groupSadeSati(phases: {kind,start_utc,end_utc}[], gapDays = 1095): {start_utc, end_utc, phases: Phase[]}[]`. This is display grouping only and does not recompute any phase.

- [ ] **Step 1: Write failing tests:**
  - With the India 1947 fixture, `groupSadeSati` yields 4 cycles: 1947–1950, 1973–1980, 2002–2009 and 2032–2039. The 2002 cycle contains 8 phases.
  - Dhaiya phases are excluded from the cycles and listed separately.
  - Manglik shows a tick or dash per reference point and the level.
  - Kaal Sarpa shows "full — Anant".
  - The Shadbala bars render one row per planet with total rupa and the required-rupa marker, and the ratio below 1 is visually flagged.
  - The Ashtakavarga grid has 7 BAV rows plus an SAV row indexed by house from the lagna, and SAV sums to 337.
- [ ] **Step 2:** Run FAIL, implement, run PASS.
- [ ] **Step 3: Commit** `feat(web): doshas and strength tabs`.

---

### Task 9: Daily panchang pages and home panchang card

**Files:** `app/[locale]/panchang/[city]/[date]/page.tsx`, `components/panchang/PanchangCard.tsx`, `app/{sitemap,robots}.ts`, `lib/cities.ts` (top 200 Indian cities by population, generated from `backend/data/cities.tsv` by a script at build time); tests `tests/unit/panchang-page.test.tsx`

**Interfaces — Produces:** route `/[locale]/panchang/[citySlug]/[YYYY-MM-DD]` with `export const revalidate = 86400`, and `generateStaticParams` for top-200 cities × {yesterday, today, tomorrow} in IST. `PanchangCard({city})` fetches client-side.

- [ ] **Step 1: Write failing tests:**
  - The page for `new-delhi/2024-01-10` (engine mocked with a captured `/panchang` response) shows sunrise and sunset in IST and five elements with end times.
  - `generateMetadata` produces a title containing city and date in the locale.
  - JSON-LD `@type: "Event"` is NOT used. Plain `WebPage` with a `dateModified` is used instead.
  - An unknown city slug returns 404.
  - An invalid date returns 404.
- [ ] **Step 2:** Run FAIL, implement, run PASS. The home card uses the last-used city from localStorage (in try/catch), defaulting to New Delhi.
- [ ] **Step 3: Commit** `feat(web): daily panchang pages and home card`.

---

### Task 10: Saved charts and PWA

**Files:** `lib/saved.ts`, `app/[locale]/saved/page.tsx`, `app/{manifest.ts, sw.ts}`; tests `tests/unit/saved.test.ts` (fake-indexeddb)

**Interfaces — Produces:**
- `SavedChart = {id, name, query: KundliQuery, response: Kundli, engine_version, savedAt}`.
- `saveChart(name, query, response)`, `listCharts()`, `getChart(id)`, `renameChart(id,name)`, `deleteChart(id)`.

- [ ] **Step 1: Write failing tests:**
  - save → list → get round trip.
  - rename.
  - delete.
  - `saved chart with old engine_version is recomputed`: opening calls `engine.kundli`, replaces the stored response, and shows an "updated" note.
  - When IndexedDB is unavailable (it throws), the Saved page shows an "unavailable in this browser" message and the rest of the app works.
- [ ] **Step 2:** Run FAIL, implement, run PASS.
- [ ] **Step 3:** Serwist service worker precaches the app shell. The manifest has name, icons and theme colour. Offline, saved charts open from IndexedDB, and a new calculation shows "needs connection".
- [ ] **Step 4: Commit** `feat(web): saved charts and installable PWA`.

---

### Task 11: PDF report

**Files:** `lib/pdf/{Report.tsx, fonts.ts}`, a download button in `KundliHeader`; tests `tests/unit/pdf.test.tsx`

**Interfaces — Produces:** `renderReport(data: Kundli, query: KundliQuery, name: string|undefined, locale): Promise<Blob>`. Its contents follow spec §4.5. Charts are drawn with react-pdf `Svg`, using the same geometry constants from Task 5 (import, do not duplicate).

- [ ] **Step 1: Write failing tests:**
  - The India 1947 report in `en` produces a PDF whose extracted text (via pdfjs-dist in the test) contains "Vrishabha" and "Pushya".
  - `pdf hindi contains Devanagari lagna text`: in `hi` the extracted text contains "वृषभ".
  - The page count is between 8 and 12.
  - The footer contains the engine_version.
- [ ] **Step 2:** Run FAIL, implement, run PASS. Fonts are registered from self-hosted TTFs: Noto Sans and Noto Sans Devanagari.
- [ ] **Step 3: Commit** `feat(web): Hindi/English PDF report`.

---

### Task 12: Visual polish pass

**Files:** components touched for motion, empty states, skeletons; `tests/unit/motion.test.tsx`

- [ ] **Step 1: Write failing test:** with `prefers-reduced-motion: reduce`, the chart draw-in and tab transitions are disabled, checked through the computed `animation-name: none`.
- [ ] **Step 2:** Implement the chart draw-in (stroke-dashoffset 600 ms), tab cross-fade (150 ms), skeletons and empty states. Check the 320 px layout for every page. Run PASS.
- [ ] **Step 3: Commit** `feat(web): motion, skeletons, mobile polish`.

---

### Task 13: End-to-end golden suite, visual regression, accessibility, Lighthouse

**Files:** `web/e2e/{golden.spec.ts, flows.spec.ts, a11y.spec.ts, visual.spec.ts}`, `web/e2e/fixtures/` (generated from `backend/fixtures/golden/charts/*.json` by a script), `playwright.config.ts` (webServer starts uvicorn and next), `lighthouserc.json`; modify `.github/workflows/web.yml`

- [ ] **Step 1: Write the e2e specs:**
  - `golden.spec.ts`: for every golden chart, submit the form and fetch the same request directly from the API in the test. Assert that each planet's displayed rashi, dms degree, nakshatra-pada and house, plus the lagna and the first maha lord, equal the API values, formatted with the same `formatDms`.
  - `flows.spec.ts`:
    - `browser in America/New_York shows IST times` (`timezoneId` option).
    - `bad query shows form errors`.
    - The DST ambiguous flow for New York 2021-11-07 01:30.
    - Save, reload, open, delete.
    - PDF download.
    - Hindi locale run.
    - Engine down shows the retry state.
  - `a11y.spec.ts`: axe on home, kundli (each tab), panchang and saved pages, with 0 serious or critical violations.
  - `visual.spec.ts`: chart screenshots for 3 charts × 2 themes × 2 styles, plus `hi` kundli at 320 px.
- [ ] **Step 2:** Run `pnpm playwright test`. Fix failures in the owning component, never by loosening assertions.
- [ ] **Step 3:** Lighthouse CI on mobile for home, kundli and panchang: performance ≥ 90, accessibility ≥ 90. Measure kundli P95 load (form submit → chart visible) over 20 runs with 4G throttling, and require it under 2 s.
- [ ] **Step 4:** CI: the backend suite plus the web unit, contract, e2e, a11y and Lighthouse jobs, uploading reports.
- [ ] **Step 5: Commit** `test(web): e2e golden suite, a11y, visual, Lighthouse gates`.

---

## Phase 2 exit criteria
- Every golden chart renders values identical to the API (e2e green).
- axe shows 0 serious violations, and Lighthouse mobile is ≥ 90 for performance and accessibility.
- `docker compose up` serves the portal at :3000 backed by the engine at :8000.
- The Phase 1 regression suite is still green in the same CI run.

---

## Amendment 2026-10-17 — UI PRD alignment (spec §10)

Prerequisite now includes Phase 1 T15 and T16. Changes per task:

- **Task 3:** use the tokens from spec §10.1 (maroon/gold/ivory/slate; Noto Serif plus Noto Serif Devanagari, Inter, IBM Plex Mono) and test them for AA contrast. The header gets the panchang ticker, recent kundlis and the HI/EN toggle. Add the mobile bottom nav (Kundli · Houses · Dasha · Yogas & Doshas · More). Vedic line icons go in `components/icons/` with a 1.5 px stroke.
- **Task 4:** add a gender field (stored locally and never sent to the API); an optional seconds field; an ayanamsa select with Lahiri, Raman, KP and Fagan (sent as `settings.ayanamsa`); and a "Birth time unknown" checkbox that sends `time_known:false`. Tests: seconds are preserved in the query round trip; time unknown produces a request without `time` and with `time_known:false`.
- **Task 6:** use the 3-panel desktop dashboard from spec §10.1, sticky left and right panels, and keys 1–12 / D. Chart tabs are D1, D9 and Moon (the Chandra chart is the D1 rotated to the Moon's sign, using the engine's Moon rashi; no computation). Strength meters show Shadbala total rupa against required rupa and SAV bindus. When `meta.lagna_basis == "moon"`, show a "Chandra kundli — birth time unknown" banner and hide the strength meters.
- **New Task 7a, Houses screen (S-04):** `components/kundli/HousesTab.tsx` with a 12-house selector, swipe on mobile, and a bottom sheet. It shows the engine's `bhavas_detail` (rashi, lord, lord's house, occupants, aspected_by, karakas) and SAV for the house. Tests: India 1947 house 1 shows lord Venus in the 3rd and occupant Rahu; arrow keys and keys 1–12 navigate.
- **Task 7:** Charts tab becomes the S-07 Varga explorer grid (16 cards with life-area labels from messages, vargottama badges).
- **Task 8:** Doshas tab becomes S-06. Add an exalted-planet count card (counting `dignity == EXALTED` from the engine) and show the Shri Ram benchmark note when 5 or more are exalted.
- **Task 9:** the landing hero (S-01) gets the animated diamond chart and engine credentials. Add a test asserting the landing page contains no numeric "Kundlis generated", rating or testimonial content.
- **Task 11:** the PDF uses the maroon/gold style, with a citations footer (Swiss Ephemeris, BPHS). Add a share button using the Web Share API with a chart PNG and link, falling back to copying the link.
- **Task 12:** the loading state becomes a rotating zodiac wheel with staged progress.
