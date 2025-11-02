"""Pydantic models for Haystack entities (Site, Equipment, Point)."""

from datetime import datetime
from typing import Any

import pytz
from dateutil import parser as date_parser
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
    model_validator,
)


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
    """Haystack Site entity with Pydantic serialization/validation."""

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both 'ref_name' and 'refName'
        validate_assignment=True,  # Validate on field updates
        str_strip_whitespace=True,  # Auto-clean strings
    )

    id: str | None = Field(None, description="Unique identifier")
    dis: str = Field(..., description="Display name")
    ref_name: str = Field(..., description="Reference name", alias="refName")
    tz: str = Field("UTC", description="Timezone (IANA tz database)")
    geo_addr: str | None = Field(None, description="Geographic address", alias="geoAddr")
    area: float | None = Field(None, description="Square footage")
    year_built: int | None = Field(None, description="Year of construction", alias="yearBuilt")
    tags: dict[str, Any] = Field(default_factory=dict, description="Additional tags")

    # FIELD VALIDATORS

    @field_validator("id", mode="before")
    @classmethod
    def parse_zinc_ref(cls, v: Any) -> str | None:
        """Parse Zinc ref: {"val": "p:demo:r:123"} or "@p:demo:r:123" → "p:demo:r:123"."""
        if v is None:
            return None
        if isinstance(v, dict):
            return v.get("val", "").lstrip("@")
        if isinstance(v, str):
            return v.lstrip("@")
        return v

    @field_validator("tz")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone format.

        Note: SkySpark may use timezone names that differ from IANA database.
        We accept any non-empty string to support SkySpark-specific formats.
        """
        if not v or not v.strip():
            msg = "Timezone cannot be empty"
            raise ValueError(msg)
        return v

    # MODEL SERIALIZER

    @model_serializer
    def serialize_to_zinc(self) -> dict[str, Any]:
        """Serialize to Zinc-compatible dict."""
        data: dict[str, Any] = {
            "dis": self.dis,
            "refName": self.ref_name,
            "tz": self.tz,
            "site": "m:",  # Marker tag
        }

        if self.id:
            data["id"] = f"@{self.id}"
        if self.geo_addr:
            data["geoAddr"] = self.geo_addr
        if self.area:
            data["area"] = self.area
        if self.year_built:
            data["yearBuilt"] = self.year_built

        # Add custom tags
        data.update(self.tags)

        return data

    def to_zinc_dict(self) -> dict[str, Any]:
        """Convert to Zinc-compatible dictionary.

        Backwards-compatible wrapper around Pydantic model_dump().
        """
        return self.model_dump(mode="python")


class Equipment(BaseModel):
    """Haystack Equipment entity with Pydantic serialization/validation."""

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both 'ref_name' and 'refName'
        validate_assignment=True,  # Validate on field updates
        str_strip_whitespace=True,  # Auto-clean strings
    )

    id: str | None = Field(None, description="Unique identifier")
    dis: str = Field(..., description="Display name")
    ref_name: str = Field(..., description="Reference name", alias="refName")
    site_ref: str = Field(..., description="Parent site reference", alias="siteRef")
    equip_ref: str | None = Field(None, description="Parent equipment ref", alias="equipRef")
    tz: str = Field("UTC", description="Timezone")
    tags: dict[str, Any] = Field(default_factory=dict, description="Additional tags")

    # FIELD VALIDATORS

    @field_validator("id", "site_ref", "equip_ref", mode="before")
    @classmethod
    def parse_zinc_ref(cls, v: Any) -> str | None:
        """Parse Zinc ref: {"val": "p:demo:r:123"} or "@p:demo:r:123" → "p:demo:r:123"."""
        if v is None:
            return None
        if isinstance(v, dict):
            return v.get("val", "").lstrip("@")
        if isinstance(v, str):
            return v.lstrip("@")
        return v

    @field_validator("tz")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone format.

        Note: SkySpark may use timezone names that differ from IANA database.
        We accept any non-empty string to support SkySpark-specific formats.
        """
        if not v or not v.strip():
            msg = "Timezone cannot be empty"
            raise ValueError(msg)
        return v

    # MODEL SERIALIZER

    @model_serializer
    def serialize_to_zinc(self) -> dict[str, Any]:
        """Serialize to Zinc-compatible dict."""
        data: dict[str, Any] = {
            "dis": self.dis,
            "refName": self.ref_name,
            "siteRef": f"@{self.site_ref}",
            "tz": self.tz,
            "equip": "m:",  # Marker tag
        }

        if self.id:
            data["id"] = f"@{self.id}"
        if self.equip_ref:
            data["equipRef"] = f"@{self.equip_ref}"

        # Add custom tags
        data.update(self.tags)

        return data

    def to_zinc_dict(self) -> dict[str, Any]:
        """Convert to Zinc-compatible dictionary.

        Backwards-compatible wrapper around Pydantic model_dump().
        """
        return self.model_dump(mode="python")


