"""Civil local time + IANA timezone -> UTC -> Julian day (UT).

Wrong timezones are the most common cause of wrong charts, so nonexistent (DST gap) and
ambiguous (DST overlap) local times are rejected rather than guessed.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, reset_tzpath

import swisseph as swe

from vedic_engine.models import InputError

# Pin tz data to the `tzdata` package (locked in uv.lock): an empty search path makes
# zoneinfo skip the OS tz database, so the same input gives the same output on any machine.
reset_tzpath(to=())


class NonexistentTimeError(InputError):
    """Local time falls in a DST gap and never occurred."""


class AmbiguousTimeError(InputError):
    """Local time occurred twice (DST overlap) and no fold was given."""


class UnknownTimezoneError(InputError):
    """Not a known IANA timezone."""


def _zone(tz: str) -> ZoneInfo:
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


def jd_from_utc(dt: datetime) -> float:
    """UT Julian day (Gregorian calendar) for an aware datetime."""
    if dt.tzinfo is None:
        raise InputError("datetime must be timezone-aware")
    try:
        u = dt.astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise InputError(f"datetime {dt} out of representable range") from exc
    hour = u.hour + u.minute / 60 + u.second / 3600 + u.microsecond / 3_600_000_000
    return float(swe.julday(u.year, u.month, u.day, hour, swe.GREG_CAL))


def utc_from_jd(jd: float) -> datetime:
    """Aware UTC datetime for a UT Julian day (Gregorian calendar), microsecond resolution."""
    try:
        year, month, day, hour = swe.revjul(jd, swe.GREG_CAL)
        midnight = datetime(year, month, day, tzinfo=UTC)
        return midnight + timedelta(microseconds=round(hour * 3_600_000_000))
    except (OverflowError, ValueError) as exc:
        raise InputError(f"Julian day {jd!r} out of representable range") from exc
