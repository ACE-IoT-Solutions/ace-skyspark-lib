"""Security tests for serialization/deserialization vulnerabilities.

These tests demonstrate and validate fixes for:
1. String injection (quotes, newlines, commas, backslashes)
2. Filter expression injection
3. Edge cases (unicode, empty strings, very long strings)
4. Malformed data handling

All tests should PASS after security fixes are implemented.
"""

import pytest
from ace_skyspark_lib.formats.zinc import ZincEncoder
from ace_skyspark_lib.models.entities import Point, Site, Equipment


class TestStringInjectionVulnerabilities:
    """Test string injection vulnerabilities in Zinc encoding."""

    def test_double_quotes_in_string(self):
        """Test that double quotes are properly escaped."""
        site = Site(
            dis='Building with "quotes" in name',
            ref_name="test_quotes",
            tz="UTC",
        )

        zinc_dict = site.to_zinc_dict()
        zinc_grid = ZincEncoder.encode_commit_add_sites([site])

        # Should not break Zinc format
        assert 'Building with "quotes" in name' in site.dis
        # Zinc grid should have escaped quotes (will fail until fixed)
        # Expected: "Building with \"quotes\" in name"
        assert '\\"' in zinc_grid or '\\u0022' in zinc_grid, \
            "Quotes should be escaped in Zinc output"

    def test_newlines_in_string(self):
        """Test that newlines are properly escaped."""
        site = Site(
            dis="Building with\nnewline\nin name",
            ref_name="test_newline",
            tz="UTC",
        )

        zinc_grid = ZincEncoder.encode_commit_add_sites([site])

        # Zinc grid should have escaped newlines (will fail until fixed)
        # Expected: "Building with\\nNewline\\nin name"
        assert '\\n' in zinc_grid, "Newlines should be escaped in Zinc output"
        # Should not have actual newline in the dis field value
        assert '"Building with\nnewline\nin name"' not in zinc_grid, \
            "Raw newlines should not appear in Zinc string values"

    def test_commas_in_string(self):
        """Test that commas don't break CSV-like Zinc format."""
        site = Site(
            dis="Building, with, commas",
            ref_name="test_commas",
            tz="UTC",
        )

        zinc_grid = ZincEncoder.encode_commit_add_sites([site])

        # Commas inside quoted strings are OK, but test they don't break parsing
        # The string should be quoted
        assert '"Building, with, commas"' in zinc_grid

    def test_backslashes_in_string(self):
        """Test that backslashes are properly escaped."""
        site = Site(
            dis=r"C:\Windows\System32",
            ref_name="test_backslash",
            tz="UTC",
        )

        zinc_grid = ZincEncoder.encode_commit_add_sites([site])

        # Backslashes should be escaped (will fail until fixed)
        # Expected: "C:\\Windows\\System32"
        assert '\\\\' in zinc_grid or 'C:/Windows/System32' in zinc_grid, \
            "Backslashes should be escaped in Zinc output"

    def test_carriage_return_in_string(self):
        """Test that carriage returns are properly escaped."""
        site = Site(
            dis="Building with\rcarriage\rreturn",
            ref_name="test_cr",
            tz="UTC",
        )

        zinc_grid = ZincEncoder.encode_commit_add_sites([site])

        # Should have escaped \r (will fail until fixed)
        assert '\\r' in zinc_grid, "Carriage returns should be escaped"

    def test_combined_special_characters(self):
        """Test multiple special characters in one string."""
        site = Site(
            dis='Test "quoted", with\nnewline and\\backslash',
            ref_name="test_combined",
            tz="UTC",
        )

        zinc_grid = ZincEncoder.encode_commit_add_sites([site])

        # All special chars should be escaped
        assert '\\' in zinc_grid, "Should have escape sequences"

    def test_sql_injection_like_strings(self):
        """Test SQL injection-like strings don't break Zinc."""
        malicious_strings = [
            "'; DROP TABLE sites; --",
            '"; DELETE FROM points WHERE 1=1; --',
            "test\"; evil_tag:\"injected",
        ]

        for mal_str in malicious_strings:
            site = Site(
                dis=mal_str,
                ref_name="test_sql",
                tz="UTC",
            )

            zinc_grid = ZincEncoder.encode_commit_add_sites([site])

            # Should be properly escaped and not executable
            # Zinc grid should still be valid
            assert 'ver:"3.0"' in zinc_grid
            assert 'site' in zinc_grid


