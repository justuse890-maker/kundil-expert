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
# Venus is deliberately not here: see KNOWN_DEVIATION.
# Printed rows that disagree with the book's own benefic-house tables (see test below).
PRINTED_DISPUTED = {
    Graha.MOON: (2, [5, 3, 5, 4, 3, 6, 5, 2, 4, 5, 5, 4]),  # p. 886, sums to 51 (BPHS: 49)
    Graha.MERCURY: (10, [5, 4, 3, 5, 5, 5, 2, 6, 3, 6, 7, 5]),  # p. 889, sums to 56 (BPHS: 54)
    Graha.VENUS: (10, [4, 4, 5, 3, 6, 4, 3, 6, 6, 3, 5, 3]),  # p. 892, sums to 52
}
# Engine minus printed, by rashi 0..11, for the disputed rows.
# Moon and Mercury: the printed rows sum to 51 and 56, contradicting the 49 and 54 that the
# book's own tables and rekha charts (pp. 856, 859) give.
# Venus: the printed row has one bindu in Virgo where the engine has it in Leo. It is exactly
# reproduced if Mars's benefic houses from Venus are 3,5,6,9,11,12 (the usual Parashari list),
# but the scan's verse 56-58 (English and Sanskrit "jna-varjita"), its rekha chart (p. 861) and
# its house table (p. 862) all give Mars in the 4th, so the engine follows the scan.
KNOWN_DEVIATION = {
    Graha.MOON: (0, -1, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0),
    Graha.MERCURY: (0, 0, 0, 0, 0, 0, -1, 0, 0, -1, 0, 0),
    Graha.VENUS: (0, 0, 0, 0, 1, -1, 0, 0, 0, 0, 0, 0),
}

# Golden table: every benefic-house list, typed independently of the JSON.
# Santhanam BPHS Vol 2 Ch 66 v.43-60 (pp. 854-863); layout {target: {contributor: houses}}.
GOLDEN = {
    "sun": {
        "sun": [1, 2, 4, 7, 8, 9, 10, 11],
        "moon": [3, 6, 10, 11],
        "mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "mercury": [3, 5, 6, 9, 10, 11, 12],
        "jupiter": [5, 6, 9, 11],
        "venus": [6, 7, 12],
        "saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "lagna": [3, 4, 6, 10, 11, 12],
    },
    "moon": {
        "sun": [3, 6, 7, 8, 10, 11],
        "moon": [1, 3, 6, 7, 9, 10, 11],
        "mars": [2, 3, 5, 6, 10, 11],
        "mercury": [1, 3, 4, 5, 7, 8, 10, 11],
        "jupiter": [1, 2, 4, 7, 8, 10, 11],
        "venus": [3, 4, 5, 7, 9, 10, 11],
        "saturn": [3, 5, 6, 11],
        "lagna": [3, 6, 10, 11],
    },
    "mars": {
        "sun": [3, 5, 6, 10, 11],
        "moon": [3, 6, 11],
        "mars": [1, 2, 4, 7, 8, 10, 11],
        "mercury": [3, 5, 6, 11],
        "jupiter": [6, 10, 11, 12],
        "venus": [6, 8, 11, 12],
        "saturn": [1, 4, 7, 8, 9, 10, 11],
        "lagna": [1, 3, 6, 10, 11],
    },
    "mercury": {
        "sun": [5, 6, 9, 11, 12],
        "moon": [2, 4, 6, 8, 10, 11],
        "mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "mercury": [1, 3, 5, 6, 9, 10, 11, 12],
        "jupiter": [6, 8, 11, 12],
        "venus": [1, 2, 3, 4, 5, 8, 9, 11],
        "saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "lagna": [1, 2, 4, 6, 8, 10, 11],
    },
    "jupiter": {
        "sun": [1, 2, 3, 4, 7, 8, 9, 10, 11],
        "moon": [2, 5, 7, 9, 11],
        "mars": [1, 2, 4, 7, 8, 10, 11],
        "mercury": [1, 2, 4, 5, 6, 9, 10, 11],
        "jupiter": [1, 2, 3, 4, 7, 8, 10, 11],
        "venus": [2, 5, 6, 9, 10, 11],
        "saturn": [3, 5, 6, 12],
        "lagna": [1, 2, 4, 5, 6, 7, 9, 10, 11],
    },
    "venus": {
        "sun": [8, 11, 12],
        "moon": [1, 2, 3, 4, 5, 8, 9, 11, 12],
        "mars": [3, 4, 6, 9, 11, 12],
        "mercury": [3, 5, 6, 9, 11],
        "jupiter": [5, 8, 9, 10, 11],
        "venus": [1, 2, 3, 4, 5, 8, 9, 10, 11],
        "saturn": [3, 4, 5, 8, 9, 10, 11],
        "lagna": [1, 2, 3, 4, 5, 8, 9, 11],
    },
    "saturn": {
        "sun": [1, 2, 4, 7, 8, 10, 11],
        "moon": [3, 6, 11],
        "mars": [3, 5, 6, 10, 11, 12],
        "mercury": [6, 8, 9, 10, 11, 12],
        "jupiter": [5, 6, 11, 12],
        "venus": [6, 11, 12],
        "saturn": [3, 5, 6, 11],
        "lagna": [1, 3, 4, 6, 10, 11],
    },
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


def test_golden_house_lists() -> None:
    raw = json.loads(
        resources.files("vedic_engine").joinpath("data/ashtakavarga_bphs.json").read_text("utf-8")
    )
    actual = {t: {c: raw[t][c] for c in GOLDEN[t]} for t in GOLDEN}
    assert actual == GOLDEN


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


def test_golden_contributor_counts() -> None:
    order = ["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "lagna"]
    expected = {
        "sun": [8, 4, 8, 7, 4, 3, 8, 6],
        "moon": [6, 7, 6, 8, 7, 7, 4, 4],
        "mars": [5, 3, 7, 4, 4, 4, 7, 5],
        "mercury": [5, 6, 8, 8, 4, 8, 8, 7],
        "jupiter": [9, 5, 7, 8, 8, 6, 4, 9],
        "venus": [3, 9, 6, 5, 5, 9, 7, 8],
        "saturn": [7, 3, 6, 6, 4, 3, 4, 6],
    }
    for target, counts in expected.items():
        assert [len(GOLDEN[target][c]) for c in order] == counts
