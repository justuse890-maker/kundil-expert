from datetime import UTC, datetime, timedelta

import pytest

from vedic_engine.constants import Graha
from vedic_engine.dasha.vimshottari import balance, subtree, vimshottari
from vedic_engine.models import Settings

BIRTH = datetime(1990, 5, 17, 6, 30, tzinfo=UTC)
S = Settings()
YD = timedelta(days=S.dasha_year_days)
MID_PUNARVASU = 6 * (360 / 27) + (360 / 27) / 2


def test_balance_mid_punarvasu() -> None:
    lord, years = balance(MID_PUNARVASU)
    assert lord == Graha.JUPITER
    assert years == pytest.approx(8.0)
    lord2, years2 = balance(86.6667)
    assert lord2 == Graha.JUPITER and years2 == pytest.approx(8.0, abs=1e-3)


def test_first_maha_clipped_and_children_own_lord_first() -> None:
    mahas = vimshottari(MID_PUNARVASU, BIRTH, S, depth=3)
    first = mahas[0]
    assert first.lord == "jupiter" and first.start_utc == BIRTH
    assert first.end_utc - BIRTH == pytest.approx(8.0 * YD, abs=timedelta(seconds=1))
    assert first.nominal_start_utc == BIRTH - 8.0 * YD
    # Jupiter-Jupiter antar (2.13y) and Jupiter-Saturn (2.53y) end before birth+0; first kept child is clipped.
    assert first.children[0].start_utc == BIRTH
    assert first.children[0].nominal_start_utc is not None
    assert first.children[0].nominal_start_utc < BIRTH


def test_first_antar_is_own_lord() -> None:
    mahas = vimshottari(0.0, BIRTH, S, depth=2)  # Ashwini start: Ketu, full
    assert mahas[0].children[0].lord == "ketu"
    assert mahas[1].children[0].lord == mahas[1].lord


def test_antar_length() -> None:
    mahas = vimshottari(0.0, BIRTH, S, depth=2)
    jupiter = next(m for m in mahas if m.lord == "jupiter")
    ju_sa = next(a for a in jupiter.children if a.lord == "saturn")
    expected = 16 * 19 / 120 * YD
    assert ju_sa.end_utc - ju_sa.start_utc == pytest.approx(expected, abs=timedelta(seconds=1))


def test_depth_5_levels() -> None:
    p = vimshottari(100.0, BIRTH, S, depth=5)[1]
    for lvl in range(1, 5):
        assert p.level == lvl
        total = sum((c.end_utc - c.start_utc for c in p.children), timedelta())
        assert abs(total - (p.end_utc - p.start_utc)) < timedelta(seconds=1)
        p = p.children[0]
    assert p.level == 5 and p.children == ()


def test_balance_near_zero() -> None:
    mahas = vimshottari(40 / 3 - 1e-9, BIRTH, S, depth=3)
    assert mahas[0].lord == "ketu"
    assert mahas[1].lord == "venus"

    def check(p):  # type: ignore[no-untyped-def]
        assert p.end_utc > p.start_utc
        for c in p.children:
            check(c)

    for m in mahas:
        check(m)


def test_covers_120_years_and_errors() -> None:
    mahas = vimshottari(55.0, BIRTH, S)
    assert mahas[-1].end_utc >= BIRTH + 120 * YD
    for bad in (0, 6, -1):
        with pytest.raises(ValueError):
            vimshottari(55.0, BIRTH, S, depth=bad)
        with pytest.raises(ValueError):
            subtree(mahas[0], S, bad)


def test_subtree_matches_full_tree_including_clipped_first() -> None:
    full = vimshottari(55.0, BIRTH, S, depth=5)
    for m in (full[0], full[1]):
        bare = vimshottari(55.0, BIRTH, S, depth=1)[full.index(m)]
        assert subtree(bare, S, 4) == m
