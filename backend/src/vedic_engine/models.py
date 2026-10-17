"""Input/output dataclasses and exceptions for the engine."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from vedic_engine.constants import Graha


class EngineError(Exception):
    """Base class for engine errors."""


class InputError(EngineError):
    """Invalid user input."""


class EphemerisRangeError(InputError):
    """Date outside the supported ephemeris range."""


@dataclass(frozen=True, slots=True)
class Settings:
    ayanamsa: Literal["LAHIRI", "RAMAN", "KP", "FAGAN_BRADLEY"] = "LAHIRI"
    node: Literal["MEAN", "TRUE"] = "MEAN"
    dasha_year_days: float = 365.25
    sunrise: Literal["UPPER_LIMB_REFRACTED", "CENTER_NO_REFRACTION"] = "UPPER_LIMB_REFRACTED"


@dataclass(frozen=True, slots=True)
class BirthInput:
    local: datetime  # naive local civil time
    tz: str  # IANA zone, or a fixed offset such as "UTC+05:53:20" / "UTC-04:00"
    lat: float
    lon: float
    alt: float = 0.0
    fold: int | None = None
    name: str | None = None
    time_known: bool = True  # False: Chandra kundli (noon positions, Moon as lagna)
    lmt: bool = False  # True: local mean time, a fixed offset of lon/15 h (``tz`` is ignored)


@dataclass(frozen=True, slots=True)
class GrahaPosition:
    graha: Graha
    lon: float
    lat: float
    speed: float
    retro: bool


@dataclass(frozen=True, slots=True)
class EngineWarning:
    code: str
    message: str