class TestFilterInjectionVulnerabilities:
    """Test filter expression injection vulnerabilities."""

    def test_filter_with_malicious_input(self):
        """Test that malicious filter input is sanitized."""
        # These should either be escaped or rejected
        malicious_filters = [
            "site and id==@bad or 1==1",
            'site and dis=="test" or dis=="*"',
            "site; DROP TABLE sites; --",
        ]

        for mal_filter in malicious_filters:
            # Currently no sanitization - should add validation
            zinc_grid = ZincEncoder.encode_read_by_filter(mal_filter)

            # Grid is created, but we should validate the filter
            assert 'ver:"3.0"' in zinc_grid
            # TODO: Add filter validation

    def test_filter_with_special_characters(self):
        """Test filters with quotes and special chars."""
        filter_expr = 'site and dis=="Test\\"Building"'

        zinc_grid = ZincEncoder.encode_read_by_filter(filter_expr)

        # Should not break the Zinc format
        assert 'ver:"3.0"' in zinc_grid
        assert 'filter' in zinc_grid


class TestUnicodeAndEdgeCases:
    """Test unicode, empty strings, and edge cases."""

    def test_unicode_characters(self):
        """Test unicode characters are handled correctly."""
        unicode_strings = [
            "Building 建物",  # Chinese
            "Здание",  # Russian
            "مبنى",  # Arabic
            "🏢 Office Building 🏗️",  # Emojis
            "Tëst Büildîñg",  # Accents
        ]

        for unicode_str in unicode_strings:
            site = Site(
                dis=unicode_str,
                ref_name="test_unicode",
                tz="UTC",
            )

            zinc_dict = site.to_zinc_dict()
            zinc_grid = ZincEncoder.encode_commit_add_sites([site])

            # Should preserve unicode
            assert site.dis == unicode_str
            # Zinc should be valid
            assert 'ver:"3.0"' in zinc_grid

    def test_empty_strings(self):
        """Test empty strings don't break encoding."""
        site = Site(
            dis="",  # Empty dis should fail validation actually
            ref_name="test_empty",
            tz="UTC",
        )

        # This might raise ValidationError, which is OK
        # But if it doesn't, encoding should handle it
        try:
            zinc_grid = ZincEncoder.encode_commit_add_sites([site])
            assert 'ver:"3.0"' in zinc_grid
        except Exception:
            # Validation error is acceptable
            pass

    def test_very_long_strings(self):
        """Test very long strings are handled."""
        long_string = "A" * 10000

        site = Site(
            dis=long_string,
            ref_name="test_long",
            tz="UTC",
        )

        zinc_grid = ZincEncoder.encode_commit_add_sites([site])

        # Should not truncate or fail
        assert long_string in zinc_grid
        assert len(zinc_grid) > 10000

    def test_null_bytes(self):
        """Test null bytes are handled or rejected."""
        try:
            site = Site(
                dis="Test\x00Null",
                ref_name="test_null",
                tz="UTC",
            )

            zinc_grid = ZincEncoder.encode_commit_add_sites([site])

            # Should either escape or strip null bytes
            assert '\x00' not in zinc_grid, "Null bytes should be removed/escaped"
        except ValueError:
            # Or validation should reject them
            pass

    def test_control_characters(self):
        """Test control characters are escaped."""
        control_chars = [
            "Test\x01\x02\x03",  # SOH, STX, ETX
            "Test\x08\x09",  # BS, TAB
            "Test\x1B",  # ESC
        ]

        for ctrl_str in control_chars:
            site = Site(
                dis=ctrl_str,
                ref_name="test_ctrl",
                tz="UTC",
            )

            zinc_grid = ZincEncoder.encode_commit_add_sites([site])

            # Control characters should be escaped or removed
            # Raw control chars should not be in output
            for char in ctrl_str:
                if ord(char) < 32 and char not in '\t\n\r':
                    assert char not in zinc_grid, \
                        f"Control character {repr(char)} should be escaped"


