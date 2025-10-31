"""Zinc grid encoding for Haystack operations."""

from datetime import datetime
from typing import Any

from ace_skyspark_lib.models.entities import Equipment, Point, Site
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
    s = s.replace('\\', '\\\\')  # Backslash MUST be first!
    s = s.replace('"', '\\"')    # Double quotes
    s = s.replace('\n', '\\n')   # Newline
    s = s.replace('\r', '\\r')   # Carriage return
    s = s.replace('\t', '\\t')   # Tab

    # Remove null bytes (can truncate strings in C-based parsers)
    s = s.replace('\x00', '')

    # Remove control characters (except tab, newline, carriage return which we've already escaped)
    # Control characters are 0x00-0x1F except \t(0x09), \n(0x0A), \r(0x0D)
    s = ''.join(c for c in s if ord(c) >= 32 or c in '\t\n\r')

    return s


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
            all_tags.update(site.to_zinc_dict().keys())
        all_tags.discard("id")  # Don't include id in add operations

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
            all_tags.update(equip.to_zinc_dict().keys())
        all_tags.discard("id")

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
            all_tags.update(point.to_zinc_dict().keys())
        all_tags.discard("id")

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
            all_tags.update(point.to_zinc_dict().keys())

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
            # Get timezone name
            tz_name = (
                sample.timestamp.tzinfo.tzname(sample.timestamp)
                if sample.timestamp.tzinfo
                else "UTC"
            )

            # Format value
            if isinstance(sample.value, bool):
                val_str = str(sample.value).lower()
            elif isinstance(sample.value, str):
                # SECURITY FIX: Escape string values to prevent injection
                val_str = f'"{_escape_zinc_string(sample.value)}"'
            else:
                val_str = str(sample.value)

            # Build hisWrite expression
            expr = (
                f'"hisWrite('
                f'{{ts: parseDateTime(\\"{sample.timestamp.isoformat()}\\", \\"YYYY-MM-DDThh:mm:ssz\\", \\"{tz_name}\\"), '
                f"val: {val_str}}}, "
                f'@{sample.point_id})"\n'
            )
            grid += expr

        return grid

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
        # SECURITY FIX: Escape any other string-like values
        return f'"{_escape_zinc_string(str(value))}"'
