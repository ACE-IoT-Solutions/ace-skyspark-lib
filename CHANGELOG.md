# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
