import pytest

from vedic_engine.constants import SEVEN, Graha
from vedic_engine.dignity import (
    NODE_DIGNITY_SCHOOL,
    Dignity,
    dignity,
    is_combust,
    natural_relation,
    temporal_relation,
)

G = Graha
EXALT = {G.SUN: (0, 10), G.MOON: (1, 3), G.MARS: (9, 28), G.MERCURY: (5, 15),
         G.JUPITER: (3, 5), G.VENUS: (11, 27), G.SATURN: (6, 20)}  # fmt: skip


def lon(sign: int, deg: float) -> float:
    return sign * 30.0 + deg


def pos(**signs: int) -> dict[Graha, float]:
    base = {g: lon(0, 1.0) for g in SEVEN}
    base.update({Graha(k): lon(v, 1.0) for k, v in signs.items()})
    return base


@pytest.mark.parametrize("g", SEVEN)
def test_exaltation_and_debilitation_points(g: Graha) -> None:
    sign, deg = EXALT[g]
    # Exact Moon (3) / Mercury (15) points are carved out as MOOLATRIKONA by spec 5.5.
    exalted_deg = {G.MOON: 2.9, G.MERCURY: 14.9}.get(g, deg)
    assert dignity(g, lon(sign, exalted_deg), pos()) == Dignity.EXALTED
    assert dignity(g, lon((sign + 6) % 12, deg), pos()) == Dignity.DEBILITATED


def test_moon_vrishabha_boundary() -> None:
    assert dignity(G.MOON, lon(1, 2.9), pos()) == Dignity.EXALTED
    assert dignity(G.MOON, lon(1, 3.0), pos()) == Dignity.MOOLATRIKONA


def test_mercury_kanya_ranges() -> None:
    assert dignity(G.MERCURY, lon(5, 14.9), pos()) == Dignity.EXALTED
    assert dignity(G.MERCURY, lon(5, 15.0), pos()) == Dignity.MOOLATRIKONA
    assert dignity(G.MERCURY, lon(5, 19.9), pos()) == Dignity.MOOLATRIKONA
    assert dignity(G.MERCURY, lon(5, 20.0), pos()) == Dignity.OWN
    assert dignity(G.MERCURY, lon(5, 21.0), pos()) == Dignity.OWN


def test_sun_mesha_always_exalted() -> None:
    for d in (0.0, 5.0, 10.0, 29.9):
        assert dignity(G.SUN, lon(0, d), pos()) == Dignity.EXALTED


def test_sun_simha() -> None:
    assert dignity(G.SUN, lon(4, 25.0), pos()) == Dignity.OWN
    assert dignity(G.SUN, lon(4, 19.9), pos()) == Dignity.MOOLATRIKONA


def test_other_moolatrikona_half_open() -> None:
    assert dignity(G.MARS, lon(0, 11.9), pos()) == Dignity.MOOLATRIKONA
    assert dignity(G.MARS, lon(0, 12.0), pos()) == Dignity.OWN
    assert dignity(G.JUPITER, lon(8, 9.9), pos()) == Dignity.MOOLATRIKONA
    assert dignity(G.JUPITER, lon(8, 10.0), pos()) == Dignity.OWN
    assert dignity(G.VENUS, lon(6, 14.9), pos()) == Dignity.MOOLATRIKONA
    assert dignity(G.VENUS, lon(6, 15.0), pos()) == Dignity.OWN
    assert dignity(G.SATURN, lon(10, 19.9), pos()) == Dignity.MOOLATRIKONA
    assert dignity(G.SATURN, lon(10, 20.0), pos()) == Dignity.OWN


def test_natural_relations() -> None:
    assert natural_relation(G.SUN, G.MOON) == "friend"
    assert natural_relation(G.SUN, G.SATURN) == "enemy"
    assert natural_relation(G.SUN, G.MERCURY) == "neutral"
    assert natural_relation(G.MERCURY, G.MOON) == "enemy"
    assert natural_relation(G.MOON, G.MERCURY) == "friend"


