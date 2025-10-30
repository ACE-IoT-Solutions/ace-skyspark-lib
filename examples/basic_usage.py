"""Basic usage examples for ace-skyspark-lib.

This script demonstrates common workflows:
- Connecting to SkySpark
- Reading sites, equipment, and points
- Creating entities with Pydantic validation
- Updating point tags
- Writing history data
"""

from datetime import UTC, datetime, timedelta

from ace_skyspark_lib import (
    Equipment,
    HistorySample,
    Point,
    Site,
    SkysparkClient,
)


async def example_read_entities() -> None:
    """Example: Reading sites, equipment, and points."""
    async with SkysparkClient(
        base_url="http://localhost:8080/api",
        project="demo",
        username="su",
        password="password",
    ) as client:
        # Read all sites
        sites = await client.read_sites()
        print(f"Found {len(sites)} sites")

        # Read equipment for first site
        if sites:
            site_id = sites[0]["id"]
            equipment = await client.read_equipment(site_ref=site_id)
            print(f"Found {len(equipment)} equipment in site {sites[0]['dis']}")

        # Read points as Pydantic models
        points = await client.read_points_as_models()
        print(f"Found {len(points)} points")

        # Filter numeric sensors
        numeric_sensors = [p for p in points if p.kind == "Number" and "sensor" in p.marker_tags]
        print(f"Found {len(numeric_sensors)} numeric sensor points")


async def example_create_site() -> None:
    """Example: Creating a new site with Pydantic validation."""
    async with SkysparkClient(
        base_url="http://localhost:8080/api",
        project="demo",
        username="su",
        password="password",
    ) as client:
        # Create site with Pydantic model
        site = Site(
            dis="Example Building",
            tz="America/New_York",  # Validated against IANA timezone database
            refName="example_bldg",
            area_sqft=10000.0,
            marker_tags=["office", "commercial"],
            kv_tags={"region": "Northeast", "yearBuilt": "2020"},
        )

        created = await client.create_sites([site])
        print(f"Created site with ID: {created[0]['id']}")


async def example_create_equipment_and_point() -> None:
    """Example: Creating equipment and point hierarchy."""
    async with SkysparkClient(
        base_url="http://localhost:8080/api",
        project="demo",
        username="su",
        password="password",
    ) as client:
        # Get site reference
        sites = await client.read_sites()
        site_id = sites[0]["id"]

        # Create equipment
        equipment = Equipment(
            dis="AHU-1",
            site_ref=site_id,
            refName="ahu_1",
            marker_tags=["ahu", "hvac"],
            kv_tags={"floor": "2", "zone": "North"},
        )
        created_equip = await client.create_equipment([equipment])
        equip_id = created_equip[0]["id"]

        # Create point
        point = Point(
            dis="AHU-1 Supply Air Temp",
            kind="Number",
            unit="°F",
            site_ref=site_id,
            equip_ref=equip_id,
            refName="ahu1_sat",
            marker_tags=[
                "sensor",
                "temp",
                "air",
                "supply",
            ],  # Must have exactly one function marker
            kv_tags={"precision": "1", "minVal": "32", "maxVal": "120"},
        )
        created_point = await client.create_points([point])
        print(f"Created point with ID: {created_point[0]['id']}")


async def example_update_point_tags() -> None:
    """Example: Updating tags on an existing point."""
    async with SkysparkClient(
        base_url="http://localhost:8080/api",
        project="demo",
        username="su",
        password="password",
    ) as client:
        # Read existing points
        points = await client.read_points_as_models()
        if not points:
            print("No points available to update")
            return

        # Get first point and update its tags
        point = points[0]
        if not point.id:
            print("Point missing ID")
            return

        # Add new marker and update KV tag
        point.marker_tags.append("commissioned")
        point.kv_tags["lastInspection"] = datetime.now(UTC).isoformat()

        # Update via API
        updated = await client.update_points([point])
        print(f"Updated point: {updated[0]['dis']}")


async def example_write_history() -> None:
    """Example: Writing history samples."""
    async with SkysparkClient(
        base_url="http://localhost:8080/api",
        project="demo",
        username="su",
        password="password",
    ) as client:
        # Get a numeric sensor point
        points = await client.read_points_as_models()
        numeric_sensors = [p for p in points if p.kind == "Number" and "sensor" in p.marker_tags]

        if not numeric_sensors or not numeric_sensors[0].id:
            print("No numeric sensor points available")
            return

        point_id = numeric_sensors[0].id

        # Create history samples (last 24 hours, hourly readings)
        now = datetime.now(UTC)
        samples = [
            HistorySample(
                point_id=point_id,
                timestamp=now - timedelta(hours=24 - i),  # Must be timezone-aware
                value=70.0 + (i % 10),  # Simulated temperature readings
            )
            for i in range(24)
        ]

        # Write samples
        result = await client.write_history(samples)
        print(f"Wrote {result.samples_written} samples")


async def example_write_history_bulk() -> None:
    """Example: Writing large batches with chunking."""
    async with SkysparkClient(
        base_url="http://localhost:8080/api",
        project="demo",
        username="su",
        password="password",
    ) as client:
        # Get multiple numeric sensor points
        points = await client.read_points_as_models()
        numeric_sensors = [p for p in points if p.kind == "Number" and "sensor" in p.marker_tags][
            :5
        ]  # Use up to 5 points

        if not numeric_sensors:
            print("No numeric sensor points available")
            return

        # Create large batch of samples (1000 samples per point)
        samples = []
        now = datetime.now(UTC)

        for point in numeric_sensors:
            if not point.id:
                continue
            for i in range(1000):
                samples.append(
                    HistorySample(
                        point_id=point.id,
                        timestamp=now - timedelta(minutes=1000 - i),
                        value=50.0 + (i % 100) * 0.5,
                    )
                )

        # Write with automatic chunking and parallelization
        results = await client.write_history_chunked(
            samples,
            chunk_size=1000,  # Write 1000 samples per chunk
            max_concurrent=3,  # Max 3 concurrent writes
        )

        total_written = sum(r.samples_written for r in results)
        failed = sum(1 for r in results if not r.success)
        print(f"Wrote {total_written} samples in {len(results)} chunks ({failed} failed)")


async def example_query_and_filter() -> None:
    """Example: Using Haystack filter expressions."""
    async with SkysparkClient(
        base_url="http://localhost:8080/api",
        project="demo",
        username="su",
        password="password",
    ) as client:
        # Filter for specific entity types
        sites = await client.read("site")
        print(f"Found {len(sites)} sites")

        # Filter for equipment in a specific site
        equipment = await client.read("equip and siteRef==@site123")
        print(f"Found {len(equipment)} equipment in site")

        # Filter for temperature sensor points
        temp_sensors = await client.read("point and sensor and temp")
        print(f"Found {len(temp_sensors)} temperature sensors")

        # Read specific entity by ID
        entity = await client.read_by_id("p:demo:r:abc123")
        if entity:
            print(f"Found entity: {entity['dis']}")


def main() -> None:
    """Run examples."""
    print("=== ace-skyspark-lib Usage Examples ===\n")

    # Uncomment the examples you want to run:

    # asyncio.run(example_read_entities())
    # asyncio.run(example_create_site())
    # asyncio.run(example_create_equipment_and_point())
    # asyncio.run(example_update_point_tags())
    # asyncio.run(example_write_history())
    # asyncio.run(example_write_history_bulk())
    # asyncio.run(example_query_and_filter())

    print("\nExamples are commented out. Uncomment to run with your SkySpark instance.")
    print("Update connection parameters (base_url, project, username, password) as needed.")


if __name__ == "__main__":
    main()
