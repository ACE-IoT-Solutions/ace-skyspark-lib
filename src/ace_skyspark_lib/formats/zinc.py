"""Zinc grid encoding for Haystack operations."""

from collections import defaultdict
from datetime import datetime
from typing import Any

from ace_skyspark_lib.models.entities import SKYSPARK_COMPUTED_TAGS, Equipment, Point, Site
from ace_skyspark_lib.models.history import HistorySample


def _escape_zinc_string(s: str) -> str:
    """Escape special characters for Zinc strings.

    Escapes characters that have special meaning in Zinc format to prevent
    injection vulnerabilities and ensure proper parsing.

    Args:
        s: String to escape

    Returns:
        Escaped string safe for use in Zinc format

    Security:
        - Prevents quote injection
        - Prevents newline injection that breaks grid structure
        - Removes null bytes that can truncate strings in C parsers
        - Removes control characters that can cause terminal/parser issues
    """
    # Escape in this order to avoid double-escaping
    s = s.replace("\\", "\\\\")  # Backslash MUST be first!
    s = s.replace('"', '\\"')  # Double quotes
    s = s.replace("\n", "\\n")  # Newline
    s = s.replace("\r", "\\r")  # Carriage return
    s = s.replace("\t", "\\t")  # Tab

    # Remove null bytes (can truncate strings in C-based parsers)
    s = s.replace("\x00", "")

    # Remove control characters (except tab, newline, carriage return which we've already escaped)
    # Control characters are 0x00-0x1F except \t(0x09), \n(0x0A), \r(0x0D)
    return "".join(c for c in s if ord(c) >= 32 or c in "\t\n\r")


