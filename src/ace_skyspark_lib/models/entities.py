"""Pydantic models for Haystack entities (Site, Equipment, Point)."""

from datetime import datetime
from typing import Any

import pytz
from dateutil import parser as date_parser
from pydantic import BaseModel, Field, field_validator, model_validator


def _parse_zinc_datetime(value: dict[str, Any]) -> datetime:
    """Parse Zinc datetime dict to Python datetime.

    Args:
        value: Zinc datetime dict with 'val' and optionally 'tz'

    Returns:
        Python datetime object with proper timezone

    Examples:
        {"val": "2025-10-30T18:30:00-04:00 New_York", "tz": "New_York"}
        -> datetime with New_York timezone
    """
    if not isinstance(value, dict) or "val" not in value:
        return value

    dt_str = value["val"]
    tz_name = value.get("tz", "UTC")

    # Extract timezone name from value if present (e.g., "... New_York")
    if " " in dt_str:
        parts = dt_str.split(" ")
        dt_str = parts[0]
        if len(parts) > 1 and not tz_name:
            tz_name = parts[1]

    # Parse the datetime string (gets offset timezone)
    dt = date_parser.parse(dt_str)

    # Convert to named timezone if available
    try:
        named_tz = pytz.timezone(tz_name)
        # Replace offset timezone with named timezone
        dt_naive = dt.replace(tzinfo=None)
        dt = named_tz.localize(dt_naive, is_dst=None)
    except Exception:
        # If timezone name is invalid, keep the parsed timezone
        pass

    return dt


class HaystackRef(BaseModel):
    """Haystack reference with optional display name."""

    id: str = Field(..., description="Entity ID")
    dis: str | None = Field(None, description="Display name")

    def __str__(self) -> str:
        """Return Haystack ref format."""
        return f"@{self.id}"


class Site(BaseModel):
    """Haystack Site entity."""

    id: str | None = Field(None, description="Unique identifier")
    dis: str = Field(..., description="Display name")
    ref_name: str = Field(..., description="Reference name", alias="refName")
    tz: str = Field("UTC", description="Timezone (IANA tz database)")
    geo_addr: str | None = Field(None, description="Geographic address", alias="geoAddr")
    area: float | None = Field(None, description="Square footage")
    year_built: int | None = Field(None, description="Year of construction", alias="yearBuilt")
    tags: dict[str, Any] = Field(default_factory=dict, description="Additional tags")

    model_config = {"populate_by_name": True}

    @field_validator("tz")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone is in IANA tz database."""
        if v not in pytz.all_timezones_set:
            msg = f"Invalid timezone: {v}"
            raise ValueError(msg)
        return v

    def to_zinc_dict(self) -> dict[str, Any]:
        """Convert to Zinc-compatible dictionary."""
        result: dict[str, Any] = {
            "dis": self.dis,
            "refName": self.ref_name,
            "tz": self.tz,
            "site": "m:",  # Marker tag
        }
        if self.id:
            result["id"] = f"@{self.id}"
        if self.geo_addr:
            result["geoAddr"] = self.geo_addr
        if self.area:
            result["area"] = self.area
        if self.year_built:
            result["yearBuilt"] = self.year_built
        result.update(self.tags)
        return result


class Equipment(BaseModel):
    """Haystack Equipment entity."""

    id: str | None = Field(None, description="Unique identifier")
    dis: str = Field(..., description="Display name")
    ref_name: str = Field(..., description="Reference name", alias="refName")
    site_ref: str = Field(..., description="Parent site reference", alias="siteRef")
    equip_ref: str | None = Field(None, description="Parent equipment ref", alias="equipRef")
    tz: str = Field("UTC", description="Timezone")
    tags: dict[str, Any] = Field(default_factory=dict, description="Additional tags")

    model_config = {"populate_by_name": True}

    @field_validator("tz")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone."""
        if v not in pytz.all_timezones_set:
            msg = f"Invalid timezone: {v}"
            raise ValueError(msg)
        return v

    def to_zinc_dict(self) -> dict[str, Any]:
        """Convert to Zinc-compatible dictionary."""
        result: dict[str, Any] = {
            "dis": self.dis,
            "refName": self.ref_name,
            "siteRef": f"@{self.site_ref}",
            "tz": self.tz,
            "equip": "m:",  # Marker tag
        }
        if self.id:
            result["id"] = f"@{self.id}"
        if self.equip_ref:
            result["equipRef"] = f"@{self.equip_ref}"
        result.update(self.tags)
        return result


