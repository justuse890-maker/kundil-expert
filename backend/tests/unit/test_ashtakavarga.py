"""Ashtakavarga tests.

Source: Brihat Parasara Hora Sastra, tr. R. Santhanam, Vol. 2 (Ranjan Publications, 1992),
Ch 66 (benefic-house tables, pp. 854-863) and the example horoscope of Ch 67-70.
"""

import json
from importlib import resources

import pytest

from vedic_engine.ashtakavarga import bav, sav
from vedic_engine.constants import SEVEN, Graha

# Example horoscope, BPHS (Santhanam) Vol. 2 p. 868 (chart) and p. 899 (Ch 72 illustration):
# Lagna, Mercury, Jupiter, Venus in Aquarius; Sun Capricorn; Mars Taurus; Moon Gemini;
# Saturn Scorpio.
EXAMPLE = {
    "sun": 9,
    "moon": 2,
    "mars": 1,
    "mercury": 10,
    "jupiter": 10,
    "venus": 10,
    "saturn": 7,
    "lagna": 10,
}

# Printed BAV rekha counts, each listed starting from the rashi named in the comment
# (Ch 67 p. 873 for the Sun; Ch 69-70 "Trikona and Ekadhipatya Shodhana Chakra" pp. 886-893).
PRINTED = {  # graha: (start rashi index, 12 printed counts)
    Graha.SUN: (9, [5, 3, 2, 4, 3, 4, 6, 5, 2, 3, 6, 5]),  # p. 873, from Capricorn
    Graha.MARS: (1, [3, 4, 5, 3, 2, 1, 6, 5, 2, 3, 2, 3]),  # p. 888, from Taurus
    Graha.JUPITER: (10, [6, 7, 4, 4, 4, 5, 4, 2, 6, 6, 6, 2]),  # p. 891, from Aquarius
    Graha.SATURN: (10, [3, 2, 5, 1, 1, 6, 2, 3, 3, 4, 4, 5]),  # p. 893, from Aquarius
}
# Printed rows that disagree with the book's own benefic-house tables (see test below).
PRINTED_DISPUTED = {
    Graha.MOON: (2, [5, 3, 5, 4, 3, 6, 5, 2, 4, 5, 5, 4]),  # p. 886, sums to 51 (BPHS: 49)
    Graha.MERCURY: (10, [5, 4, 3, 5, 5, 5, 2, 6, 3, 6, 7, 5]),  # p. 889, sums to 56 (BPHS: 54)
    Graha.VENUS: (10, [4, 4, 5, 3, 6, 4, 3, 6, 6, 3, 5, 3]),  # p. 892, sums to 52
}
# Engine minus printed, by rashi 0..11, for the disputed rows. Moon/Mercury: the printed rows
# overshoot the totals the book itself states. Venus: one bindu printed in Virgo instead of Leo,
# which contradicts the book's own Venus house table on p. 862 (cause not identified).
KNOWN_DEVIATION = {
    Graha.MOON: (0, -1, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0),
    Graha.MERCURY: (0, -1, 0, 0, 0, 0, -1, 0, 0, -1, 0, 1),
    Graha.VENUS: (0, 0, 0, 0, 1, -1, 0, 0, 0, 0, 0, 0),
}

ZERO = {k: 0 for k in EXAMPLE}


def _by_rashi(printed: tuple[int, list[int]]) -> tuple[int, ...]:
    start, rows = printed
    return tuple(rows[(r - start) % 12] for r in range(12))


def test_contributor_counts() -> None:
    table = json.loads(
        resources.files("vedic_engine").joinpath("data/ashtakavarga_bphs.json").read_text("utf-8")
    )
    counts = {c: len(h) for c, h in table["sun"].items()}
    assert counts == {
        "sun": 8,
        "moon": 4,
        "mars": 8,
        "mercury": 7,
        "jupiter": 4,
        "venus": 3,
        "saturn": 8,
        "lagna": 6,
    }


def test_bav_totals() -> None:
    result = bav(EXAMPLE)
    totals = [sum(result[g]) for g in SEVEN]
    assert totals == [48, 49, 39, 54, 56, 52, 39]


def test_bav_indexed_by_rashi_not_house() -> None:
    base = bav(ZERO)
    shifted = bav({k: 3 for k in ZERO})
    for g in SEVEN:
        assert shifted[g] == base[g][-3:] + base[g][:-3]


@pytest.mark.parametrize("graha", list(PRINTED))
def test_bphs_example(graha: Graha) -> None:
    assert bav(EXAMPLE)[graha] == _by_rashi(PRINTED[graha])


@pytest.mark.parametrize("graha", list(PRINTED_DISPUTED))
def test_bphs_example_disputed_rows(graha: Graha) -> None:
    printed = _by_rashi(PRINTED_DISPUTED[graha])
    diff = tuple(a - b for a, b in zip(bav(EXAMPLE)[graha], printed, strict=True))
    assert diff == KNOWN_DEVIATION[graha]


def test_sav_example_total() -> None:
    assert sum(sav(bav(EXAMPLE))) == 337
