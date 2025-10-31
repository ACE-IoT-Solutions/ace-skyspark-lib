# Pydantic Refactor Plan

## Objective
Replace manual serialization/deserialization with Pydantic v2 features for better maintainability, type safety, and performance.

---

## Current Architecture (Manual)

### Serialization (to_zinc_dict)
```python
def to_zinc_dict(self) -> dict[str, Any]:
    """Convert to Zinc-compatible dictionary."""
    result: dict[str, Any] = {
        "dis": self.dis,
        "refName": self.ref_name,
        "siteRef": f"@{self.site_ref}",  # Manual formatting
        "equipRef": f"@{self.equip_ref}",
        "kind": self.kind,
        "tz": self.tz,
        "point": "m:",  # Manual marker
    }
    if self.id:  # Manual conditional
        result["id"] = f"@{self.id}"
    if self.unit:
        result["unit"] = self.unit
    # ... 20 more lines of manual logic
    return result
```

### Deserialization (from_zinc_dict)
```python
@classmethod
def from_zinc_dict(cls, data: dict[str, Any]) -> "Point":
    """Create Point from Zinc dictionary."""
    # 60+ lines of manual parsing
    if "id" in data:
        if isinstance(data["id"], dict):
            point_id = data["id"].get("val", "")
        else:
            point_id = data["id"].lstrip("@")
    # ... manual extraction of every field
    return cls(id=point_id, dis=..., ...)
```

**Problems:**
- 200+ lines of repetitive code
- Easy to make mistakes
- Hard to maintain
- No type safety
- Doesn't leverage Pydantic

---

## New Architecture (Pydantic)

### Key Pydantic v2 Features We'll Use:

1. **`@field_serializer`** - Custom serialization per field
2. **`@field_validator(mode='before')`** - Custom parsing before validation
3. **`@model_serializer`** - Custom model-level serialization
4. **`ConfigDict`** - Model configuration
5. **`model_dump()`** - Automatic serialization
6. **`model_validate()`** - Automatic parsing with validators

---

## Refactored Point Model

### Part 1: Field Validators (Deserialization)

```python
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Any

class Point(BaseModel):
    """Haystack Point entity with Pydantic serialization."""

    model_config = ConfigDict(
        populate_by_name=True,      # Allow both 'ref_name' and 'refName'
        validate_assignment=True,    # Validate on field updates
        str_strip_whitespace=True,   # Auto-clean strings
    )

    # Fields
    id: str | None = Field(None, description="Unique identifier")
    dis: str = Field(..., description="Display name")
    ref_name: str = Field(..., description="Reference name", alias="refName")
    site_ref: str = Field(..., description="Parent site ref", alias="siteRef")
    equip_ref: str = Field(..., description="Parent equip ref", alias="equipRef")
    kind: str = Field(..., description="Data kind")
    tz: str = Field("UTC", description="Timezone")
    unit: str | None = Field(None, description="Engineering unit")
    his: bool = Field(False, description="Historized")
    cur: bool = Field(False, description="Current value")
    writable: bool = Field(False, description="Writable")
    marker_tags: list[str] = Field(default_factory=list, alias="markerTags")
    kv_tags: dict[str, Any] = Field(default_factory=dict, alias="kvTags")

    # VALIDATORS - Replace from_zinc_dict() logic

    @field_validator('id', 'site_ref', 'equip_ref', mode='before')
    @classmethod
    def parse_zinc_ref(cls, v: Any) -> str | None:
        """Parse Zinc ref format: {"val": "p:demo:r:123"} or "@p:demo:r:123" → "p:demo:r:123"."""
        if v is None:
            return None
        if isinstance(v, dict):
            return v.get("val", "").lstrip("@")
        if isinstance(v, str):
            return v.lstrip("@")
        return v

    @field_validator('his', 'cur', 'writable', mode='before')
    @classmethod
    def parse_zinc_marker(cls, v: Any) -> bool:
        """Parse Zinc marker: "m:" or {"_kind": "marker"} → True."""
        if v == "m:" or (isinstance(v, dict) and v.get("_kind") == "marker"):
            return True
        return bool(v)

    @field_validator('kv_tags', mode='before')
    @classmethod
    def parse_zinc_tags(cls, v: Any, info) -> dict[str, Any]:
        """Extract kv_tags from full Zinc dict if needed."""
        # If we're validating from full Zinc response, extract tags
        # This will be handled by model_validate logic
        if isinstance(v, dict):
            # Convert datetime dicts
            return {
                k: _parse_zinc_datetime(val) if isinstance(val, dict) and "val" in val else val
                for k, val in v.items()
            }
        return v or {}
```

### Part 2: Field Serializers (to_zinc_dict replacement)

```python
from pydantic import field_serializer

class Point(BaseModel):
    # ... fields from above ...

    # SERIALIZERS - Replace to_zinc_dict() logic

    @field_serializer('id', 'site_ref', 'equip_ref', when_used='always')
    def serialize_ref(self, value: str | None) -> str | None:
        """Serialize to Zinc ref format: "p:demo:r:123" → "@p:demo:r:123"."""
        if value is None:
            return None
        return f"@{value}" if not value.startswith("@") else value

    @field_serializer('ref_name')
    def serialize_ref_name(self, value: str) -> str:
        """Use alias 'refName' in output."""
        return value
```

### Part 3: Model-level Serialization (for markers and tags)

```python
from pydantic import model_serializer

class Point(BaseModel):
    # ... fields and field serializers from above ...

    @model_serializer
    def serialize_to_zinc(self) -> dict[str, Any]:
        """Serialize to Zinc-compatible dict with markers and tags."""
        # Get base serialization using Pydantic
        data = self.model_dump(by_alias=True, exclude_none=True, mode='json')

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

        # Remove internal fields
        data.pop("markerTags", None)
        data.pop("kvTags", None)

        return data
```

