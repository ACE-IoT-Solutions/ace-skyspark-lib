# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
