"""Latency gate (spec 7, 9 item 6): P95 of build_kundli with default arguments."""

import random
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tolerances import P95_MS
from vedic_engine import ephemeris
from vedic_engine.kundli import build_kundli
from vedic_engine.models import BirthInput

pytestmark = pytest.mark.perf

N_CASES = 200
WARMUP = 5

# (tz, lat, lon): a spread of zones and hemispheres.
PLACES = [
    ("Asia/Kolkata", 28.6139, 77.2090),
    ("Asia/Kolkata", 13.0827, 80.2707),
    ("Europe/London", 51.5074, -0.1278),
    ("America/New_York", 40.7128, -74.0060),
    ("Australia/Sydney", -33.8688, 151.2093),
    ("Africa/Johannesburg", -26.2041, 28.0473),
    ("Asia/Singapore", 1.3521, 103.8198),
    ("America/Sao_Paulo", -23.5505, -46.6333),
]


def _births() -> list[BirthInput]:
    rng = random.Random(7)
    start = datetime(1900, 1, 1)
    span_minutes = int((datetime(2100, 12, 31) - start).total_seconds() // 60)
    out: list[BirthInput] = []
    while len(out) < N_CASES + WARMUP:
        tz, lat, lon = rng.choice(PLACES)
        local = start + timedelta(minutes=rng.randrange(span_minutes))
        try:
            out.append(BirthInput(local=local, tz=tz, lat=lat, lon=lon, alt=0.0, fold=0))
        except ValueError:
            continue
    return out


def test_p95_under_200ms(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)
    births = _births()
    for b in births[:WARMUP]:
        build_kundli(b)
    ms: list[float] = []
    for b in births[WARMUP:]:
        t0 = time.perf_counter()
        build_kundli(b)
        ms.append((time.perf_counter() - t0) * 1000.0)
    ms.sort()
    p95 = ms[int(0.95 * len(ms)) - 1]
    print(f"build_kundli over {len(ms)} births: median {ms[len(ms) // 2]:.1f} ms, "
          f"P95 {p95:.1f} ms, max {ms[-1]:.1f} ms")  # fmt: skip
    assert p95 < P95_MS, f"P95 {p95:.1f} ms >= {P95_MS} ms"