### Part 4: Custom Validation for from_zinc_dict

```python
from pydantic import model_validator

class Point(BaseModel):
    # ... all previous code ...

    @model_validator(mode='before')
    @classmethod
    def extract_from_zinc_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Extract Point fields from raw Zinc response.

        Handles extracting marker_tags and kv_tags from flat Zinc dict.
        """
        if not isinstance(data, dict):
            return data

        # Extract standard fields
        extracted = {
            "id": data.get("id"),
            "dis": data.get("dis", ""),
            "refName": data.get("refName", ""),
            "siteRef": data.get("siteRef"),
            "equipRef": data.get("equipRef"),
            "kind": data.get("kind", "Number"),
            "tz": data.get("tz", "UTC"),
            "unit": data.get("unit"),
            "his": data.get("his"),
            "cur": data.get("cur"),
            "writable": data.get("writable"),
        }

        # Extract marker tags and kv tags
        marker_tags = []
        kv_tags = {}

        # Known system fields to skip
        known_fields = {
            "id", "dis", "refName", "siteRef", "equipRef",
            "kind", "tz", "unit", "point", "his", "cur", "writable", "mod"
        }

        for key, value in data.items():
            if key in known_fields:
                continue

            # Check if it's a marker
            if value == "m:" or (isinstance(value, dict) and value.get("_kind") == "marker"):
                marker_tags.append(key)
            else:
                # It's a kv tag - convert datetime dicts
                if isinstance(value, dict) and "val" in value:
                    value = _parse_zinc_datetime(value)
                kv_tags[key] = value

        extracted["markerTags"] = marker_tags
        extracted["kvTags"] = kv_tags

        return extracted
```

---

## Usage Examples

### Deserialization (Replaces from_zinc_dict)

```python
# BEFORE:
point = Point.from_zinc_dict(zinc_data)

# AFTER:
point = Point.model_validate(zinc_data)
```

**Pydantic automatically:**
1. Runs `extract_from_zinc_dict` validator
2. Parses refs with `parse_zinc_ref`
3. Parses markers with `parse_zinc_marker`
4. Validates types
5. Creates Point instance

### Serialization (Replaces to_zinc_dict)

```python
# BEFORE:
zinc_dict = point.to_zinc_dict()

# AFTER:
zinc_dict = point.model_dump(mode='json', by_alias=True)
```

**Pydantic automatically:**
1. Uses `serialize_to_zinc` model serializer
2. Applies ref serializers
3. Adds markers
4. Returns Zinc-compatible dict

---

## Benefits

### Code Reduction
- **Before**: 200+ lines of manual serialization/deserialization
- **After**: ~80 lines of declarative validators/serializers
- **Savings**: 60% less code

### Type Safety
```python
# Pydantic catches errors at validation time:
point = Point.model_validate({"dis": 123})  # ValidationError: str expected
```

### Maintainability
```python
# Adding a new field is simple:
new_field: str = Field(None, alias="newField")

# Validator automatically handles it!
```

### Performance
- Pydantic v2 is Rust-based (10-50x faster than v1)
- Built-in caching
- Optimized serialization

### Better Errors
```python
# Before: Silent failure or KeyError
# After: Clear validation error with field path
try:
    Point.model_validate(bad_data)
except ValidationError as e:
    print(e.json())  # {"loc": ["site_ref"], "msg": "field required"}
```

---

## Migration Plan

### Phase 1: Point Model (Most Complex)
1. Add validators and serializers to Point
2. Keep `to_zinc_dict()` as wrapper: `return self.model_dump(...)`
3. Keep `from_zinc_dict()` as wrapper: `return cls.model_validate(...)`
4. Test thoroughly
5. Remove wrappers once confirmed working

### Phase 2: Equipment Model
- Apply same pattern
- Simpler than Point (no marker_tags/kv_tags)

### Phase 3: Site Model
- Apply same pattern
- Simplest model

### Phase 4: Cleanup
- Remove manual serialization code
- Update all call sites to use `model_validate()` / `model_dump()`
- Update tests

---

## Testing Strategy

### Unit Tests
```python
def test_point_serialization():
    """Test Pydantic serialization."""
    point = Point(
        dis="Test",
        ref_name="test",
        site_ref="site123",
        equip_ref="equip456",
        kind="Number",
        marker_tags=["sensor"],
    )

    zinc_dict = point.model_dump(mode='json', by_alias=True)

    assert zinc_dict["id"] is None  # Should be excluded by exclude_none
    assert zinc_dict["siteRef"] == "@site123"
    assert zinc_dict["point"] == "m:"
    assert zinc_dict["sensor"] == "m:"
```

### Integration Tests
```python
async def test_round_trip():
    """Test parsing SkySpark response and re-serializing."""
    # Read from SkySpark
    points_data = await client.read_points()

    # Parse with Pydantic
    points = [Point.model_validate(p) for p in points_data]

    # Modify
    points[0].marker_tags.append("critical")

    # Serialize back
    zinc_dict = points[0].model_dump(mode='json', by_alias=True)

    # Should work without errors
    result = await client.update_points([points[0]])
    assert result
```

---

## Implementation Order

1. ✅ Create refactored Point model in new file
2. ✅ Test Point model thoroughly
3. ✅ Apply to Equipment model
4. ✅ Apply to Site model
5. ✅ Update ZincEncoder to use model_dump()
6. ✅ Update operations to use model_validate()
7. ✅ Run full test suite
8. ✅ Remove old manual code
9. ✅ Add security fixes to serializers

---

## Next Steps

Ready to implement! Starting with Point model refactor.