class Point(BaseModel):
    """Haystack Point entity."""

    id: str | None = Field(None, description="Unique identifier")
    dis: str = Field(..., description="Display name")
    ref_name: str = Field(..., description="Reference name", alias="refName")
    site_ref: str = Field(..., description="Parent site reference", alias="siteRef")
    equip_ref: str = Field(..., description="Parent equipment reference", alias="equipRef")
    kind: str = Field(..., description="Data kind: Bool, Number, or Str")
    tz: str = Field("UTC", description="Timezone")
    unit: str | None = Field(None, description="Engineering unit (for Number kind)")
    his: bool = Field(False, description="Point is historized")
    cur: bool = Field(False, description="Current value sync enabled")
    writable: bool = Field(False, description="Point is writable")
    marker_tags: list[str] = Field(
        default_factory=list, description="Marker tags (sensor, cmd, sp, etc)", alias="markerTags"
    )
    kv_tags: dict[str, Any] = Field(
        default_factory=dict, description="Key-value tags", alias="kvTags"
    )

    model_config = {"populate_by_name": True}

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        """Validate kind is Bool, Number, or Str."""
        if v not in {"Bool", "Number", "Str"}:
            msg = f"Invalid kind: {v}. Must be Bool, Number, or Str"
            raise ValueError(msg)
        return v

    @field_validator("tz")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone."""
        if v not in pytz.all_timezones_set:
            msg = f"Invalid timezone: {v}"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_point_function(self) -> "Point":
        """Validate point has exactly one function marker."""
        function_markers = {"sensor", "cmd", "sp", "synthetic"}
        found_functions = [tag for tag in self.marker_tags if tag in function_markers]

        if len(found_functions) == 0:
            msg = "Point must have one function marker: sensor, cmd, sp, or synthetic"
            raise ValueError(msg)
        if len(found_functions) > 1:
            msg = f"Point can only have one function marker, found: {found_functions}"
            raise ValueError(msg)

        return self

    def to_zinc_dict(self) -> dict[str, Any]:
        """Convert to Zinc-compatible dictionary."""
        result: dict[str, Any] = {
            "dis": self.dis,
            "refName": self.ref_name,
            "siteRef": f"@{self.site_ref}",
            "equipRef": f"@{self.equip_ref}",
            "kind": self.kind,
            "tz": self.tz,
            "point": "m:",  # Marker tag
        }
        if self.id:
            result["id"] = f"@{self.id}"
        if self.unit:
            result["unit"] = self.unit
        if self.his:
            result["his"] = "m:"
        if self.cur:
            result["cur"] = "m:"
        if self.writable:
            result["writable"] = "m:"

        # Add marker tags
        for tag in self.marker_tags:
            result[tag] = "m:"

        # Add key-value tags
        result.update(self.kv_tags)

        return result

    @classmethod
    def from_zinc_dict(cls, data: dict[str, Any]) -> "Point":
        """Create Point from Zinc dictionary."""
        # Extract ID
        point_id = None
        if "id" in data:
            if isinstance(data["id"], dict):
                point_id = data["id"].get("val", "")
            else:
                point_id = data["id"].lstrip("@")

        # Extract marker and kv tags
        marker_tags = []
        kv_tags = {}

        for key, value in data.items():
            if key in {
                "id",
                "dis",
                "refName",
                "siteRef",
                "equipRef",
                "kind",
                "tz",
                "unit",
                "point",
                "his",
                "cur",
                "writable",
            }:
                continue

            if value == "m:" or (isinstance(value, dict) and value.get("_kind") == "marker"):
                marker_tags.append(key)
            else:
                # Convert Zinc datetime dicts to Python datetime
                if isinstance(value, dict) and "val" in value:
                    value = _parse_zinc_datetime(value)
                kv_tags[key] = value

        # Extract refs
        site_ref = data.get("siteRef", "")
        if isinstance(site_ref, dict):
            site_ref = site_ref.get("val", "")
        site_ref = site_ref.lstrip("@")

        equip_ref = data.get("equipRef", "")
        if isinstance(equip_ref, dict):
            equip_ref = equip_ref.get("val", "")
        equip_ref = equip_ref.lstrip("@")

        return cls(
            id=point_id,
            dis=data.get("dis", ""),
            refName=data.get("refName", ""),
            siteRef=site_ref,
            equipRef=equip_ref,
            kind=data.get("kind", "Number"),
            tz=data.get("tz", "UTC"),
            unit=data.get("unit"),
            his="his" in data or data.get("his") == "m:",
            cur="cur" in data or data.get("cur") == "m:",
            writable="writable" in data or data.get("writable") == "m:",
            markerTags=marker_tags,
            kvTags=kv_tags,
        )
