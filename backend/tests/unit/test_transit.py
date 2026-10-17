import itertools
import random
from datetime import UTC, datetime
from pathlib import Path

import pytest
import swisseph as swe

from vedic_engine import ephemeris, transit
from vedic_engine.constants import Graha
from vedic_engine.models import Settings
from vedic_engine.timeutil import jd_from_utc, utc_from_jd
from vedic_engine.transit import positions_at, sign_ingresses

S = Settings()
MAKARA, KUMBHA = 9, 10


@pytest.fixture(autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


def _ingresses(y0: int, y1: int) -> list[tuple[datetime, int]]:
    jd0 = jd_from_utc(datetime(y0, 1, 1, tzinfo=UTC))
    jd1 = jd_from_utc(datetime(y1, 1, 1, tzinfo=UTC))
    return [(utc_from_jd(j), s) for j, s in sign_ingresses(Graha.SATURN, jd0, jd1, S)]


def test_saturn_ingress_known() -> None:
    ing = _ingresses(2022, 2024)
    # Kumbha Apr 2022, retrograde re-entry into Makara Jul 2022, Kumbha again Jan 2023
    assert [s for _, s in ing] == [KUMBHA, MAKARA, KUMBHA]
    assert (ing[1][0].year, ing[1][0].month) == (2022, 7)
    assert abs((ing[2][0] - datetime(2023, 1, 17, 12, tzinfo=UTC)).total_seconds()) <= 86400


def test_ingress_is_a_real_boundary() -> None:
    jd = sign_ingresses(
        Graha.SATURN,
        jd_from_utc(datetime(2022, 8, 1, tzinfo=UTC)),
        jd_from_utc(datetime(2024, 1, 1, tzinfo=UTC)),
        S,
    )[0][0]
    before = ephemeris.body_longitude(jd - 2 / 1440, Graha.SATURN, S)
    after = ephemeris.body_longitude(jd + 2 / 1440, Graha.SATURN, S)
    assert before < 300.0 <= after


def test_moon_ingresses_every_couple_of_days() -> None:
    jd0 = jd_from_utc(datetime(2024, 1, 1, tzinfo=UTC))
    ing = sign_ingresses(Graha.MOON, jd0, jd0 + 27.32, S)
    assert 12 <= len(ing) <= 14
    assert all((b[1] - a[1]) % 12 == 1 for a, b in itertools.pairwise(ing))


def test_positions_at_matches_ephemeris() -> None:
    dt = datetime(2024, 4, 10, 6, 30, tzinfo=UTC)
    got = positions_at(dt, S)
    assert got == ephemeris.positions(jd_from_utc(dt), S)
    assert set(got) == set(Graha)


def _hover(t0: float):  # type: ignore[no-untyped-def]
    """Synthetic longitude: 29.9 -> 30.1 -> 29.9 over 0.6 day from t0, else 29.9."""

    def lon(jd: float, graha: Graha, settings: Settings) -> float:
        x = (jd - t0) / 0.6
        return 29.9 + 0.2 * (1 - abs(2 * x - 1)) if 0.0 <= x <= 1.0 else 29.9

    return lon


def test_station_hover_cross_and_recross_within_one_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    t0 = 2460000.0
    monkeypatch.setattr(transit, "_lon", _hover(t0))
    ing = sign_ingresses(Graha.SATURN, t0 - 0.2, t0 + 0.8, S)  # one 1-day scan step
    assert [s for _, s in ing] == [1, 0]
    assert abs(ing[0][0] - (t0 + 0.15)) < 2 / 1440  # up-crossing at x = 0.25
    assert abs(ing[1][0] - (t0 + 0.45)) < 2 / 1440  # down-crossing at x = 0.75


# --- adaptive scan -------------------------------------------------------------------------------


def _reference_ingresses(
    graha: Graha, jd_start: float, jd_end: float, settings: Settings
) -> list[tuple[float, int]]:
    """The original fixed-step scan (1 day; Moon 0.25 day), kept as the exactness oracle."""
    step = 0.25 if graha is Graha.MOON else 1.0
    out: list[tuple[float, int]] = []
    t = jd_start
    lon = transit._lon(t, graha, settings)
    sign = int(lon // 30.0)
    while t < jd_end:
        t_next = min(t + step, jd_end)
        lon_next = transit._lon(t_next, graha, settings)
        if transit._near_boundary(lon) or transit._near_boundary(lon_next):
            n = transit._FINE_SUBSTEPS
            marks = [t + (t_next - t) * i / n for i in range(1, n + 1)]
        else:
            marks = [t_next]
        prev = t
        for i, m in enumerate(marks):
            m_lon = lon_next if i == len(marks) - 1 else transit._lon(m, graha, settings)
            m_sign = int(m_lon // 30.0)
            if m_sign != sign:
                out.append((transit._bisect(prev, m, sign, graha, settings), m_sign))
                sign = m_sign
            prev = m
        t, lon = t_next, lon_next
    return out


def test_adaptive_matches_reference_on_50_random_births() -> None:
    rng = random.Random(2026)
    for _ in range(50):
        jd0 = jd_from_utc(datetime(1850, 1, 1, tzinfo=UTC)) + rng.uniform(0, 200 * 365.25)
        jd1 = jd0 + 100 * 365.25
        assert sign_ingresses(Graha.SATURN, jd0, jd1, S) == _reference_ingresses(
            Graha.SATURN, jd0, jd1, S
        )


@pytest.mark.parametrize(
    ("graha", "days"),
    [
        (Graha.MOON, 120.0),
        (Graha.SUN, 800.0),
        (Graha.MERCURY, 800.0),
        (Graha.VENUS, 800.0),
        (Graha.MARS, 1600.0),
        (Graha.JUPITER, 4000.0),
        (Graha.RAHU, 4000.0),
        (Graha.KETU, 4000.0),
    ],
)
def test_adaptive_matches_reference_for_every_graha(graha: Graha, days: float) -> None:
    rng = random.Random(str(graha))
    for settings in (S, Settings(node="TRUE")):
        for _ in range(3):
            jd0 = jd_from_utc(datetime(1900, 1, 1, tzinfo=UTC)) + rng.uniform(0, 100 * 365.25)
            assert sign_ingresses(graha, jd0, jd0 + days, settings) == _reference_ingresses(
                graha, jd0, jd0 + days, settings
            )


def test_speed_table_bounds_real_speeds() -> None:
    """Every table entry is at least the largest speed Swiss Ephemeris reports (1800-2399)."""
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    bodies = {
        Graha.SUN: [swe.SUN], Graha.MOON: [swe.MOON], Graha.MARS: [swe.MARS],
        Graha.MERCURY: [swe.MERCURY], Graha.JUPITER: [swe.JUPITER], Graha.VENUS: [swe.VENUS],
        Graha.SATURN: [swe.SATURN], Graha.RAHU: [swe.MEAN_NODE, swe.TRUE_NODE],
        Graha.KETU: [swe.MEAN_NODE, swe.TRUE_NODE],
    }  # fmt: skip
    assert set(transit.MAX_SPEED_DEG_PER_DAY) == set(Graha)
    for graha, ids in bodies.items():
        fastest = 0.0
        for body in ids:
            jd = 2378496.5  # 1800-01-01
            while jd < 2597000.0:
                fastest = max(fastest, abs(swe.calc_ut(jd, body, flags)[0][3]))
                jd += 0.5 if graha is not Graha.MOON else 0.1
        assert transit.MAX_SPEED_DEG_PER_DAY[graha] >= fastest, graha


def test_saturn_century_scan_is_cheap(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    real = transit._lon

    def counting(jd: float, graha: Graha, settings: Settings) -> float:
        nonlocal calls
        calls += 1
        return real(jd, graha, settings)

    monkeypatch.setattr(transit, "_lon", counting)
    jd0 = jd_from_utc(datetime(1990, 1, 1, tzinfo=UTC))
    sign_ingresses(Graha.SATURN, jd0, jd0 + 100 * 365.25, S)
    assert calls < 40_000  # the fixed 1-day scan took ~99,000 evaluations
