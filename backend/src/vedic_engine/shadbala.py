"""Shadbala, the six-fold planetary strength (BPHS Ch 27; spec 5.9), Sun to Saturn.

School ``SCHOOL`` = "raman-1942": BPHS Ch 27 as worked by B. V. Raman, *Graha and Bhava Balas*
(2nd ed., Raman Publications, Bangalore, 1942), whose fully worked "Standard Horoscope" is the
golden reference (fixtures/golden/shadbala_bphs_example.json). Santhanam's BPHS translation has
no complete worked chart. Where Raman's working differs from Santhanam's BPHS notes, Raman is
followed, because his example is what the engine is verified against:

* Saptavargaja: 45 moolatrikona (rasi only), 30 own, 22.5 great friend, 15 friend, 7.5
  neutral, 3.75 enemy, 1.875 great enemy (Santhanam: 20/15/10/4/2 for the last five).
* Cheshta: Sun and Moon get none (Raman Art. 79, 136; Santhanam v.18: Sun's = Ayana bala,
  Moon's = Paksha bala). Mars to Saturn use Raman's mean longitudes and seeghrochchas
  (Kedarnath Dutt's tables, Raman Tables IV-IX).
* Ayana: Kesava's (24 +/- kranti) / 48 x 60 with Raman's tabular kranti (max 24 deg); the Sun's
  is doubled (Santhanam: 23 deg 27' form).
* Yuddha: planets within 1 deg, the lesser longitude wins, and the difference of (sthana + dig +
  kaala up to hora) divided by the difference of disc diameters moves between them (Raman
  Art. 76-77; Santhanam v.20 moves the Shadbala difference itself).
* Drik: one quarter of the net aspect (dristi pinda) for every aspecting planet, with the
  special aspects of Mars (15), Jupiter (30) and Saturn (45) added (Santhanam v.19 adds the
  whole aspect of Mercury and Jupiter).
* Required strength follows BPHS v.32-33 (Sun 6.5 rupa; Raman Art. 122 says 5).

All strengths are in virupas (shashtiamsas); 60 virupas make a rupa.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

from vedic_engine import ephemeris
from vedic_engine.angles import arc, deg_in_sign, norm, sign_of
from vedic_engine.constants import RASHI_LORD, SEVEN, Graha
from vedic_engine.dignity import Dignity, dignity, natural_relation, temporal_relation
from vedic_engine.models import EngineWarning, Settings
from vedic_engine.timeutil import utc_from_jd
from vedic_engine.varga import varga_sign

SCHOOL = "raman-1942"

REQUIRED_RUPA: dict[Graha, float] = {
    Graha.SUN: 6.5, Graha.MOON: 6.0, Graha.MARS: 5.0, Graha.MERCURY: 7.0,
    Graha.JUPITER: 6.5, Graha.VENUS: 5.5, Graha.SATURN: 5.0,
}  # fmt: skip

STAR_PLANETS: tuple[Graha, ...] = SEVEN[2:]  # Mars to Saturn (taara grahas)

# Deep debilitation points (BPHS Ch 3; Raman Example 3).
_DEBILITATION: dict[Graha, float] = {
    Graha.SUN: 190.0, Graha.MOON: 213.0, Graha.MARS: 118.0, Graha.MERCURY: 345.0,
    Graha.JUPITER: 275.0, Graha.VENUS: 177.0, Graha.SATURN: 20.0,
}  # fmt: skip

_SAPTAVARGAS: tuple[int, ...] = (1, 2, 3, 7, 9, 12, 30)
_COMPOUND_VIRUPA: dict[tuple[str, str], float] = {
    ("friend", "friend"): 22.5,
    ("neutral", "friend"): 15.0,
    ("friend", "enemy"): 7.5,
    ("enemy", "friend"): 7.5,
    ("neutral", "enemy"): 3.75,
    ("enemy", "enemy"): 1.875,
}

_MALE = (Graha.SUN, Graha.MARS, Graha.JUPITER)
_FEMALE = (Graha.MOON, Graha.VENUS)

_DAY_THIRDS = (Graha.MERCURY, Graha.SUN, Graha.SATURN)
_NIGHT_THIRDS = (Graha.MOON, Graha.VENUS, Graha.MARS)

_WEEKDAY_LORD = (
    Graha.SUN, Graha.MOON, Graha.MARS, Graha.MERCURY, Graha.JUPITER, Graha.VENUS, Graha.SATURN,
)  # fmt: skip  # Sunday first
_WEDNESDAY = 3
_HORA_ORDER = (
    Graha.SATURN, Graha.JUPITER, Graha.MARS, Graha.SUN, Graha.VENUS, Graha.MERCURY, Graha.MOON,
)  # fmt: skip

# Raman Art. 73: declination gained in each successive 15 deg of bhuja, in arc-minutes.
_KRANTI_STEPS: tuple[float, ...] = (362.0, 341.0, 299.0, 236.0, 150.0, 52.0)

_DISC_DIAMETER: dict[Graha, float] = {  # Raman Art. 77, arc-seconds
    Graha.MARS: 9.4, Graha.MERCURY: 6.6, Graha.JUPITER: 190.4,
    Graha.VENUS: 16.6, Graha.SATURN: 158.0,
}  # fmt: skip

_VISESHA: dict[Graha, tuple[float, tuple[tuple[float, float], ...]]] = {
    Graha.MARS: (15.0, ((90.0, 120.0), (210.0, 240.0))),
    Graha.JUPITER: (30.0, ((120.0, 150.0), (240.0, 270.0))),
    Graha.SATURN: (45.0, ((60.0, 90.0), (270.0, 300.0))),
}

# Raman's condensed ahargana: days since 1 Jan 1900 plus this constant (Art. 64).
_AHARGANA_1900 = 26543
_EPOCH_1900 = date(1900, 1, 1)
# Mean-position epoch: 1 Jan 1900, 0h at 76 deg E (Ujjain mean midnight, Art. 88-90).
_MEAN_EPOCH_JD = 2415020.5 - 76.0 / 360.0

# (epoch longitude, degrees per day) from Raman Tables IV-IX; each rate is the table's
# 90,000-day entry plus its whole turns, divided by 90,000.
_MEAN_SUN = (257.4568, (144.2389 + 246 * 360.0) / 90000.0)
_MEAN_MARS = (270.22, (1.74 + 131 * 360.0) / 90000.0)
_MEAN_JUPITER = (220.04, (278.67 + 20 * 360.0) / 90000.0)
_MEAN_SATURN = (236.74, (129.54 + 8 * 360.0) / 90000.0)
_SIGHRA_MERCURY = (164.0, (28.63 + 1023 * 360.0) / 90000.0)
_SIGHRA_VENUS = (328.51, (193.18 + 400 * 360.0) / 90000.0)

_MINUTE = 1.0 / 1440.0


@dataclass(frozen=True, slots=True)
class ShadbalaRow:
    sthana: float
    dig: float
    kaala: float
    cheshta: float
    naisargika: float
    drik: float
    total_virupa: float
    total_rupa: float
    required_rupa: float
    ratio: float
    components: dict[str, float]


@dataclass(frozen=True, slots=True)
class ShadbalaInputs:
    """Everything Shadbala needs, in the form a worked example prints it.

    ``lon``: sidereal longitudes, Sun to Saturn. ``asc``/``mc``: sidereal ascendant and
    midheaven. ``ayanamsa``: added to ``lon`` for declinations. ``apparent_hours``: local
    apparent time in hours from apparent midnight. ``is_day``: born between sunrise and sunset.
    ``part_elapsed``: fraction (0-1) of that day or night already elapsed. ``hours_from_sunrise``:
    hours since the sunrise that began the Hindu day. ``ahargana``: Raman's condensed ahargana of
    that day. ``mean_lon``/``seeghrochcha``: Raman mean longitude and seeghrochcha, Mars to Saturn.
    """

    lon: Mapping[Graha, float]
    asc: float
    mc: float
    ayanamsa: float
    apparent_hours: float
    is_day: bool
    part_elapsed: float
    hours_from_sunrise: float
    ahargana: int
    mean_lon: Mapping[Graha, float]
    seeghrochcha: Mapping[Graha, float]


def _reduced(deg: float) -> float:
    """Angular separation folded into [0, 180]."""
    d = norm(deg)
    return 360.0 - d if d > 180.0 else d


# --- Sthana bala ---------------------------------------------------------------------------


def _uchcha(graha: Graha, lon: float) -> float:
    """Uchcha bala. BPHS 27.1: (longitude - deep debilitation), folded to 180, divided by 3."""
    return _reduced(lon - _DEBILITATION[graha]) / 3.0


def _relation_virupa(graha: Graha, lord: Graha, lon: Mapping[Graha, float]) -> float:
    if lord == graha:
        return 30.0
    natural = natural_relation(graha, lord)
    temporal = temporal_relation(sign_of(lon[graha]), sign_of(lon[lord]))
    return _COMPOUND_VIRUPA[(natural, temporal)]


def _saptavargaja(graha: Graha, lon: Mapping[Graha, float]) -> float:
    """Saptavargaja bala. BPHS 27.2-4: value of the dispositor in each of the seven vargas.

    D1, D2, D3, D7, D9, D12 and D30. Relationships are the compound ones of the rasi chart.
    Moolatrikona (45) counts in the rasi only (Raman Art. 30).
    """
    total = 0.0
    for n in _SAPTAVARGAS:
        if n == 1 and dignity(graha, lon[graha], lon) is Dignity.MOOLATRIKONA:
            total += 45.0
            continue
        total += _relation_virupa(graha, RASHI_LORD[varga_sign(lon[graha], n)], lon)
    return total


def _ojhayugma(graha: Graha, lon: float) -> float:
    """Ojhayugmarasyamsa bala. BPHS 27.4-5: 15 each for an odd/even rasi and navamsa.

    The Moon and Venus gain in even signs, the others in odd signs.
    """
    wants_even = graha in _FEMALE
    total = 0.0
    for sign in (sign_of(lon), varga_sign(lon, 9)):
        is_even = sign % 2 == 1
        total += 15.0 if is_even == wants_even else 0.0
    return total


def _kendradi(lon: float, asc: float) -> float:
    """Kendradi bala. BPHS 27.5: 60 in a kendra, 30 in a panaphara, 15 in an apoklima.

    Houses are counted in signs from the lagna sign (Raman Art. 33).
    """
    house = (sign_of(lon) - sign_of(asc)) % 12
    return (60.0, 30.0, 15.0)[house % 3]


def _drekkana(graha: Graha, lon: float) -> float:
    """Drekkana bala. BPHS 27.6: 15 to male planets in the first, female in the second and
    neuter (Mercury, Saturn) in the third drekkana. Raman's p. 26 table follows this order.
    """
    part = min(int(deg_in_sign(lon) // 10.0), 2)
    wanted = 0 if graha in _MALE else 1 if graha in _FEMALE else 2
    return 15.0 if part == wanted else 0.0


# --- Dig bala ------------------------------------------------------------------------------


def _dig(graha: Graha, lon: float, asc: float, mc: float) -> float:
    """Dig bala. BPHS 27.7-13: distance from the powerless point, folded to 180, over 3.

    Powerless points: nadir for the Sun and Mars, descendant for Jupiter and Mercury,
    midheaven for the Moon and Venus, ascendant for Saturn.
    """
    if graha in (Graha.SUN, Graha.MARS):
        powerless = mc + 180.0
    elif graha in (Graha.JUPITER, Graha.MERCURY):
        powerless = asc + 180.0
    elif graha in (Graha.MOON, Graha.VENUS):
        powerless = mc
    else:
        powerless = asc
    return _reduced(lon - powerless) / 3.0


# --- Kaala bala ----------------------------------------------------------------------------


def _natonnata(graha: Graha, apparent_hours: float) -> float:
    """Natonnata (divaratri) bala. BPHS 27.8-9.

    Time from apparent midnight at 15 deg an hour, folded to 180, over 3, is the day strength
    of the Sun, Jupiter and Venus; 60 minus it is the night strength of the Moon, Mars and
    Saturn; Mercury always has 60 (Raman Art. 51, method B).
    """
    if graha is Graha.MERCURY:
        return 60.0
    diva = _reduced(apparent_hours * 15.0) / 3.0
    return diva if graha in (Graha.SUN, Graha.JUPITER, Graha.VENUS) else 60.0 - diva


def _moon_is_benefic(lon: Mapping[Graha, float]) -> bool:
    """Benefic from the 8th tithi of the bright half to the 8th of the dark half (Raman
    Art. 53): reduced Moon - Sun elongation of at least 84 deg."""
    return _reduced(lon[Graha.MOON] - lon[Graha.SUN]) >= 84.0


def _mercury_is_benefic(lon: Mapping[Graha, float]) -> bool:
    """Mercury turns malefic in the same sign as a malefic (BPHS 27.10-11 note; Raman Art. 53
    "afflicted Budha"): the Sun, Mars, Saturn or a malefic Moon. Nodes are not counted."""
    malefics = [Graha.SUN, Graha.MARS, Graha.SATURN]
    if not _moon_is_benefic(lon):
        malefics.append(Graha.MOON)
    return all(sign_of(lon[m]) != sign_of(lon[Graha.MERCURY]) for m in malefics)


def _is_benefic(graha: Graha, lon: Mapping[Graha, float]) -> bool:
    if graha is Graha.MOON:
        return _moon_is_benefic(lon)
    if graha is Graha.MERCURY:
        return _mercury_is_benefic(lon)
    return graha in (Graha.JUPITER, Graha.VENUS)


def _paksha(graha: Graha, lon: Mapping[Graha, float]) -> float:
    """Paksha bala. BPHS 27.10-11: (Moon - Sun, folded to 180) / 3 for benefics, 60 minus that
    for malefics; the Moon's own value is doubled (Raman Art. 55, rules a-c).

    A malefic Moon takes the malefic value, doubled: Raman p. 34 (Art. 53) makes the Moon a
    malefic outside the 8th bright to 8th dark tithi, and p. 35 rule (c) doubles her value
    "always"; Santhanam's note to 27.10-11 (p. 269) doubles it "whether the Moon is in a group
    of benefics or otherwise". So a Moon 30 deg from the Sun scores 2 x (60 - 10) = 100."""
    benefic = _reduced(lon[Graha.MOON] - lon[Graha.SUN]) / 3.0
    value = benefic if _is_benefic(graha, lon) else 60.0 - benefic
    return 2.0 * value if graha is Graha.MOON else value


