# Phase 2 — Kundli Portal (Web) Design Spec

- **Date:** 2026-10-17
- **Status:** Draft for review
- **Depends on:** Phase 1 engine + API (`docs/specs/2026-10-16-phase1-calculation-engine-design.md` §6). Phase 2 build starts only after Phase 1 Task 13 (API) is merged.
- **Programme:** 1 Engine+API → **2 Web portal** → 3 Accounts/Scale → 4 Pandit prediction engine

## 1. Intent

A public, premium, self-serve kundli website. A visitor enters birth details and gets a complete,
accurate North Indian kundli computed by the Phase 1 engine. The bar for look and feel is "top-class Indian astrology site"
— an original design, not a copy of any existing site.

**Honesty rule (binding):** every astrological value on screen comes from the engine API response. The web
layer formats and visualises; it never computes, rounds differently or invents astrology. No
prediction/reading text appears until Phase 4.

### Success criteria
- India 1947 golden chart (and every Phase 1 golden chart) renders exactly the engine's values (automated).
- Kundli page usable at 320 px width; WCAG 2.1 AA; Lighthouse ≥ 90 performance/accessibility on mobile.
- Birth details → rendered kundli in < 2 s P95 on a mid-range phone over 4G (PRD §7.2).
- Hindi and English throughout, including PDF.

## 2. Scope

### In scope
1. Home: birth-details form + today's panchang for the visitor's chosen city.
2. Kundli result with tabs: Overview, Charts, Planets, Dasha, Doshas, Strength, Panchang-at-birth.
3. Daily Panchang pages per city/date (server-rendered for SEO).
4. Saved charts on the device (IndexedDB), list/open/delete.
5. PDF report (Hindi or English).
6. North and South Indian chart styles; light/dark themes; Hindi/English toggle.
7. Installable PWA shell (offline viewing of saved charts; new calculations need the API).

### Out of scope
Accounts, cloud sync, payments, rate limiting, deployment at scale (Phase 3). Predictions, psychology readings, yogas, AI chat, astrologer booking (Phase 4+). Offline calculation (WASM ephemeris) — deferred.

## 3. Architecture

```
vedic-astro/
  backend/            Phase 1 (AGPL)
  web/                Phase 2 (proprietary, own LICENSE "All rights reserved")
    app/[locale]/                 Next.js App Router pages (en, hi)
      page.tsx                    Home
      kundli/page.tsx             Kundli result (client component reads URL params)
      panchang/[city]/[date]/     SSR/ISR daily panchang
      saved/page.tsx
    app/api/engine/[...path]/route.ts   Server proxy → FastAPI (hides engine URL, no CORS)
    components/chart/NorthIndianChart.tsx, SouthIndianChart.tsx
    components/kundli/*           Tab panels
    lib/api/types.ts              GENERATED from backend OpenAPI (openapi-typescript)
    lib/api/client.ts             Typed fetch wrapper
    lib/format.ts                 dms, dates in IST/local tz, number formatting (display only)
    lib/store.ts                  Zustand: current kundli request/response, UI prefs
    lib/saved.ts                  IndexedDB (idb) saved charts
    lib/pdf/                      @react-pdf/renderer report
    messages/{en,hi}.json         UI strings (next-intl)
    public/i18n/engine.json       COPIED from backend/src/vedic_engine/data/i18n.json at build
    e2e/                          Playwright
```

- **Stack:** Next.js (App Router) + React + TypeScript (strict) + Tailwind CSS + Zustand + next-intl + idb + @react-pdf/renderer + Serwist (PWA). Node LTS, pnpm.
- **Engine access:** browser → `/api/engine/*` (Next route handler) → FastAPI `/api/v1/*`. The proxy forwards bodies unchanged and maps errors; it adds no logic.
- **Contract:** `lib/api/types.ts` is generated from the backend OpenAPI snapshot (`backend/tests/snapshots/openapi.json`). CI fails if regeneration produces a diff.
- **Translations:** engine keys (`karka`, `punarvasu`) are displayed via the engine's own i18n table; UI chrome via `messages/*.json`.

## 4. Pages & components

### 4.1 Home (`/[locale]`)
Birth form: name (optional), date (DD-MM-YYYY), time (HH:MM, 24 h with AM/PM helper), "time unknown" is NOT offered (engine needs time), place (autocomplete via `/places`, shows country + timezone), advanced: chart style, node (Mean/True), ayanamsa shown read-only (Lahiri). Ambiguous DST times → inline choice "first/second occurrence" (maps to `fold`). Submit → `/kundli?…` with all inputs in the URL query (shareable, no personal data sent anywhere but our API; name is never sent to the API).
Below the form: today's panchang card for the selected/last city.