class ZincEncoder:
    """Encode Python objects to Zinc grid format."""

    @staticmethod
    def encode_commit_add_sites(sites: list[Site]) -> str:
        """Encode sites for commit:add operation.

        Args:
            sites: List of Site entities to create

        Returns:
            Zinc grid string
        """
        if not sites:
            return ""

        grid = 'ver:"3.0" commit:"add"\n'

        # Collect all unique tags
        all_tags = {"dis", "tz", "refName", "site"}
        for site in sites:
            zinc_dict = site.to_zinc_dict()
            # Filter out empty string keys
            valid_keys = {k for k in zinc_dict if k and k.strip()}
            all_tags.update(valid_keys)
        all_tags.discard("id")  # Don't include id in add operations
        all_tags.discard("")  # Remove empty strings

        # Header row
        grid += ", ".join(sorted(all_tags)) + "\n"

        # Data rows
        for site in sites:
            zinc_dict = site.to_zinc_dict()
            row_values: list[str] = []
            for tag in sorted(all_tags):
                value = zinc_dict.get(tag, "")
                row_values.append(ZincEncoder._encode_value(value))
            grid += ", ".join(row_values) + "\n"

        return grid

    @staticmethod
    def encode_commit_add_equipment(equipment: list[Equipment]) -> str:
        """Encode equipment for commit:add operation.

        Args:
            equipment: List of Equipment entities to create

        Returns:
            Zinc grid string
        """
        if not equipment:
            return ""

        grid = 'ver:"3.0" commit:"add"\n'

        # Collect all unique tags
        all_tags = {"dis", "siteRef", "tz", "refName", "equip"}
        for equip in equipment:
            zinc_dict = equip.to_zinc_dict()
            # Filter out empty string keys
            valid_keys = {k for k in zinc_dict if k and k.strip()}
            all_tags.update(valid_keys)
        all_tags.discard("id")
        all_tags.discard("")  # Remove empty strings

        # Header row
        grid += ", ".join(sorted(all_tags)) + "\n"

        # Data rows
        for equip in equipment:
            zinc_dict = equip.to_zinc_dict()
            row_values: list[str] = []
            for tag in sorted(all_tags):
                value = zinc_dict.get(tag, "")
                row_values.append(ZincEncoder._encode_value(value))
            grid += ", ".join(row_values) + "\n"

        return grid

    @staticmethod
    def encode_commit_add_points(points: list[Point]) -> str:
        """Encode points for commit:add operation.

        Args:
            points: List of Point entities to create

        Returns:
            Zinc grid string
        """
        if not points:
            return ""

        grid = 'ver:"3.0" commit:"add"\n'

        # Collect all unique tags
        all_tags = {"dis", "siteRef", "equipRef", "kind", "tz", "refName", "point"}
        for point in points:
            zinc_dict = point.to_zinc_dict()
            # Filter out empty string keys before adding to all_tags
            valid_keys = {k for k in zinc_dict if k and k.strip()}
            all_tags.update(valid_keys)
        all_tags.discard("id")
        all_tags.discard("")
        all_tags -= SKYSPARK_COMPUTED_TAGS

        # Header row
        grid += ", ".join(sorted(all_tags)) + "\n"

        # Data rows
        for point in points:
            zinc_dict = point.to_zinc_dict()
            row_values: list[str] = []
            for tag in sorted(all_tags):
                value = zinc_dict.get(tag, "")
                row_values.append(ZincEncoder._encode_value(value))
            grid += ", ".join(row_values) + "\n"

        return grid

    @staticmethod
    def encode_commit_update_equipment(equipment: list[Equipment]) -> str:
        """Encode equipment for commit:update operation.

        Args:
            equipment: List of Equipment entities to update

        Returns:
            Zinc grid string
        """
        if not equipment:
            return ""

        grid = 'ver:"3.0" commit:"update"\n'

        # Collect all unique tags (including id and mod for updates)
        all_tags = {"id", "dis", "siteRef", "tz", "refName", "equip"}
        for equip in equipment:
            zinc_dict = equip.to_zinc_dict()
            # Filter out empty string keys
            valid_keys = {k for k in zinc_dict if k and k.strip()}
            all_tags.update(valid_keys)
        all_tags.discard("")  # Remove empty strings

        # Header row
        grid += ", ".join(sorted(all_tags)) + "\n"

        # Data rows
        for equip in equipment:
            if not equip.id:
                msg = f"Equipment {equip.dis} must have an ID for update operations"
                raise ValueError(msg)

            zinc_dict = equip.to_zinc_dict()
            row_values: list[str] = []
            for tag in sorted(all_tags):
                value = zinc_dict.get(tag, "")
                row_values.append(ZincEncoder._encode_value(value))
            grid += ", ".join(row_values) + "\n"

        return grid

    @staticmethod
    def encode_commit_update_points(points: list[Point]) -> str:
        """Encode points for commit:update operation.

        Args:
            points: List of Point entities to update

        Returns:
            Zinc grid string
        """
        if not points:
            return ""

        grid = 'ver:"3.0" commit:"update"\n'

        # Collect all unique tags (including id for updates)
        all_tags = {"id", "dis", "siteRef", "equipRef", "kind", "tz", "refName", "point"}
        for point in points:
            zinc_dict = point.to_zinc_dict()
            # Filter out empty string keys before adding to all_tags
            valid_keys = {k for k in zinc_dict if k and k.strip()}
            all_tags.update(valid_keys)
        all_tags.discard("")
        all_tags -= SKYSPARK_COMPUTED_TAGS - {"mod"}

        # Header row
        grid += ", ".join(sorted(all_tags)) + "\n"

        # Data rows
        for point in points:
            if not point.id:
                msg = f"Point {point.dis} must have an ID for update operations"
                raise ValueError(msg)

            zinc_dict = point.to_zinc_dict()
            row_values: list[str] = []
            for tag in sorted(all_tags):
                value = zinc_dict.get(tag, "")
                row_values.append(ZincEncoder._encode_value(value))
            grid += ", ".join(row_values) + "\n"

        return grid

    @staticmethod
    def encode_his_write_rpc(samples: list[HistorySample]) -> str:
        """Encode history samples for RPC evalAll method.

        Args:
            samples: List of history samples

        Returns:
            Zinc grid string with hisWrite expressions
        """
        if not samples:
            return ""

        grid = 'ver:"3.0"\n'
        grid += "expr\n"

        for sample in samples:
            # Format value
            if isinstance(sample.value, bool):
                val_str = str(sample.value).lower()
            elif isinstance(sample.value, str):
                # The value is an Axon string literal embedded inside a Zinc
                # string, so its quotes/backslashes must survive both layers:
                # escape for the Axon layer, then escape that result for the
                # Zinc layer (matching the \" used for the parseDateTime args
                # below). Without the second pass the bare quotes terminate the
                # outer Zinc string and corrupt the grid.
                axon_literal = f'"{_escape_zinc_string(sample.value)}"'
                val_str = axon_literal.replace("\\", "\\\\").replace('"', '\\"')
            else:
                val_str = str(sample.value)

            # Build hisWrite expression.
            # Timestamps are UTC; toTimeZone converts to the point's configured tz,
            # which SkySpark requires to match the rec's tz tag.
            ts_iso = sample.timestamp.isoformat()
            expr = (
                f'"hisWrite('
                f'{{ts: parseDateTime(\\"{ts_iso}\\", '
                f'\\"YYYY-MM-DDThh:mm:ssz\\").toTimeZone(readById(@{sample.point_id})->tz), '
                f"val: {val_str}}}, "
                f'@{sample.point_id})"\n'
            )
            grid += expr

        return grid

    @staticmethod
    def encode_his_write_batch(samples: list[HistorySample], timezone_name: str) -> str:
        """Encode a standard Haystack batch ``hisWrite`` request.

        Each point is represented by a ``v{i}`` column whose column metadata
        contains its id. Samples that share a timestamp are combined into the
        same row; missing point values are encoded as Zinc nulls.

        Args:
            samples: Samples for points that share one configured timezone.
            timezone_name: Haystack timezone name shared by all points.

        Returns:
            Zinc grid accepted by the standard ``hisWrite`` HTTP operation.
        """
        if not samples:
            return ""

        point_ids = list(dict.fromkeys(sample.point_id for sample in samples))
        point_indexes = {point_id: index for index, point_id in enumerate(point_ids)}

        # A timestamp may occur more than once for one point. Keep every sample
        # by creating as many same-timestamp rows as the largest duplicate set.
        by_timestamp: dict[datetime, dict[str, list[HistorySample]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for sample in samples:
            by_timestamp[sample.timestamp].setdefault(sample.point_id, []).append(sample)

        header = ["ts"] + [f"v{i} id:@{point_id}" for i, point_id in enumerate(point_ids)]
        lines = ['ver:"3.0"', ",".join(header)]

        for timestamp in sorted(by_timestamp):
            samples_by_point = by_timestamp[timestamp]
            duplicate_rows = max(len(values) for values in samples_by_point.values())
            for duplicate_index in range(duplicate_rows):
                row = [ZincEncoder._encode_datetime(timestamp, timezone_name)] + ["N"] * len(
                    point_ids
                )
                for point_id, point_samples in samples_by_point.items():
                    if duplicate_index < len(point_samples):
                        row[point_indexes[point_id] + 1] = ZincEncoder._encode_value(
                            point_samples[duplicate_index].value
                        )
                lines.append(",".join(row))

        return "\n".join(lines) + "\n"

    @staticmethod
    def encode_his_write_single(
        point_id: str,
        samples: list[HistorySample],
        timezone_name: str,
    ) -> str:
        """Encode a standard single-point ``hisWrite`` request grid."""
        if not samples:
            return ""

        lines = [f'ver:"3.0" id:@{point_id}', "ts,val"]
        lines.extend(
            f"{ZincEncoder._encode_datetime(sample.timestamp, timezone_name)},"
            f"{ZincEncoder._encode_value(sample.value)}"
            for sample in sorted(samples, key=lambda item: item.timestamp)
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def encode_read_by_ids(entity_ids: list[str]) -> str:
        """Encode a standard ordered read-by-id request grid."""
        if not entity_ids:
            return ""
        return 'ver:"3.0"\nid\n' + "".join(f"@{entity_id}\n" for entity_id in entity_ids)

    @staticmethod
    def encode_read_by_filter(filter_expr: str) -> str:
        """Encode read operation by filter.

        Args:
            filter_expr: Haystack filter expression

        Returns:
            Zinc grid string
        """
        grid = 'ver:"3.0"\n'
        grid += "filter\n"
        # SECURITY FIX: Escape filter expression to prevent injection
        grid += f'"{_escape_zinc_string(filter_expr)}"\n'
        return grid

    @staticmethod
    def _encode_value(value: Any) -> str:
        """Encode a single value to Zinc format.

        Args:
            value: Value to encode

        Returns:
            Zinc-encoded string
        """
        if value == "":
            return ""
        if value == "m:":  # Marker tag
            return "M"
        if isinstance(value, str):
            if value.startswith("@"):  # Ref
                return value
            # Old Haystack JSON DateTime literal, e.g. "t:2024-01-01T00:00:00Z UTC".
            if value.startswith("t:"):
                return value[2:]
            # SECURITY FIX: Escape special characters to prevent injection
            return f'"{_escape_zinc_string(value)}"'
        if isinstance(value, bool):
            return "T" if value else "F"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, datetime):
            # Zinc datetime format: ISO8601 + space + timezone name
            # E.g., "2025-10-30T18:30:00-04:00 New_York"
            iso_str = value.isoformat()
            tz_name = value.tzinfo.tzname(value) if value.tzinfo else "UTC"
            return f"{iso_str} {tz_name}"
        if isinstance(value, dict) and value.get("_kind") == "dateTime":
            # Handle SkySpark DateTime dict format: {"_kind": "dateTime", "val": "...", "tz": "..."}
            val = value.get("val", "")
            tz = value.get("tz", "UTC")
            return f"{val} {tz}"
        # SECURITY FIX: Escape any other string-like values
        return f'"{_escape_zinc_string(str(value))}"'

    @staticmethod
    def _encode_datetime(value: datetime, timezone_name: str) -> str:
        """Encode a datetime with an explicit Haystack timezone name."""
        return f"{value.isoformat()} {timezone_name}"
