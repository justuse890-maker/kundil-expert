# Vedic Kundli

A Vedic astrology app: enter birth details and get a kundli (Lahiri sidereal positions, lagna,
panchang, vargas, Vimshottari and other dashas, doshas, Sade Sati, ashtakavarga, shadbala) with
cited, chart-specific analysis. All astronomy is computed server-side by the Swiss Ephemeris
based engine in `backend/`; the UI in `frontend/` only displays it.

## Run

Needs [uv](https://docs.astral.sh/uv/) and Python 3.12.

```sh
./run.sh                  # then open http://localhost:8000
PORT=9000 ./run.sh        # different port
```

`run.sh` installs the locked runtime dependencies only (`uv sync --frozen --no-dev`, never re-locks) and binds to 127.0.0.1 only, so the app is not reachable from other machines. API docs are at
`/docs`, health at `/health`. With Docker: `docker build -t vedic-astro-api .` then
`docker run --rm -p 8000:8000 vedic-astro-api` (the image is built and checked in CI only).

## Test

```sh
cd backend
uv run pytest -n auto                       # unit, property and golden tests
uv run pytest -m perf -s                    # latency gate, run serially: P95 < 200 ms
uv run python scripts/accuracy_report.py    # rewrites ../reports/accuracy.md; exit 1 on FAIL
uv run ruff check
uv run mypy --strict src/vedic_engine
```

## Accuracy

The engine is checked against independent references for the quantities listed in the
[accuracy report](reports/accuracy.md): JPL Horizons (planets), the Indian Astronomical Ephemeris
(Lahiri ayanamsa), Drik Panchang (sunrise and element end times), an independent sidereal-time
ascendant, an independent Vimshottari computation, and the BPHS and Raman worked examples. All
rows currently PASS. Caveats, all detailed in the report:

* Drik tithi and karana end times are compared after reconciling Drik's Delta T convention; the
  raw difference is up to 96 s (ruling R15).
* Shadbala is verified on the book's printed inputs (formulas only), not on engine-computed
  inputs, and two printed Saptavargaja values are known misprints (R25).
* Ashtakavarga follows the standard JHora/Raman table where BPHS contradicts itself (R23). **R24
  is open:** the Moon BAV 9th-house bindu is placed under Mars (JHora) rather than Moon (Santhanam);
  please verify against a real JHora export.

Not yet verified: any comparison with Jagannath Hora exports (drop them into
`backend/fixtures/golden/jhora/`), and engine-computed Shadbala against an external source.

Licence: AGPL-3.0 (see `LICENSE`); data attributions in `NOTICE.md`.

## Deploy
Free hosting on Render: see [docs/DEPLOY.md](docs/DEPLOY.md).