### 4.2 Kundli (`/[locale]/kundli`)
Header: name, date/time/place, lagna, rashi, nakshatra-pada, name syllable, Save / PDF / Share.
**Birth-time sensitivity banner** when the engine returns `birth_time_sensitive` (e.g. "Lagna changes 3 min later").
Tabs:
- **Overview:** key facts cards; dosha badges (Manglik level, Kaal Sarpa, current Sade Sati phase); current Maha/Antar/Pratyantar dasha with dates.
- **Charts:** D1 and D9 side by side; varga selector (all 16); North/South toggle; planet degrees on/off; retrograde and combust markers; Bhava table.
- **Planets:** table — graha, rashi, degree (dms), nakshatra-pada, house, dignity, combust, retro, avastha.
- **Dasha:** Vimshottari as a horizontal timeline + expandable list down to 5 levels (lazy-loads deeper levels via `/dasha`), "today" marker; Yogini tab.
- **Doshas:** Manglik per reference point; Kaal Sarpa type; Sade Sati and Dhaiya grouped into cycles (phases merged when gaps < 3 years, each phase listed inside its cycle).
- **Strength:** Shadbala bar chart vs required rupa; Bhinnashtakavarga grid per planet + Sarvashtakavarga row by house.
- **Panchang at birth:** vaar, tithi/paksha, nakshatra, yoga, karana with end times.

### 4.3 Daily Panchang (`/[locale]/panchang/[city]/[date]`)
Server-rendered with daily revalidation; pre-generated for the 200 most populous Indian cities for today ±1 day; any city/date renders on demand. Shows sunrise/sunset/moonrise/moonset, tithi, nakshatra, yoga, karana with end times, and a "Make my kundli" CTA. Structured data (schema.org) and per-page meta tags.

### 4.4 Saved (`/[locale]/saved`)
List of saved charts from IndexedDB (stores the request + last response + engine_version); open, rename, delete. If `engine_version` differs from the live API, opening re-computes and marks "updated".

### 4.5 PDF report
Client-side via @react-pdf/renderer with embedded Noto Sans + Noto Sans Devanagari. Contents: cover, birth details, D1/D9/D10 charts, planets table, panchang, Vimshottari (3 levels), doshas, Shadbala, Ashtakavarga, engine version + settings footer. 8–12 pages.

### 4.6 Chart components
`<NorthIndianChart lagnaRashi planets vargaLabel showDegrees />` and `<SouthIndianChart …/>`: pure SVG, responsive (320 → 480 px), print-safe, theme tokens, each with a visually hidden table alternative for screen readers. Input is the engine response shape; geometry is fixed (house 1 top centre; rashi numbers 1–12 in each house).

## 5. Visual design
Original "night-sky" theme.
- **Dark (default on dark OS):** deep indigo background (#0B1026 range), star-dust texture used sparingly, saffron/marigold accent (#F59E0B range), soft gold for highlights, ivory text.
- **Light:** warm ivory background, indigo ink, saffron accents.
- **Type:** Instrument Serif (display), Inter (UI), Noto Sans Devanagari / Tiro Devanagari Hindi (Hindi), IBM Plex Mono (degrees).
- Motion: subtle (chart draw-in, tab transitions), respects `prefers-reduced-motion`.
- Colours as CSS tokens; both themes meet AA contrast.

## 6. Error & edge handling
- API 422 → field-level messages under the form (DST nonexistent/ambiguous, out of range 1800-01-01 06:00 UT … 2399-12-31, bad place).
- API unreachable → clear retry state; saved charts still viewable.
- Polar latitude / school-dependent warnings shown as info notes.
- All times shown in the birth place's timezone, with the IANA zone name visible.

## 7. Testing
1. **Unit (Vitest):** chart geometry (house polygons, rashi numbering for all 12 lagnas), formatting (dms, dates), cycle grouping of Sade Sati, URL ⇄ form round trip.
2. **Contract:** generated types vs OpenAPI snapshot (CI diff check).
3. **E2E (Playwright, real API):** spin up FastAPI + Next; for each Phase 1 golden chart (incl. India 1947): submit the form, assert every displayed lagna/planet/nakshatra/dasha value equals the API response; Hindi locale run; DST-ambiguous flow; error states; save/open/delete; PDF downloads and contains the lagna text.
4. **Visual regression:** Playwright screenshots of charts for 3 fixed charts × 2 themes × 2 styles.
5. **Accessibility:** axe on every page (0 serious violations).
6. **Performance:** Lighthouse CI mobile budgets (performance ≥ 90, a11y ≥ 90); kundli P95 < 2 s.
7. Phase 1 backend suite runs in the same CI (regression gate).

## 8. Delivery
- `docker compose up` runs API + web locally.
- CI: lint (eslint), typecheck (tsc --noEmit), unit, contract, e2e, a11y, Lighthouse.
- Hosting choice deferred to Phase 3.

## 9. Open items (do not block)
- Final brand name and logo (placeholder wordmark "Kundli" until provided).
- Which 200 cities to pre-render: default = most populous Indian cities from GeoNames.
