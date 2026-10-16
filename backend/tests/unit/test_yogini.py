from datetime import UTC, datetime, timedelta

import pytest

from vedic_engine.dasha.vimshottari import subtree
from vedic_engine.dasha.yogini import YOGINI_LORD, YOGINIS, yogini
from vedic_engine.models import Settings

BIRTH = datetime(1990, 5, 17, 6, 30, tzinfo=UTC)
S = Settings()
YD = timedelta(days=S.dasha_year_days)


def test_yogini_ashwini_starts_bhramari() -> None:
    mahas = yogini(0.0, BIRTH, S)
    assert mahas[0].lord == "bhramari"
    assert mahas[0].start_utc == BIRTH
    assert mahas[0].end_utc - BIRTH == pytest.approx(4 * YD, abs=timedelta(seconds=1))
    assert mahas[1].lord == "bhadrika"


def test_yogini_cycle_36() -> None:
    mahas = yogini(0.0, BIRTH, S)
    assert [m.lord for m in mahas[:8]] == [YOGINIS[(3 + i) % 8] for i in range(8)]
    span = mahas[8].end_utc - mahas[0].end_utc
    assert span == pytest.approx(36 * YD, abs=timedelta(seconds=1))
    assert mahas[-1].end_utc >= BIRTH + 120 * YD


def test_start_rule_wraps() -> None:
    # Nakshatra 5 (1-based) -> (5+3)%8 == 0 -> sankata; Mrigashira = index 4
    assert yogini(4 * 360 / 27 + 1, BIRTH, S)[0].lord == "sankata"


def test_sub_periods_and_subtree() -> None:
    full = yogini(0.0, BIRTH, S, depth=3)
    m = full[1]  # bhadrika, 5y
    assert m.children[0].lord == "bhadrika"
    assert m.children[0].end_utc - m.children[0].start_utc == pytest.approx(
        5 * 5 / 36 * YD, abs=timedelta(seconds=1)
    )
    bare = yogini(0.0, BIRTH, S, depth=1)[1]
    assert subtree(bare, S, 2) == m
    assert set(YOGINI_LORD) == set(YOGINIS)
