"""Static astrological constants. All keys are stable lowercase machine keys."""

from enum import StrEnum


class Graha(StrEnum):
    SUN = "sun"
    MOON = "moon"
    MARS = "mars"
    MERCURY = "mercury"
    JUPITER = "jupiter"
    VENUS = "venus"
    SATURN = "saturn"
    RAHU = "rahu"
    KETU = "ketu"


SEVEN: tuple[Graha, ...] = (
    Graha.SUN,
    Graha.MOON,
    Graha.MARS,
    Graha.MERCURY,
    Graha.JUPITER,
    Graha.VENUS,
    Graha.SATURN,
)

RASHIS: tuple[str, ...] = (
    "mesha", "vrishabha", "mithuna", "karka", "simha", "kanya",
    "tula", "vrishchika", "dhanu", "makara", "kumbha", "meena",
)  # fmt: skip

RASHI_LORD: tuple[Graha, ...] = (
    Graha.MARS, Graha.VENUS, Graha.MERCURY, Graha.MOON, Graha.SUN, Graha.MERCURY,
    Graha.VENUS, Graha.MARS, Graha.JUPITER, Graha.SATURN, Graha.SATURN, Graha.JUPITER,
)  # fmt: skip

NAKSHATRAS: tuple[str, ...] = (
    "ashwini", "bharani", "krittika", "rohini", "mrigashira", "ardra",
    "punarvasu", "pushya", "ashlesha", "magha", "purva_phalguni", "uttara_phalguni",
    "hasta", "chitra", "swati", "vishakha", "anuradha", "jyeshtha",
    "mula", "purva_ashadha", "uttara_ashadha", "shravana", "dhanishta", "shatabhisha",
    "purva_bhadrapada", "uttara_bhadrapada", "revati",
)  # fmt: skip

VIMSHOTTARI_ORDER: tuple[Graha, ...] = (
    Graha.KETU, Graha.VENUS, Graha.SUN, Graha.MOON, Graha.MARS,
    Graha.RAHU, Graha.JUPITER, Graha.SATURN, Graha.MERCURY,
)  # fmt: skip

VIMSHOTTARI_YEARS: dict[Graha, int] = {
    Graha.KETU: 7,
    Graha.VENUS: 20,
    Graha.SUN: 6,
    Graha.MOON: 10,
    Graha.MARS: 7,
    Graha.RAHU: 18,
    Graha.JUPITER: 16,
    Graha.SATURN: 19,
    Graha.MERCURY: 17,
}

_TITHI_NAMES: tuple[str, ...] = (
    "pratipada", "dwitiya", "tritiya", "chaturthi", "panchami", "shashthi", "saptami",
    "ashtami", "navami", "dashami", "ekadashi", "dwadashi", "trayodashi", "chaturdashi",
)  # fmt: skip

TITHIS: tuple[str, ...] = (
    *(f"shukla_{n}" for n in _TITHI_NAMES),
    "purnima",
    *(f"krishna_{n}" for n in _TITHI_NAMES),
    "amavasya",
)

YOGAS: tuple[str, ...] = (
    "vishkambha", "priti", "ayushman", "saubhagya", "shobhana", "atiganda",
    "sukarma", "dhriti", "shula", "ganda", "vriddhi", "dhruva", "vyaghata",
    "harshana", "vajra", "siddhi", "vyatipata", "variyan", "parigha", "shiva",
    "siddha", "sadhya", "shubha", "shukla", "brahma", "indra", "vaidhriti",
)  # fmt: skip

KARANAS_MOVABLE: tuple[str, ...] = (
    "bava",
    "balava",
    "kaulava",
    "taitila",
    "gara",
    "vanija",
    "vishti",
)
KARANAS_FIXED: tuple[str, ...] = ("kimstughna", "shakuni", "chatushpada", "naga")

# Indexed by Python datetime.weekday() (Monday = 0).
VAARS: tuple[str, ...] = ("soma", "mangala", "budha", "guru", "shukra", "shani", "ravi")
