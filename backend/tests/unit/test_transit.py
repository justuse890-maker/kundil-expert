import itertools
from datetime import UTC, datetime
from pathlib import Path

import pytest

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
