# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.6] - 2025-11-01

### Changed
- Improved `get_project_timezone()` with two-tier fallback strategy
  - First tries to get timezone from project entity (with `proj` marker)
  - Falls back to `about` endpoint if project entity doesn't have timezone
  - More accurate timezone detection using project-specific settings
- Enhanced logging to indicate timezone source (project entity vs about endpoint)
- Better error handling with warnings instead of failures when reading project entity

## [0.1.5] - 2025-11-01

### Changed
- Version bump for maintenance release

## [0.1.4] - 2025-11-01

### Added
- Equipment update operations with `update_equipment()` method
  - Added to both `EntityOperations` and `SkysparkClient`
  - Includes validation that equipment have IDs before updating
  - Uses `encode_commit_update_equipment()` for proper Zinc serialization
- New `get_project_timezone()` method to retrieve project default timezone
- Dict datetime format handling in `ZincEncoder._encode_value()`
  - Handles SkySpark DateTime dict format: `{"_kind": "dateTime", "val": "...", "tz": "..."}`

### Changed
- **Relaxed timezone validation for SkySpark compatibility**
  - Now accepts any non-empty string instead of strict IANA timezone validation
  - Allows SkySpark-specific timezone names that may differ from pytz database
  - Updated validators in Site, Equipment, and Point models
  - Updated test suite to reflect new validation behavior

### Fixed
- Empty string keys no longer added to Zinc grid headers
  - Added filtering: `valid_keys = {k for k in zinc_dict.keys() if k and k.strip()}`
  - Prevents malformed Zinc grids with empty column names

## [0.1.3] - 2025-10-31

### Fixed
- **CRITICAL**: Fixed delete operation to include `mod` field for SkySpark optimistic locking
  - Delete operations were failing with "haystack::UnknownNameErr: mod" error
  - Now reads entity before delete to get current mod timestamp
  - Properly formats mod field in Zinc datetime format
  - Re-enabled delete cleanup in integration tests
- Fixed `delete_entity()` to handle dict-format entity IDs from SkySpark responses
  - Accepts both `str` and `dict[str, Any]` entity_id formats
  - Extracts ID from `{"_kind": "ref", "val": "...", "dis": "..."}` format
- Added missing `from typing import Any` import in client.py

### Added
- Delete operation now uses read-before-delete pattern for optimistic locking
- Improved entity_id handling throughout delete operations

### Changed
- Delete operations now require two API calls (read + delete) for safety
- Integration tests now successfully clean up created test entities

## [0.1.2] - 2025-10-30

### Security
- **CRITICAL**: Fixed string injection vulnerabilities in Zinc encoding
  - Implemented `_escape_zinc_string()` function to escape special characters
  - Fixed unescaped double quotes that could break Zinc format parsing
  - Fixed unescaped newlines that could break grid structure
  - Fixed unescaped backslashes that could interfere with escape sequences
  - Removed null bytes that could truncate strings in C-based parsers
  - Removed control characters that could cause parser issues
  - Applied escaping to all string values, filter expressions, and history writes

### Added
- Comprehensive security test suite (20 tests) in `tests/test_security_vulnerabilities.py`
- `SECURITY_TEST_BASELINE.md` documenting all security vulnerabilities and fixes
- String escaping for injection prevention in all Zinc serialization

### Fixed
- Integration test configuration (added `TEST_SKYSPARK_PROJECT` environment variable)
- Test suite base URL handling for proper authentication
- Point update test to handle Haystack tag omission vs removal semantics

### Changed
- All Zinc string encoding now uses proper escaping for security
- Risk level reduced from **HIGH** to **LOW** after security fixes

## [0.1.1] - 2025-10-30

### Fixed
- **CRITICAL**: Fixed point update operations that were completely broken due to mod field datetime round-trip issue
  - Point.from_zinc_dict() now properly converts Zinc datetime dicts to Python datetime objects
  - ZincEncoder now correctly formats datetime values with timezone names for SkySpark compatibility
  - Added proper timezone handling using pytz for named timezones
  - Resolved ClassCastException and ParseErr errors when updating points with mod timestamps

### Added
- test_mod_roundtrip.py: Unit test for datetime field encoding
- test_point_update.py: Integration test verifying point updates work end-to-end

## [0.1.0] - 2025-10-30

### Added
- Initial release of ace-skyspark-lib
- Async/await support using httpx HTTP client
- SCRAM-SHA-256 authentication with automatic token management
- Type-safe Pydantic models for sites, equipment, and points
- Project Haystack compliance with Zinc format support
- Connection pooling and automatic retry logic with exponential backoff
- Bulk history write operations with chunking and parallelization
- Comprehensive entity management (create, read, update, delete)
- History data read/write operations
- Query operations with filter support
- Idempotent operations support using refName attributes
- Comprehensive error handling and custom exceptions
- Full async context manager support
- Structured logging with structlog

### Architecture
- Separate HTTP sessions for authentication and API calls to resolve SkySpark connection reuse issues
- httpx library chosen over aiohttp for better SkySpark compatibility
- Modular architecture with separate modules for auth, HTTP, operations, and models
- Pydantic v2 for data validation and serialization

### Testing
- Unit tests for all core functionality
- Integration tests with real SkySpark server
- Idempotent test suite to verify no duplicate entity creation

### Documentation
- Comprehensive README with examples
- API documentation through type hints
- Development setup instructions
