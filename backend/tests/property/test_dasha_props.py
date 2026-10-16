import itertools
from datetime import UTC, datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from vedic_engine.dasha import DashaPeriod
from vedic_engine.dasha.vimshottari import vimshottari
from vedic_engine.dasha.yogini import yogini
from vedic_engine.models import Settings

LON = st.floats(min_value=0.0, max_value=360.0, exclude_max=True, allow_nan=False)
BIRTH = datetime(1985, 11, 3, 12, 0, tzinfo=UTC)
S = Settings()


def _check(p: DashaPeriod) -> None:
    assert p.end_utc > p.start_utc
    if p.children:
        assert p.children[0].start_utc == p.start_utc
        assert p.children[-1].end_utc == p.end_utc
        for a, b in itertools.pairwise(p.children):
            assert a.end_utc == b.start_utc
        for c in p.children:
            assert c.level == p.level + 1
            _check(c)
    else:
        assert p.level == 5 or p.level >= 1


@settings(max_examples=15, deadline=None)
@given(lon=LON)
def test_vimshottari_contiguous(lon: float) -> None:
    mahas = vimshottari(lon, BIRTH, S, depth=5)
    assert mahas[0].start_utc == BIRTH
    for a, b in itertools.pairwise(mahas):
        assert a.end_utc == b.start_utc
    for m in mahas:
        _check(m)
    full = [m for m in mahas[1:10]]
    if len(full) == 9:
        total = full[-1].end_utc - full[0].start_utc
        assert abs(total - timedelta(days=120 * S.dasha_year_days)) < timedelta(seconds=1)


@settings(max_examples=15, deadline=None)
@given(lon=LON)
def test_yogini_contiguous(lon: float) -> None:
    mahas = yogini(lon, BIRTH, S, depth=4)
    assert mahas[0].start_utc == BIRTH
    for a, b in itertools.pairwise(mahas):
        assert a.end_utc == b.start_utc
    for m in mahas:
        _check(m)