def _tribhaga(graha: Graha, is_day: bool, part_elapsed: float) -> float:
    """Tribhaga bala. BPHS 27.12: 60 to the lord of the third of the day (Mercury, Sun,
    Saturn) or night (Moon, Venus, Mars) in which birth falls; Jupiter always has 60."""
    if graha is Graha.JUPITER:
        return 60.0
    third = min(int(part_elapsed * 3.0), 2)
    return 60.0 if (_DAY_THIRDS if is_day else _NIGHT_THIRDS)[third] is graha else 0.0


def _weekday_counted_from_wednesday(remainder: int) -> Graha:
    """Raman Art. 63: a remainder r counts r days from Wednesday (r = 1 is Wednesday)."""
    return _WEEKDAY_LORD[(_WEDNESDAY + remainder - 1) % 7]


def ahargana(day: date) -> int:
    """Raman's condensed ahargana of a civil (sunrise-to-sunrise) day (Art. 63-64)."""
    return (day - _EPOCH_1900).days + _AHARGANA_1900


def ahargana_lords(ahargana_days: int) -> tuple[Graha, Graha, Graha]:
    """(year, month, weekday) lords from the ahargana: 360-day years and 30-day months whose
    first weekday advances by 3 and 2 days (BPHS 27.13; Raman Art. 60-62)."""
    year = _weekday_counted_from_wednesday((ahargana_days // 360 * 3 + 1) % 7)
    month = _weekday_counted_from_wednesday((ahargana_days // 30 * 2 + 1) % 7)
    day = _weekday_counted_from_wednesday(ahargana_days % 7)
    return year, month, day


def _abda(graha: Graha, ahargana_days: int) -> float:
    """Abda bala. BPHS 27.13: 15 to the lord of the (360-day) year."""
    return 15.0 if ahargana_lords(ahargana_days)[0] is graha else 0.0


def _masa(graha: Graha, ahargana_days: int) -> float:
    """Masa bala. BPHS 27.13: 30 to the lord of the (30-day) month."""
    return 30.0 if ahargana_lords(ahargana_days)[1] is graha else 0.0


def _vara(graha: Graha, ahargana_days: int) -> float:
    """Vara bala. BPHS 27.13: 45 to the lord of the weekday (sunrise to sunrise)."""
    return 45.0 if ahargana_lords(ahargana_days)[2] is graha else 0.0


def _hora(graha: Graha, ahargana_days: int, hours_from_sunrise: float) -> float:
    """Hora bala. BPHS 27.13: 60 to the lord of the planetary hour. The first hour after
    sunrise belongs to the weekday lord; each later one to the next in Saturn, Jupiter, Mars,
    Sun, Venus, Mercury, Moon order (Raman Art. 69-70, equal clock hours)."""
    day_lord = ahargana_lords(ahargana_days)[2]
    n = int(hours_from_sunrise // 1.0)
    lord = _HORA_ORDER[(_HORA_ORDER.index(day_lord) + n) % 7]
    return 60.0 if lord is graha else 0.0


def _kranti(bhuja: float) -> float:
    """Declination in degrees for a bhuja (0-90 deg from the nearest equinox), Raman Art. 73:
    362', 341', 299', 236', 150' and 52' over successive 15 deg, linear within each."""
    total = 0.0
    for i, step in enumerate(_KRANTI_STEPS):
        lo = 15.0 * i
        if bhuja <= lo:
            break
        total += step * min(bhuja - lo, 15.0) / 15.0
    return total / 60.0


def _ayana(graha: Graha, lon: float, ayanamsa: float) -> float:
    """Ayana bala. BPHS 27.15-17 (Kesava's form, Raman Art. 75): (24 +/- kranti) / 48 x 60.

    Kranti is from the sayana longitude. North declination adds for the Sun, Mars, Jupiter
    and Venus, south for the Moon and Saturn, either for Mercury. The Sun's is doubled.
    """
    sayana = norm(lon + ayanamsa)
    kranti = _kranti(90.0 - abs(90.0 - _reduced(sayana)))
    north = sayana < 180.0
    if graha is Graha.MERCURY:
        additive = True
    elif graha in (Graha.MOON, Graha.SATURN):
        additive = not north
    else:
        additive = north
    value = (24.0 + (kranti if additive else -kranti)) / 48.0 * 60.0
    return 2.0 * value if graha is Graha.SUN else value


def _yuddha(lon: Mapping[Graha, float], strength: Mapping[Graha, float]) -> dict[Graha, float]:
    """Yuddha bala. BPHS 27.20 (Raman Art. 76-77): star planets less than 1 deg apart are at
    war; the one with the lesser longitude wins. The difference of their ``strength`` (sthana +
    dig + kaala up to hora) divided by the difference of their disc diameters is added to the
    winner and taken from the loser."""
    out = {g: 0.0 for g in SEVEN}
    for i, a in enumerate(STAR_PLANETS):
        for b in STAR_PLANETS[i + 1 :]:
            if _reduced(lon[b] - lon[a]) >= 1.0:
                continue
            winner, loser = (a, b) if arc(lon[a], lon[b]) < 180.0 else (b, a)
            war = abs(strength[a] - strength[b]) / abs(_DISC_DIAMETER[a] - _DISC_DIAMETER[b])
            out[winner] += war
            out[loser] -= war
    return out


# --- Cheshta bala --------------------------------------------------------------------------


def raman_mean_positions(
    interval_days: float, year: int
) -> tuple[dict[Graha, float], dict[Graha, float]]:
    """Mean longitude and seeghrochcha, Mars to Saturn, from Raman's tables (Art. 88-104).

    ``interval_days``: days from 1 Jan 1900 0h at 76 deg E; ``year``: civil year of birth. The
    mean Sun is the seeghrochcha of Mars, Jupiter and Saturn and the mean longitude of Mercury
    and Venus, whose seeghrochchas have their own tables.
    """
    t = year - 1900

    def at(epoch_rate: tuple[float, float], correction: float = 0.0) -> float:
        epoch, rate = epoch_rate
        return norm(epoch + rate * interval_days + correction)

    sun = at(_MEAN_SUN)
    mean = {
        Graha.MARS: at(_MEAN_MARS),
        Graha.MERCURY: sun,
        Graha.JUPITER: at(_MEAN_JUPITER, -(3.33 + 0.0067 * t)),
        Graha.VENUS: sun,
        Graha.SATURN: at(_MEAN_SATURN, 5.0 + 0.001 * t),
    }
    sighra = {
        Graha.MARS: sun,
        Graha.MERCURY: at(_SIGHRA_MERCURY, 6.67 - 0.00133 * t),
        Graha.JUPITER: sun,
        Graha.VENUS: at(_SIGHRA_VENUS, -(5.0 + 0.001 * t)),
        Graha.SATURN: sun,
    }
    return mean, sighra


def _cheshta(graha: Graha, lon: float, mean: float, seeghrochcha: float) -> float:
    """Cheshta bala. BPHS 27.24-25: seeghrochcha minus the average of mean and true longitude
    is the cheshta kendra; folded to 180 and divided by 3. The Sun and Moon have none in this
    school (Raman Art. 79, 136)."""
    if graha in (Graha.SUN, Graha.MOON):
        return 0.0
    half = (norm(lon - mean + 180.0) - 180.0) / 2.0  # half the signed mean -> true distance
    return _reduced(seeghrochcha - (mean + half)) / 3.0


# --- Naisargika and Drik bala --------------------------------------------------------------


def naisargika(graha: Graha) -> float:
    """Naisargika bala. BPHS 27.14: 60/7 times 1..7 for Saturn, Mars, Mercury, Jupiter, Venus,
    Moon, Sun."""
    order = (Graha.SATURN, Graha.MARS, Graha.MERCURY, Graha.JUPITER, Graha.VENUS, Graha.MOON,
             Graha.SUN)  # fmt: skip
    return 60.0 * (order.index(graha) + 1) / 7.0


def _drishti(angle: float) -> float:
    """Ordinary aspect value for an aspect angle (aspected minus aspecting), Raman Art. 114."""
    k = norm(angle)
    if k < 30.0 or k >= 300.0:
        return 0.0
    if k < 60.0:
        return (k - 30.0) / 2.0
    if k < 90.0:
        return k - 60.0 + 15.0
    if k < 120.0:
        return (120.0 - k) / 2.0 + 30.0
    if k < 150.0:
        return 150.0 - k
    if k < 180.0:
        return (k - 150.0) * 2.0
    return (300.0 - k) / 2.0


def _drik(graha: Graha, lon: Mapping[Graha, float]) -> float:
    """Drik bala. BPHS 27.19 (Raman Art. 115-120): a quarter of the dristi pinda, the sum of
    benefic minus malefic aspects (with the special aspects of Mars, Jupiter and Saturn) on
    the planet."""
    pinda = 0.0
    for other in SEVEN:
        if other is graha:
            continue
        k = norm(lon[graha] - lon[other])
        value = _drishti(k)
        if other in _VISESHA:
            extra, ranges = _VISESHA[other]
            if any(lo <= k < hi for lo, hi in ranges):
                value += extra
        pinda += value if _is_benefic(other, lon) else -value
    return pinda / 4.0


# --- Assembly ------------------------------------------------------------------------------


def shadbala_from_inputs(inp: ShadbalaInputs) -> dict[Graha, ShadbalaRow]:
    """Shadbala of Sun to Saturn from fully prepared inputs (see ``ShadbalaInputs``)."""
    lon = inp.lon
    comps: dict[Graha, dict[str, float]] = {}
    for g in SEVEN:
        comps[g] = {
            "uchcha": _uchcha(g, lon[g]),
            "saptavargaja": _saptavargaja(g, lon),
            "ojhayugma": _ojhayugma(g, lon[g]),
            "kendradi": _kendradi(lon[g], inp.asc),
            "drekkana": _drekkana(g, lon[g]),
            "natonnata": _natonnata(g, inp.apparent_hours),
            "paksha": _paksha(g, lon),
            "tribhaga": _tribhaga(g, inp.is_day, inp.part_elapsed),
            "abda": _abda(g, inp.ahargana),
            "masa": _masa(g, inp.ahargana),
            "vara": _vara(g, inp.ahargana),
            "hora": _hora(g, inp.ahargana, inp.hours_from_sunrise),
            "ayana": _ayana(g, lon[g], inp.ayanamsa),
        }
    sthana_keys = ("uchcha", "saptavargaja", "ojhayugma", "kendradi", "drekkana")
    upto_hora = ("natonnata", "paksha", "tribhaga", "abda", "masa", "vara", "hora")
    dig = {g: _dig(g, lon[g], inp.asc, inp.mc) for g in SEVEN}
    war_strength = {g: sum(comps[g][k] for k in sthana_keys + upto_hora) + dig[g] for g in SEVEN}
    yuddha = _yuddha(lon, war_strength)

    rows: dict[Graha, ShadbalaRow] = {}
    for g in SEVEN:
        c = comps[g]
        c["yuddha"] = yuddha[g]
        sthana = sum(c[k] for k in sthana_keys)
        kaala = sum(c[k] for k in (*upto_hora, "ayana", "yuddha"))
        cheshta = (
            0.0
            if g not in STAR_PLANETS
            else _cheshta(g, lon[g], inp.mean_lon[g], inp.seeghrochcha[g])
        )
        nais = naisargika(g)
        drik = _drik(g, lon)
        total = sthana + dig[g] + kaala + cheshta + nais + drik
        rupa = total / 60.0
        rows[g] = ShadbalaRow(
            sthana=sthana,
            dig=dig[g],
            kaala=kaala,
            cheshta=cheshta,
            naisargika=nais,
            drik=drik,
            total_virupa=total,
            total_rupa=rupa,
            required_rupa=REQUIRED_RUPA[g],
            ratio=rupa / REQUIRED_RUPA[g],
            components=c,
        )
    return rows


_SUNRISE_SEARCH_WINDOWS = 3  # one-day rise_set windows tried before the Sun counts as polar


def _first_sun_event(
    start: float, kind: Literal["rise", "set"], lat: float, lon: float, settings: Settings
) -> float | None:
    """First sunrise/sunset at or after ``start``, searching up to three one-day windows.

    ``ephemeris.rise_set`` only reports an event inside [start, start + 1), and at high
    latitudes consecutive sunrises can be more than 24 h apart, so one window is not enough.
    Window starts are kept inside the supported range.
    """
    s = max(start, ephemeris.JD_MIN)
    for _ in range(_SUNRISE_SEARCH_WINDOWS):
        t = ephemeris.rise_set(min(s, ephemeris.JD_MAX), lat, lon, 0.0, "sun", kind, settings)
        if t is not None and t >= start:
            return t
        if s >= ephemeris.JD_MAX:
            return None
        s += 1.0
    return None


def _day_frame(
    jd_ut: float, lat: float, lon: float, settings: Settings
) -> tuple[bool, float, float, date, EngineWarning | None]:
    """(is_day, part_elapsed, hours_from_sunrise, civil date of that sunrise, warning).

    The Hindu day runs from the last sunrise at or before ``jd_ut`` to the next one. Only
    where those sunrises or the sunset between them do not exist (polar day or night, or the
    edge of the supported range) do 06:00 and 18:00 local mean time stand in for sunrise and
    sunset, and a warning says so.
    """

    def first(start: float, kind: Literal["rise", "set"]) -> float | None:
        return _first_sun_event(start, kind, lat, lon, settings)

    lmt_offset = lon / 360.0
    rise: float | None = None
    t = first(jd_ut - 2.0, "rise")
    while t is not None and t <= jd_ut:
        rise, t = t, first(t + _MINUTE, "rise")
    nxt = t
    sett = None if rise is None else first(rise, "set")
    warning = None
    if rise is None or nxt is None or sett is None or sett > nxt:
        rise = math.floor(jd_ut + lmt_offset - 0.75) + 0.75 - lmt_offset  # last 06:00 LMT
        sett, nxt = rise + 0.5, rise + 1.0
        at_edge = jd_ut - 2.0 < ephemeris.JD_MIN or jd_ut + 2.0 > ephemeris.JD_MAX
        warning = EngineWarning(
            "range_sunrise" if at_edge else "polar_sunrise",
            ("the sunrise before the birth lies outside the supported range"
             if at_edge else "the Sun does not rise or set around the birth (polar day or night)")
            + ": Shadbala time lords use 06:00 and 18:00 local mean time",
        )  # fmt: skip
    day = utc_from_jd(rise + lmt_offset).date()
    hours = (jd_ut - rise) * 24.0
    if jd_ut < sett:
        return True, (jd_ut - rise) / (sett - rise), hours, day, warning
    return False, (jd_ut - sett) / (nxt - sett), hours, day, warning


def shadbala_report(
    jd_ut: float, lat: float, lon: float, settings: Settings
) -> tuple[dict[Graha, ShadbalaRow], tuple[EngineWarning, ...]]:
    """Shadbala of Sun to Saturn with the warnings the kundli must surface (polar frame)."""
    pos = ephemeris.positions(jd_ut, settings)
    lons = {g: pos[g].lon for g in SEVEN}
    is_day, part, hours, day, warning = _day_frame(jd_ut, lat, lon, settings)
    apparent = jd_ut + lon / 360.0 + ephemeris.equation_of_time(jd_ut) + 0.5
    mean, sighra = raman_mean_positions(
        jd_ut - _MEAN_EPOCH_JD, utc_from_jd(jd_ut + lon / 360.0).year
    )
    inputs = ShadbalaInputs(
        lon=lons,
        asc=ephemeris.ascendant(jd_ut, lat, lon, settings),
        mc=ephemeris.midheaven(jd_ut, lat, lon, settings),
        ayanamsa=ephemeris.ayanamsa(jd_ut, settings),
        apparent_hours=(apparent % 1.0) * 24.0,
        is_day=is_day,
        part_elapsed=part,
        hours_from_sunrise=hours,
        ahargana=ahargana(day),
        mean_lon=mean,
        seeghrochcha=sighra,
    )
    return shadbala_from_inputs(inputs), (() if warning is None else (warning,))


def shadbala(jd_ut: float, lat: float, lon: float, settings: Settings) -> dict[Graha, ShadbalaRow]:
    """Shadbala of Sun to Saturn at ``jd_ut`` for geographic ``lat``/``lon`` (east positive).

    The brief's interface; callers that report warnings use ``shadbala_report``.
    """
    return shadbala_report(jd_ut, lat, lon, settings)[0]