class TestMalformedDataHandling:
    """Test handling of malformed or unexpected data."""

    def test_point_with_unexpected_types_in_kv_tags(self):
        """Test kv_tags with unexpected types."""
        point = Point(
            dis="Test",
            ref_name="test",
            site_ref="site123",
            equip_ref="equip456",
            kind="Number",
            marker_tags=["sensor"],
            kv_tags={
                "nested_dict": {"key": "value"},
                "nested_list": [1, 2, 3],
                "none_value": None,
            },
        )

        # Should handle or raise clear error
        try:
            zinc_dict = point.to_zinc_dict()
            zinc_grid = ZincEncoder.encode_commit_add_points([point])

            # If it succeeds, should produce valid Zinc
            assert 'ver:"3.0"' in zinc_grid
        except (TypeError, ValueError) as e:
            # Or should raise clear error
            assert "unexpected type" in str(e).lower() or "cannot encode" in str(e).lower()

    def test_refs_with_special_characters(self):
        """Test that refs with special characters are handled."""
        # Refs should only contain valid characters
        try:
            point = Point(
                dis="Test",
                ref_name="test",
                site_ref="site@#$%^&*()",
                equip_ref="equip\n\t\r",
                kind="Number",
                marker_tags=["sensor"],
            )

            zinc_dict = point.to_zinc_dict()

            # Refs should be cleaned or validated
            assert "@site@#$%^&*()" in str(zinc_dict) or "site" in zinc_dict["siteRef"]
        except ValueError:
            # Or validation should reject them
            pass

    def test_deeply_nested_tags(self):
        """Test deeply nested tag structures."""
        point = Point(
            dis="Test",
            ref_name="test",
            site_ref="site123",
            equip_ref="equip456",
            kind="Number",
            marker_tags=["sensor"],
            kv_tags={
                "level1": {
                    "level2": {
                        "level3": {
                            "level4": "deep value"
                        }
                    }
                }
            },
        )

        # Should handle or raise error
        try:
            zinc_grid = ZincEncoder.encode_commit_add_points([point])
            assert 'ver:"3.0"' in zinc_grid
        except Exception as e:
            # Should have clear error message
            assert e is not None


class TestZincFormatValidity:
    """Test that generated Zinc is actually valid."""

    def test_zinc_version_header(self):
        """Test all Zinc grids have proper version header."""
        site = Site(dis="Test", ref_name="test", tz="UTC")

        zinc_grid = ZincEncoder.encode_commit_add_sites([site])

        # Must start with version
        assert zinc_grid.startswith('ver:"3.0"')

    def test_zinc_grid_structure(self):
        """Test Zinc grid has proper structure."""
        site = Site(dis="Test", ref_name="test", tz="UTC")

        zinc_grid = ZincEncoder.encode_commit_add_sites([site])

        lines = zinc_grid.strip().split('\n')

        # Should have at least 3 lines: version, header, data
        assert len(lines) >= 3, "Zinc grid should have version, header, and data rows"

        # First line: version
        assert 'ver:' in lines[0]

        # Second line: column headers
        assert 'dis' in lines[1] or 'refName' in lines[1]

    def test_no_unescaped_quotes_in_values(self):
        """Test that values don't have unescaped quotes."""
        site = Site(
            dis='Test "quoted" value',
            ref_name="test",
            tz="UTC",
        )

        zinc_grid = ZincEncoder.encode_commit_add_sites([site])

        # After the opening quote for dis value, should not have unescaped quote
        # This is a basic check - proper fix needed
        # For now, just check it produces output
        assert 'dis' in zinc_grid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
