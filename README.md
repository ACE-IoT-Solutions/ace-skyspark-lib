# ace-skyspark-lib

Modern async Python client library for SkySpark with Pydantic validation and Project Haystack compliance.

## Features

-  **Async/await support** with httpx
-  **SCRAM-SHA-256 authentication**
-  **Type-safe Pydantic models** for sites, equipment, and points
-  **Project Haystack compliance** with Zinc format support
-  **Connection pooling** and automatic retry logic
-  **Bulk operations** with chunking and parallelization
-  **History data** read/write operations
-  **Comprehensive entity management** (CRUD operations)

## Installation

```bash
pip install ace-skyspark-lib
```

Or with uv:

```bash
uv add ace-skyspark-lib
```

## Quick Start

```python
import asyncio
from ace_skyspark_lib import SkysparkClient, Site, Equipment, Point, HistorySample
from datetime import datetime, UTC

async def main():
    # Initialize client
    async with SkysparkClient(
        base_url="http://localhost:8080/api",
        project="demo",
        username="admin",
        password="password",
        timeout=30.0,
    ) as client:
        # Read all sites
        sites = await client.read_sites()
        print(f"Found {len(sites)} sites")

        # Create a new site
        new_site = Site(
            dis="My Building",
            tz="America/New_York",
            refName="building_001",
            area_sqft=50000.0,
            marker_tags=["office"],
        )
        created = await client.create_sites([new_site])
        site_id = created[0]["id"]["val"]

        # Write history data
        samples = [
            HistorySample(
                point_id="p:demo:r:abc123",
                timestamp=datetime.now(UTC),
                value=72.5,
            )
        ]
        result = await client.write_history(samples)
        print(f"Wrote {result.samples_written} samples")

if __name__ == "__main__":
    asyncio.run(main())
```

## Authentication

The library uses SCRAM-SHA-256 authentication with automatic token management:

```python
async with SkysparkClient(
    base_url="http://localhost:8080/api",
    project="demo",
    username="your_username",
    password="your_password",
) as client:
    # Authentication happens automatically
    # Token is cached and refreshed as needed
    pass
```

## Entity Operations

### Creating Entities

```python
from ace_skyspark_lib import Site, Equipment, Point

# Create sites
sites = await client.create_sites([
    Site(dis="Building A", tz="America/New_York", refName="bldg_a"),
    Site(dis="Building B", tz="America/Chicago", refName="bldg_b"),
])

# Create equipment
equipment = await client.create_equipment([
    Equipment(
        dis="AHU-1",
        site_ref="p:demo:r:site_id",
        refName="ahu_1",
        marker_tags=["ahu", "hvac"],
    )
])

# Create points
points = await client.create_points([
    Point(
        dis="Temperature Sensor",
        kind="Number",
        unit="°F",
        site_ref="p:demo:r:site_id",
        equip_ref="p:demo:r:equip_id",
        refName="temp_sensor_1",
        marker_tags=["sensor", "temp"],
    )
])
```

### Reading Entities

```python
# Read by ID
site = await client.read_by_id("p:demo:r:site_id")

# Read with filters
equipment = await client.read_equipment(site_ref="p:demo:r:site_id")
points = await client.read_points(equip_ref="p:demo:r:equip_id")

# Read with custom filter
results = await client.read("site and area > 10000")

# Read as Pydantic models
points = await client.read_points_as_models(site_ref="p:demo:r:site_id")
for point in points:
    print(f"{point.dis}: {point.kind} ({point.unit})")
```

### Updating Entities

```python
# Update points
point = points[0]
point.marker_tags.append("critical")
point.kv_tags["priority"] = "high"

updated = await client.update_points([point])
```

### Deleting Entities

```python
# Delete by ID
await client.delete_entity("p:demo:r:entity_id")
```

## History Operations

### Writing History Data

```python
from datetime import datetime, timedelta, UTC
from ace_skyspark_lib import HistorySample

# Write single batch
now = datetime.now(UTC)
samples = [
    HistorySample(
        point_id="p:demo:r:point1",
        timestamp=now - timedelta(hours=i),
        value=70.0 + i * 0.5,
    )
    for i in range(24)
]

result = await client.write_history(samples)
print(f"Success: {result.success}, Wrote: {result.samples_written}")
```

### Bulk Writing with Chunking

```python
# Write large batches with automatic chunking
large_batch = [...]  # 10,000+ samples

results = await client.write_history_chunked(
    samples=large_batch,
    chunk_size=1000,  # Write 1000 samples per chunk
    max_concurrent=3,  # Up to 3 concurrent writes
)

total_written = sum(r.samples_written for r in results)
print(f"Wrote {total_written} samples in {len(results)} chunks")
```

## Configuration Options

```python
client = SkysparkClient(
    base_url="http://localhost:8080/api",
    project="demo",
    username="admin",
    password="password",
    timeout=30.0,        # Request timeout in seconds
    max_retries=3,       # Retry attempts for failed requests
    pool_size=10,        # HTTP connection pool size
)
```

## Error Handling

```python
from ace_skyspark_lib.exceptions import (
    AuthenticationError,
    ServerError,
    CommitError,
    SkysparkConnectionError,
)

try:
    async with SkysparkClient(...) as client:
        sites = await client.read_sites()
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except ServerError as e:
    print(f"Server error: {e}")
except SkysparkConnectionError as e:
    print(f"Connection error: {e}")
```

## Idempotent Operations

For production use, implement find-or-create patterns using `refName`:

```python
# Find existing entity by refName
all_sites = await client.read("site")
existing = [s for s in all_sites if s.get("refName") == "my_site"]

if existing:
    site_id = existing[0]["id"]["val"]
    print(f"Found existing site: {site_id}")
else:
    # Create new
    new_site = Site(dis="My Site", refName="my_site", ...)
    created = await client.create_sites([new_site])
    site_id = created[0]["id"]["val"]
    print(f"Created new site: {site_id}")
```

## Development

### Setup

```bash
# Install with dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Run linting
uv run ruff check src/
uv run ruff format src/

# Run type checking
uv run mypy src/
```

### Running Integration Tests

Create a `.env` file:

```bash
TEST_SKYSPARK_URL=http://localhost:8080/
TEST_SKYSPARK_USER=admin
TEST_SKYSPARK_PASS=password
```

Run tests:

```bash
uv run python tests/test_idempotent.py
```

## Architecture

- **httpx**: Modern async HTTP client (replaces aiohttp for compatibility)
- **Pydantic v2**: Type-safe data models with validation
- **SCRAM authentication**: Secure password-based auth
- **Zinc format**: Project Haystack compliant data serialization
- **Separate sessions**: Auth and API use separate HTTP clients to avoid SkySpark connection reuse issues

## Requirements

- Python >=3.13
- httpx >=0.27.0
- pydantic >=2.12.3
- scramp >=1.4.5
- tenacity >=8.5.0
- structlog >=24.1.0
- aceiot-models >=0.3.4

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/ace-skyspark-lib/issues
- Email: andrew@aceiotsolutions.com

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.
