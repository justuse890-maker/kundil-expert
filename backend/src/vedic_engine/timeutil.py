"""Civil local time + IANA timezone -> UTC -> Julian day (UT).

Wrong timezones are the most common cause of wrong charts, so nonexistent (DST gap) and
ambiguous (DST overlap) local times are rejected rather than guessed.
"""

import math
import re
from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, reset_tzpath

from vedic_engine.models import BirthInput, InputError

# Pin tz data to the `tzdata` package (locked in uv.lock): an empty search path makes
# zoneinfo skip the OS tz database, so the same input gives the same output on any machine.
reset_tzpath(to=())


class NonexistentTimeError(InputError):
    """Local time falls in a DST gap and never occurred."""


class AmbiguousTimeError(InputError):
    """Local time occurred twice (DST overlap) and no fold was given."""


class UnknownTimezoneError(InputError):
    """Not a known IANA timezone."""


_OFFSET = re.compile(r"UTC([+-])(\d{2}):(\d{2})(?::(\d{2}(?:\.\d{1,6})?))?")
_HOURS_PER_DAY = 24


def fixed_offset(tz: str) -> timezone | None:
    """The fixed-offset zone of ``"UTC+HH:MM[:SS[.fff]]"`` / ``"UTC-HH:MM"``, else ``None``.

    A string that starts like an offset but is malformed or out of range raises InputError.
    """
    if not tz.startswith(("UTC+", "UTC-")):
        return None
    match = _OFFSET.fullmatch(tz)
    if match is None:
        raise InputError(f"malformed UTC offset {tz!r}; expected UTC+HH:MM[:SS], e.g. UTC+05:53:20")
    sign, hh, mm, ss = match.groups()
    hours, minutes, seconds = int(hh), int(mm), float(ss or 0)
    if hours >= _HOURS_PER_DAY or minutes >= 60 or seconds >= 60:
        raise InputError(f"UTC offset {tz!r} out of range")
    delta = timedelta(hours=hours, minutes=minutes, seconds=seconds)
    return timezone(-delta if sign == "-" else delta)


def lmt_offset(lon: float) -> timedelta:
    """Local mean time offset of east-positive longitude ``lon``: lon/15 hours (ms resolution)."""
    if not -180.0 <= lon <= 180.0:
        raise InputError(f"longitude {lon} outside -180..180")
    return timedelta(milliseconds=round(lon / 15.0 * 3_600_000))


def lmt_tz(lon: float) -> str:
    """The fixed-offset ``tz`` string of local mean time at ``lon``, e.g. ``UTC+05:53:27.340``."""
    ms = round(lmt_offset(lon) / timedelta(milliseconds=1))
    sign = "-" if ms < 0 else "+"
    total_s, milli = divmod(abs(ms), 1000)
    minutes, sec = divmod(total_s, 60)
    hour, minute = divmod(minutes, 60)
    return f"UTC{sign}{hour:02d}:{minute:02d}:{sec:02d}.{milli:03d}"


def effective_tz(birth: BirthInput) -> str:
    """The ``tz`` string to convert ``birth`` with: LMT (lon/15 h) when ``birth.lmt``."""
    return lmt_tz(birth.lon) if birth.lmt else birth.tz


def birth_utc(birth: BirthInput) -> datetime:
    """Aware UTC instant of ``birth`` (IANA zone, fixed offset or LMT)."""
    return to_utc(birth.local, effective_tz(birth), birth.fold)


def _zone(tz: str) -> ZoneInfo | timezone:
    fixed = fixed_offset(tz)
    if fixed is not None:
        return fixed
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
        raise UnknownTimezoneError(f"unknown timezone: {tz!r}") from exc


def to_utc(local: datetime, tz: str, fold: int | None = None) -> datetime:
    """Convert naive civil ``local`` time in IANA zone ``tz`` to an aware UTC datetime."""
    if local.tzinfo is not None:
        raise InputError("local time must be naive (no tzinfo)")
    if fold not in (None, 0, 1):
        raise InputError(f"fold must be 0, 1 or None, got {fold!r}")
    zone = _zone(tz)
    if isinstance(zone, timezone):
        try:
            return local.replace(tzinfo=zone).astimezone(UTC)
        except (OverflowError, ValueError) as exc:
            raise InputError(f"local time {local} out of representable range in {tz}") from exc
    try:
        base = local.replace(fold=0)
        first = base.replace(tzinfo=zone)
        second = base.replace(fold=1, tzinfo=zone)

        # Nonexistent: converting to UTC and back does not reproduce the wall time.
        roundtrip = first.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
        if roundtrip != base:
            raise NonexistentTimeError(f"{local} does not exist in {tz} (DST gap)")

        if first.utcoffset() != second.utcoffset():
            if fold is None:
                raise AmbiguousTimeError(f"{local} is ambiguous in {tz}; specify fold=0 or fold=1")
            chosen = second if fold == 1 else first
        else:
            chosen = first
        return chosen.astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise InputError(f"local time {local} out of representable range in {tz}") from exc


def to_local(dt_utc: datetime, tz: str) -> datetime:
    """Convert an aware datetime to the aware local time in IANA zone ``tz``."""
    if dt_utc.tzinfo is None:
        raise InputError("datetime must be timezone-aware")
    zone = _zone(tz)
    try:
        return dt_utc.astimezone(zone)
    except (OverflowError, ValueError) as exc:
        raise InputError(f"datetime {dt_utc} out of representable range in {tz}") from exc


def _gregorian_jd(year: int, month: int, day: int) -> float:
    """Julian day at 0h UT of a Gregorian date (Meeus, Astronomical Algorithms, ch. 7)."""
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return float(int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b) - 1524.5


_MIDNIGHT_2000 = datetime(2000, 1, 1, tzinfo=UTC)
_JD_2000_MIDNIGHT = 2451544.5


def jd_from_utc(dt: datetime) -> float:
    """UT Julian day (Gregorian calendar) for an aware datetime."""
    if dt.tzinfo is None:
        raise InputError("datetime must be timezone-aware")
    try:
        u = dt.astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise InputError(f"datetime {dt} out of representable range") from exc
    hour = u.hour + u.minute / 60 + u.second / 3600 + u.microsecond / 3_600_000_000
    return _gregorian_jd(u.year, u.month, u.day) + hour / 24.0


def utc_from_jd(jd: float) -> datetime:
    """Aware UTC datetime for a UT Julian day (Gregorian calendar), microsecond resolution."""
    try:
        days = jd - _JD_2000_MIDNIGHT
        whole = math.floor(days)
        midnight = _MIDNIGHT_2000 + timedelta(days=whole)
        return midnight + timedelta(microseconds=round((days - whole) * 86_400_000_000))
    except (OverflowError, ValueError) as exc:
        raise InputError(f"Julian day {jd!r} out of representable range") from exc