def test_natural_relation_nodes_raise() -> None:
    with pytest.raises(ValueError):
        natural_relation(G.RAHU, G.SUN)
    with pytest.raises(ValueError):
        natural_relation(G.SUN, G.KETU)


def test_temporal_relation() -> None:
    friends = {1, 2, 3, 9, 10, 11}
    for off in range(1, 12):
        assert temporal_relation(5, (5 + off) % 12) == ("friend" if off in friends else "enemy")
    assert temporal_relation(5, 5) == "enemy"


def test_compound_relationship_all_six() -> None:
    # Sun in Vrishabha (lord Venus: natural enemy). Venus placed 2nd from Sun -> friend.
    assert dignity(G.SUN, lon(1, 10), pos(sun=1, venus=2)) == Dignity.NEUTRAL
    # Venus in same sign as Sun -> temporal enemy -> great enemy.
    assert dignity(G.SUN, lon(1, 10), pos(sun=1, venus=1)) == Dignity.GREAT_ENEMY
    # Sun in Mithuna (lord Mercury: neutral). Mercury 2nd -> friend; same sign -> enemy.
    assert dignity(G.SUN, lon(2, 10), pos(sun=2, mercury=3)) == Dignity.FRIEND
    assert dignity(G.SUN, lon(2, 10), pos(sun=2, mercury=2)) == Dignity.ENEMY
    # Sun in Dhanu (lord Jupiter: friend). Jupiter 2nd -> great friend; same sign -> neutral.
    assert dignity(G.SUN, lon(8, 10), pos(sun=8, jupiter=9)) == Dignity.GREAT_FRIEND
    assert dignity(G.SUN, lon(8, 10), pos(sun=8, jupiter=8)) == Dignity.NEUTRAL


def test_sign_lord_relationship_uses_graha_position_not_input_lon_sign() -> None:
    # Mars in Mithuna (Mercury, natural enemy of Mars). Mercury 7th from Mars -> enemy.
    assert dignity(G.MARS, lon(2, 10), pos(mars=2, mercury=8)) == Dignity.GREAT_ENEMY


def test_nodes() -> None:
    assert NODE_DIGNITY_SCHOOL["rahu"]["exalted"] == 1
    assert dignity(G.RAHU, lon(1, 5), pos()) == Dignity.EXALTED
    assert dignity(G.RAHU, lon(7, 5), pos()) == Dignity.DEBILITATED
    assert dignity(G.RAHU, lon(3, 5), pos()) == Dignity.NEUTRAL
    assert dignity(G.KETU, lon(7, 5), pos()) == Dignity.EXALTED
    assert dignity(G.KETU, lon(1, 5), pos()) == Dignity.DEBILITATED
    assert dignity(G.KETU, lon(3, 5), pos()) == Dignity.NEUTRAL


def test_combustion() -> None:
    assert is_combust(G.MERCURY, 113.0, 100.0, False) is True
    assert is_combust(G.MERCURY, 113.0, 100.0, True) is False
    assert is_combust(G.MERCURY, 112.0, 100.0, True) is True
    assert is_combust(G.VENUS, 109.0, 100.0, False) is True
    assert is_combust(G.VENUS, 109.0, 100.0, True) is False
    assert is_combust(G.MARS, 118.0, 100.0, False) is False
    assert is_combust(G.MARS, 83.5, 100.0, False) is True
    assert is_combust(G.MOON, 5.0, 355.0, False) is True  # wraps across 0
    assert is_combust(G.JUPITER, 112.0, 100.0, False) is False
    assert is_combust(G.SATURN, 115.0, 100.0, False) is True


def test_combustion_never_for_sun_and_nodes() -> None:
    for g in (G.SUN, G.RAHU, G.KETU):
        assert is_combust(g, 100.0, 100.0, False) is False
