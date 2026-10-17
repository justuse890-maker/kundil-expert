# Vedic Kundli

A Vedic astrology app: enter birth details and get a kundli (Lahiri sidereal positions, lagna,
panchang, vargas, Vimshottari and other dashas, doshas, Sade Sati, ashtakavarga, shadbala) with
cited, chart-specific analysis. All astronomy is computed server-side by the Swiss Ephemeris
based engine in `backend/`; the UI in `frontend/` only displays it.

## Run

Needs [uv](https://docs.astral.sh/uv/) and Python 3.12.

```sh
./run.sh            # then open http://localhost:8000   (PORT=9000 ./run.sh to change port)
```

API docs are at `/docs`, health at `/health`. Or with Docker: `docker build -t vedic-astro-api .
&& docker run --rm -p 8000:8000 vedic-astro-api`.

## Test

```sh
cd backend
uv run pytest -n auto   # unit, property and golden tests
uv run pytest -m perf -s                              # latency gate: P95 < 200 ms
uv run python scripts/accuracy_report.py              # rewrites ../reports/accuracy.md, exit 1 on FAIL
uv run ruff check && uv run mypy --strict src/vedic_engine
```

## Accuracy

Every quantity is checked against an independent reference: JPL Horizons (planets within 1",
Moon 2"), the Indian Astronomical Ephemeris (Lahiri ayanamsa within 1"), Drik Panchang (sunrise
and element end times within 1 minute), an independent sidereal-time ascendant (within 1'), and
the BPHS and Raman worked examples (ashtakavarga exact, shadbala within 1 virupa). Current
results: all rows PASS, worst planet error about 0.13", `build_kundli` P95 about 150 ms. Full
table, conventions and known source variants: [reports/accuracy.md](reports/accuracy.md).

Licence: AGPL-3.0 (see `LICENSE`); data attributions in `NOTICE.md`.
