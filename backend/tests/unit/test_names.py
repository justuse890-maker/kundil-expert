"""Nakshatra-pada name syllables (spec 5.12)."""

import pytest

from vedic_engine.constants import NAKSHATRAS
from vedic_engine.names import SYLLABLES, syllable

PUNARVASU, CHITRA, ASHWINI = (NAKSHATRAS.index(n) for n in ("punarvasu", "chitra", "ashwini"))


def test_syllables() -> None:
    assert syllable(PUNARVASU, 4) == ("Hi", "ही")
    assert syllable(CHITRA, 3) == ("Ra", "रा")
    assert syllable(ASHWINI, 1) == ("Chu", "चु")


def test_punarvasu_padas_match_spec_correction_4() -> None:
    assert [syllable(PUNARVASU, p)[0] for p in range(1, 5)] == ["Ke", "Ko", "Ha", "Hi"]


def test_table_has_108_entries() -> None:
    assert len(SYLLABLES) == 27
    assert all(len(row) == 4 for row in SYLLABLES)
    for row in SYLLABLES:
        for latin, devanagari in row:
            assert latin and latin.isascii()
            assert devanagari and all("ऀ" <= ch <= "ॿ" for ch in devanagari)


def test_last_entry() -> None:
    assert syllable(26, 4) == ("Chi", "ची")


@pytest.mark.parametrize(("nak", "pada"), [(-1, 1), (27, 1), (0, 0), (0, 5)])
def test_out_of_range_rejected(nak: int, pada: int) -> None:
    with pytest.raises(ValueError):
        syllable(nak, pada)