class Point(BaseModel):
    """Haystack Point entity with Pydantic serialization/validation."""

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both 'ref_name' and 'refName'
        validate_assignment=True,  # Validate on field updates
        str_strip_whitespace=True,  # Auto-clean strings
    )

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

    # FIELD VALIDATORS - Parse Zinc format to Python types

    @field_validator("id", "site_ref", "equip_ref", mode="before")
    @classmethod
    def parse_zinc_ref(cls, v: Any) -> str | None:
        """Parse Zinc ref: {"val": "p:demo:r:123"} or "@p:demo:r:123" → "p:demo:r:123"."""
        if v is None:
            return None
        if isinstance(v, dict):
            return v.get("val", "").lstrip("@")
        if isinstance(v, str):
            return v.lstrip("@")
        return v

    @field_validator("his", "cur", "writable", mode="before")
    @classmethod
    def parse_zinc_marker(cls, v: Any) -> bool:
        """Parse Zinc marker: "m:" or {"_kind": "marker"} → True."""
        if v == "m:" or (isinstance(v, dict) and v.get("_kind") == "marker"):
            return True
        return bool(v) if v else False

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
        """Validate timezone format.

        Note: SkySpark may use timezone names that differ from IANA database.
        We accept any non-empty string to support SkySpark-specific formats.
        """
        if not v or not v.strip():
            msg = "Timezone cannot be empty"
            raise ValueError(msg)
        return v

    # MODEL VALIDATORS - Extract fields from Zinc dict

    @model_validator(mode="before")
    @classmethod
    def extract_from_zinc_dict(cls, data: Any) -> dict[str, Any]:
        """Extract Point fields from raw Zinc response.

        Handles flat Zinc dicts where markers and kv tags are mixed with standard fields.
        This runs before field validation, preparing data for the validators above.
        """
        if not isinstance(data, dict):
            return data

        # Known system fields (mod is intentionally not here - it goes in kv_tags)
        known_fields = {
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
        }

        # Check if this looks like already-processed data (has markerTags/kvTags keys)
        # This happens when creating Point directly with Python (not from Zinc dict)
        has_marker_tags = "markerTags" in data or "marker_tags" in data
        has_kv_tags = "kvTags" in data or "kv_tags" in data

        if has_marker_tags and has_kv_tags:
            return data  # Already processed, pass through

        # Extract marker tags and kv tags from flat Zinc structure
        marker_tags = []
        kv_tags = {}

        for key, value in data.items():
            if key in known_fields:
                continue

            # Skip if these are already-provided tags (not Zinc format)
            if key in ("markerTags", "marker_tags", "kvTags", "kv_tags"):
                continue

            # Check if it's a marker
            if value == "m:" or (isinstance(value, dict) and value.get("_kind") == "marker"):
                marker_tags.append(key)
            else:
                # It's a kv tag - convert datetime dicts
                if isinstance(value, dict) and "val" in value:
                    value = _parse_zinc_datetime(value)
                kv_tags[key] = value

        # Only add extracted tags if they're not empty (meaning we extracted from Zinc)
        result = dict(data)
        if marker_tags:  # Only if we extracted some from Zinc format
            result["markerTags"] = marker_tags
        if kv_tags:  # Only if we extracted some from Zinc format
            result["kvTags"] = kv_tags

        return result

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

    # MODEL SERIALIZER - Convert to Zinc format

    @model_serializer
    def serialize_to_zinc(self) -> dict[str, Any]:
        """Serialize to Zinc-compatible dict with markers and tags.

        This replaces the manual to_zinc_dict() logic with Pydantic serialization.
        """
        # Start with basic serialization (uses field_serializers if defined)
        data: dict[str, Any] = {}

        # Add standard fields with aliases
        if self.id:
            data["id"] = f"@{self.id}"
        data["dis"] = self.dis
        data["refName"] = self.ref_name
        data["siteRef"] = f"@{self.site_ref}"
        data["equipRef"] = f"@{self.equip_ref}"
        data["kind"] = self.kind
        data["tz"] = self.tz

        # Add optional fields
        if self.unit:
            data["unit"] = self.unit

        # Add point marker
        data["point"] = "m:"

        # Add his/cur/writable markers if True
        if self.his:
            data["his"] = "m:"
        if self.cur:
            data["cur"] = "m:"
        if self.writable:
            data["writable"] = "m:"

        # Add marker tags
        for tag in self.marker_tags:
            data[tag] = "m:"

        # Add kv tags
        data.update(self.kv_tags)

        return data

    def to_zinc_dict(self) -> dict[str, Any]:
        """Convert to Zinc-compatible dictionary.

        Backwards-compatible wrapper around Pydantic model_dump().
        Uses the serialize_to_zinc model_serializer defined above.
        """
        return self.model_dump(mode="python")

    @classmethod
    def from_zinc_dict(cls, data: dict[str, Any]) -> "Point":
        """Create Point from Zinc dictionary.

        Backwards-compatible wrapper around Pydantic model_validate().
        Uses extract_from_zinc_dict model_validator and field validators defined above.
        """
        return cls.model_validate(data)
