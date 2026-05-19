# ace-skyspark-lib

Modern async Python client library for SkySpark with Pydantic validation and Project Haystack compliance. Part of the **ACE IoT Ecosystem**.

## Features

- 🚀 **Async/await support** with `httpx`
- 🔒 **SCRAM-SHA-256 authentication** with automatic token refresh
- ✅ **Type-safe Pydantic models** for sites, equipment, and points
- 📊 **Project Haystack compliance** with Zinc format support
- 🔄 **Connection pooling** and robust retry logic
- 📦 **Bulk operations** with chunking and optimistic locking
- 📈 **History data** paginated read/write operations
- 🧩 **Seamless integration** with `aceiot-models`

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

        # Create a new site using the ACE IoT model pattern
        new_site = Site(
            dis="My Building",
            tz="America/New_York",
            refName="building_001",
            area=50000.0,
            marker_tags=["office"],
            kv_tags={"priority": "high"}
        )
        created = await client.create_sites([new_site])
        site_id = created[0]["id"]

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

## ACE IoT Ecosystem Integration

This library is designed to work seamlessly with the [aceiot-models](https://github.com/ace-iot-solutions/aceiot-models) package. It uses these models for data validation and standardized pagination, making it an ideal choice for large-scale building automation and energy management applications.

## Authentication

The library uses SCRAM-SHA-256 authentication with automatic token management and proactive 401 handling:

```python
async with SkysparkClient(
    base_url="http://localhost:8080/api",
    project="demo",
    username="your_username",
    password="your_password",
) as client:
    # Authentication happens automatically
    # Token is cached and refreshed automatically if it expires (401 response)
    pass
```

## Entity Operations

### Creating Entities

The library uses a consistent `marker_tags` (list) and `kv_tags` (dict) pattern for all entity types:

```python
from ace_skyspark_lib import Site, Equipment, Point

# Create sites
sites = await client.create_sites([
    Site(
        dis="Building A", 
        tz="America/New_York", 
        refName="bldg_a",
        marker_tags=["commercial"],
        kv_tags={"region": "east"}
    )
])

# Create equipment
equipment = await client.create_equipment([
    Equipment(
        dis="AHU-1",
        site_ref="site_id",
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
        site_ref="site_id",
        equip_ref="equip_id",
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
equipment = await client.read_equipment(site_ref="site_id")
points = await client.read_points(equip_ref="equip_id")

# Read as Pydantic models (recommended)
points = await client.read_points_as_models(site_ref="site_id")
for point in points:
    print(f"{point.dis}: markers={point.marker_tags}, tags={point.kv_tags}")
```

### Deleting Entities

```python
# Delete single entity (automatically fetches 'mod' for safety)
await client.delete_entity("p:demo:r:entity_id")

# Bulk delete (requires entities with 'id' and 'mod' for optimistic locking)
entities_to_delete = await client.read("point and junk")
await client.delete_entities(entities_to_delete)
```

## History Operations

### Reading History (Paginated)

The library supports paginated history reading via the ACE IoT timeseries endpoint, preventing timeouts on large datasets:

```python
from datetime import datetime, timedelta, UTC

# Read a single page
response = await client.read_history(
    point_id="point_id",
    start_time=datetime.now(UTC) - timedelta(days=7),
    end_time=datetime.now(UTC),
    page=1,
    per_page=1000
)
print(f"Total samples: {response.total}, Pages: {response.pages}")

# Fetch ALL history across all pages automatically
all_samples = await client.read_history_all(
    point_id="point_id",
    start_time=datetime.now(UTC) - timedelta(days=30),
    end_time=datetime.now(UTC)
)
```

### Writing History Data

```python
from ace_skyspark_lib import HistorySample

# Write single batch
samples = [
    HistorySample(point_id="p1", timestamp=now, value=72.5),
    HistorySample(point_id="p1", timestamp=now + timedelta(minutes=5), value=72.6),
]

result = await client.write_history(samples)
```

### Bulk Writing with Chunking

```python
# Write large batches with automatic chunking and parallel execution
results = await client.write_history_chunked(
    samples=large_batch,
    chunk_size=1000,
    max_concurrent=3
)
```

## Configuration Options

```python
client = SkysparkClient(
    base_url="http://localhost:8080/api",
    project="demo",
    username="admin",
    password="password",
    timeout=30.0,        # Request timeout in seconds
    max_retries=3,       # Retry attempts for failed requests (including 401s)
    pool_size=10,        # HTTP connection pool size
)
```

## Development

### Setup

```bash
uv sync --dev
uv run pytest
```

### Running Integration Tests

Create a `.env` file:

```bash
TEST_SKYSPARK_URL=http://localhost:8080/
TEST_SKYSPARK_PROJECT=demo
TEST_SKYSPARK_USER=admin
TEST_SKYSPARK_PASS=password
```

## Architecture

- **httpx**: Modern async HTTP client with connection pooling
- **Pydantic v2**: Rust-powered data validation and serialization
- **SCRAM**: Industry-standard secure authentication
- **Paginated API**: Predictable performance for large data volumes
- **Separated Concerns**: Modular design for auth, operations, and models

## Requirements

- Python >=3.13
- aceiot-models >=0.3.4
- httpx >=0.27.0
- pydantic >=2.12.3

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: https://github.com/ace-iot-solutions/ace-skyspark-lib/issues
- Email: andrew@aceiotsolutions.com

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.
