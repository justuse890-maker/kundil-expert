"""Request schemas of the v1 API (spec 6, amended by Task 2).

Time-zone input is exactly one of ``tz`` (IANA name), ``utc_offset`` (``"+05:30"``) or
``lmt: true`` (local mean time at the longitude); anything else is a 422.
"""

import datetime as dt
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from vedic_engine.constants import VIMSHOTTARI_ORDER
from vedic_engine.dasha.yogini import YOGINIS
from vedic_engine.models import BirthInput, Settings
from vedic_engine.timeutil import lmt_tz
from vedic_engine.varga import VARGAS

NOON = dt.time(12, 0)
LORD_KEYS: tuple[str, ...] = (*(g.value for g in VIMSHOTTARI_ORDER), *YOGINIS)


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SettingsIn(Request):
    ayanamsa: Literal["LAHIRI", "RAMAN", "KP", "FAGAN_BRADLEY"] = "LAHIRI"
    node: Literal["MEAN", "TRUE"] = "MEAN"
    dasha_year_days: float = Field(default=365.25, ge=300.0, le=400.0)
    sunrise: Literal["UPPER_LIMB_REFRACTED", "CENTER_NO_REFRACTION"] = "UPPER_LIMB_REFRACTED"

    def to_engine(self) -> Settings:
        return Settings(
            ayanamsa=self.ayanamsa,
            node=self.node,
            dasha_year_days=self.dasha_year_days,
            sunrise=self.sunrise,
        )


class ZoneIn(Request):
    """The three ways to say how local civil time relates to UTC."""

    tz: str | None = Field(None, min_length=1, description="IANA zone, e.g. Asia/Kolkata")
    utc_offset: str | None = Field(
        None,
        pattern=r"^[+-][0-9]{2}:[0-9]{2}(:[0-9]{2})?$",
        description='Fixed offset from UTC, e.g. "+05:30"',
    )
    lmt: bool = Field(False, description="Local mean time at the longitude (lon/15 hours)")

    @model_validator(mode="after")
    def _exactly_one_zone(self) -> Self:
        chosen = [n for n, v in (("tz", self.tz), ("utc_offset", self.utc_offset)) if v is not None]
        if self.lmt:
            chosen.append("lmt")
        if len(chosen) != 1:
            got = ", ".join(chosen) if chosen else "none"
            raise ValueError(f"give exactly one of tz, utc_offset or lmt=true (got: {got})")
        return self

    def engine_tz(self, lon: float) -> str:
        """The engine ``tz`` string: IANA name, ``UTC+HH:MM``, or the LMT offset of ``lon``."""
        if self.lmt:
            return lmt_tz(lon)
        if self.utc_offset is not None:
            return f"UTC{self.utc_offset}"
        assert self.tz is not None
        return self.tz


class KundliRequest(ZoneIn):
    date: dt.date
    time: dt.time | None = Field(None, description="HH:MM[:SS]; may be omitted if time_known=false")
    time_known: bool = True
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    alt: float = Field(0.0, ge=-500.0, le=10000.0)
    fold: Literal[0, 1] | None = Field(None, description="0 = first, 1 = second occurrence")
    name: str | None = Field(None, max_length=200)
    settings: SettingsIn = Field(default_factory=lambda: SettingsIn())
    vargas: list[int] | None = Field(None, description=f"Subset of {list(VARGAS)}; default all")
    dasha_depth: int = Field(3, ge=1, le=5)

    @model_validator(mode="after")
    def _time_and_vargas(self) -> Self:
        if self.time_known and self.time is None:
            raise ValueError("time is required unless time_known is false")
        if self.vargas is not None:
            bad = sorted(set(self.vargas) - set(VARGAS))
            if bad:
                raise ValueError(f"unsupported vargas {bad}; supported: {list(VARGAS)}")
        return self

    def to_birth(self) -> BirthInput:
        return BirthInput(
            local=dt.datetime.combine(self.date, self.time or NOON),
            tz=self.engine_tz(self.lon) if not self.lmt else "UTC+00:00",  # LMT: ignored
            lat=self.lat,
            lon=self.lon,
            alt=self.alt,
            fold=self.fold,
            name=self.name,
            time_known=self.time_known,
            lmt=self.lmt,
        )

    def vargas_list(self) -> list[int]:
        return sorted(set(self.vargas)) if self.vargas is not None else list(VARGAS)


class PanchangRequest(ZoneIn):
    date: dt.date
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    alt: float = Field(0.0, ge=-500.0, le=10000.0)
    settings: SettingsIn = Field(default_factory=lambda: SettingsIn())


class DashaRequest(Request):
    kundli: KundliRequest
    path: list[str] = Field(
        min_length=1,
        max_length=5,
        description="Lords from the maha down, e.g. ['jupiter', 'saturn']; Vimshottari lords "
        "or yogini keys (an earlier-occurring maha wins if a lord appears twice)",
    )
    depth: int = Field(1, ge=1, le=5, description="Levels to expand below the path's period")

    @model_validator(mode="after")
    def _known_lords(self) -> Self:
        bad = [p for p in self.path if p not in LORD_KEYS]
        if bad:
            raise ValueError(f"unknown dasha lords {bad}")
        return self


class TransitRequest(Request):
    datetime_utc: AwareDatetime
    natal: KundliRequest | None = None
    settings: SettingsIn | None = Field(
        None, description="Defaults to natal.settings if natal is given, else the defaults"
    )
