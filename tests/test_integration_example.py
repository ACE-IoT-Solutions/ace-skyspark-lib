"""Integration test example for ace-skyspark-lib.

This test demonstrates the complete workflow:
1. Connect and authenticate
2. Read existing entities (sites, equipment, points)
3. Create new entities if needed
4. Update point tags
5. Write history samples

NOTE: Requires .env file with TEST_SKYSPARK_* credentials.
"""

import os
from datetime import UTC, datetime, timedelta

import pytest
from dotenv import load_dotenv

from ace_skyspark_lib import (
    Equipment,
    HistorySample,
    Point,
    Site,
    SkysparkClient,
)
from ace_skyspark_lib.exceptions import CommitError, EntityNotFoundError

# Load test credentials from .env
load_dotenv()

TEST_URL = os.getenv("TEST_SKYSPARK_URL")
TEST_PROJECT = os.getenv("TEST_SKYSPARK_PROJECT", "demo")
TEST_USER = os.getenv("TEST_SKYSPARK_USER")
TEST_PASS = os.getenv("TEST_SKYSPARK_PASS")

# Skip integration tests if credentials not provided
pytestmark = pytest.mark.skipif(
    not all([TEST_URL, TEST_USER, TEST_PASS]),
    reason="Integration test credentials not provided in .env",
)


@pytest.mark.asyncio
async def test_integration_workflow() -> None:
    """Complete integration test workflow."""
    async with SkysparkClient(
        base_url=TEST_URL,
        project=TEST_PROJECT,
        username=TEST_USER,
        password=TEST_PASS,
    ) as client:
        # Step 1: Read existing sites
        sites = await client.read_sites()
        print(f"\n✓ Found {len(sites)} sites")

        # Step 2: Read equipment (limit to first site if multiple exist)
        site_ref = sites[0]["id"] if sites else None
        equipment = await client.read_equipment(site_ref=site_ref)
        print(f"✓ Found {len(equipment)} equipment")

        # Step 3: Read points
        points = await client.read_points_as_models(site_ref=site_ref)
        print(f"✓ Found {len(points)} points")

        # Display first point details if available
        if points:
            point = points[0]
            print(f"\n  Example point: {point.dis}")
            print(f"  Kind: {point.kind}")
            print(f"  Markers: {point.marker_tags[:5]}")  # First 5 markers

        # Step 4: Filter for numeric sensor points
        numeric_sensors = [p for p in points if p.kind == "Number" and "sensor" in p.marker_tags]
        print(f"✓ Found {len(numeric_sensors)} numeric sensor points")

        assert len(sites) > 0, "No sites found - check test environment"
        assert len(points) > 0, "No points found - check test environment"


@pytest.mark.asyncio
async def test_integration_create_site() -> None:
    """Test creating a new site."""
    async with SkysparkClient(
        base_url=TEST_URL,
        project=TEST_PROJECT,
        username=TEST_USER,
        password=TEST_PASS,
    ) as client:
        # Create test site
        test_site = Site(
            dis="Integration Test Site",
            tz="America/New_York",
            refName="test_site_001",
            area_sqft=5000.0,
            marker_tags=["office"],
            kv_tags={"testRun": "true"},
        )

        created_sites = await client.create_sites([test_site])
        assert len(created_sites) == 1
        assert "id" in created_sites[0]
        print(f"\n✓ Created site with ID: {created_sites[0]['id']}")

        # Clean up - delete the test site
        site_id = created_sites[0]["id"]
        await client.delete_entity(site_id)
        print(f"✓ Cleaned up test site: {site_id}")


@pytest.mark.asyncio
async def test_integration_create_point() -> None:
    """Test creating equipment and point."""
    async with SkysparkClient(
        base_url=TEST_URL,
        project=TEST_PROJECT,
        username=TEST_USER,
        password=TEST_PASS,
    ) as client:
        # Get first site for reference
        sites = await client.read_sites()
        assert len(sites) > 0, "No sites available for test"
        site_id = sites[0]["id"]

        # Create test equipment
        test_equip = Equipment(
            dis="Integration Test Equipment",
            site_ref=site_id,
            refName="test_equip_001",
            marker_tags=["ahu"],
            kv_tags={"testRun": "true"},
        )

        created_equip = await client.create_equipment([test_equip])
        assert len(created_equip) == 1
        equip_id = created_equip[0]["id"]
        print(f"\n✓ Created equipment with ID: {equip_id}")

        # Create test point
        test_point = Point(
            dis="Integration Test Point",
            kind="Number",
            unit="°F",
            site_ref=site_id,
            equip_ref=equip_id,
            refName="test_point_001",
            marker_tags=["sensor", "temp", "air"],
            kv_tags={"testRun": "true"},
        )

        created_points = await client.create_points([test_point])
        assert len(created_points) == 1
        point_id = created_points[0]["id"]
        print(f"✓ Created point with ID: {point_id}")

        # Clean up - delete point and equipment
        await client.delete_entity(point_id)
        await client.delete_entity(equip_id)
        print("✓ Cleaned up test entities")


@pytest.mark.asyncio
async def test_integration_update_point() -> None:
    """Test updating point tags."""
    async with SkysparkClient(
        base_url=TEST_URL,
        project=TEST_PROJECT,
        username=TEST_USER,
        password=TEST_PASS,
    ) as client:
        # Get first site and equipment
        sites = await client.read_sites()
        site_id = sites[0]["id"]
        equipment = await client.read_equipment(site_ref=site_id)

        if not equipment:
            pytest.skip("No equipment available for point update test")

        equip_id = equipment[0]["id"]

        # Create a point to update
        test_point = Point(
            dis="Update Test Point",
            kind="Number",
            unit="°F",
            site_ref=site_id,
            equip_ref=equip_id,
            refName="update_test_001",
            marker_tags=["sensor", "temp"],
            kv_tags={"version": "1"},
        )

        created = await client.create_points([test_point])
        point_id = created[0]["id"]
        print(f"\n✓ Created point for update test: {point_id}")

        # Update the point - add new marker and update kv tag
        updated_point = Point(
            id=point_id,
            dis="Updated Test Point",
            kind="Number",
            unit="°F",
            site_ref=site_id,
            equip_ref=equip_id,
            refName="update_test_001",
            marker_tags=["sensor", "temp", "outside"],  # Added 'outside'
            kv_tags={"version": "2", "updated": "true"},  # Updated and added tags
        )

        updated = await client.update_points([updated_point])
        assert len(updated) == 1
        print("✓ Updated point tags")

        # Verify update by reading back
        read_point = await client.read_by_id(point_id)
        assert read_point is not None
        assert read_point.get("dis") == "Updated Test Point"
        print(f"✓ Verified updated point: {read_point['dis']}")

        # Clean up
        await client.delete_entity(point_id)
        print("✓ Cleaned up test point")


@pytest.mark.asyncio
async def test_integration_write_history() -> None:
    """Test writing history samples."""
    async with SkysparkClient(
        base_url=TEST_URL,
        project=TEST_PROJECT,
        username=TEST_USER,
        password=TEST_PASS,
    ) as client:
        # Get a numeric sensor point
        points = await client.read_points_as_models()
        numeric_sensors = [p for p in points if p.kind == "Number" and "sensor" in p.marker_tags]

        if not numeric_sensors:
            pytest.skip("No numeric sensor points available for history write test")

        point = numeric_sensors[0]
        assert point.id is not None

        # Create history samples for the last hour
        now = datetime.now(UTC)
        samples = [
            HistorySample(
                point_id=point.id,
                timestamp=now - timedelta(minutes=60 - i),
                value=70.0 + i * 0.5,  # Temperature trend: 70°F to 80°F
            )
            for i in range(12)  # One sample every 5 minutes
        ]

        # Write samples
        result = await client.write_history(samples)

        assert result.success is True
        assert result.samples_written == 12
        print(f"\n✓ Wrote {result.samples_written} history samples to {point.dis}")


@pytest.mark.asyncio
async def test_integration_write_history_chunked() -> None:
    """Test chunked history write for large batches."""
    async with SkysparkClient(
        base_url=TEST_URL,
        project=TEST_PROJECT,
        username=TEST_USER,
        password=TEST_PASS,
    ) as client:
        # Get numeric sensor points
        points = await client.read_points_as_models()
        numeric_sensors = [p for p in points if p.kind == "Number" and "sensor" in p.marker_tags]

        if len(numeric_sensors) < 2:
            pytest.skip("Need at least 2 numeric sensor points for chunked write test")

        # Create large batch across multiple points
        now = datetime.now(UTC)
        samples = []

        for point in numeric_sensors[:2]:  # Use first 2 points
            assert point.id is not None
            for i in range(100):  # 100 samples per point
                samples.append(
                    HistorySample(
                        point_id=point.id,
                        timestamp=now - timedelta(minutes=100 - i),
                        value=50.0 + (i % 50),
                    )
                )

        # Write with chunking (chunk_size=50, max_concurrent=2)
        results = await client.write_history_chunked(samples, chunk_size=50, max_concurrent=2)

        assert len(results) == 4  # 200 samples / 50 per chunk = 4 chunks
        assert all(r.success for r in results)
        total_written = sum(r.samples_written for r in results)
        assert total_written == 200

        print(f"\n✓ Wrote {total_written} samples in {len(results)} chunks")


@pytest.mark.asyncio
async def test_integration_error_handling() -> None:
    """Test error handling for invalid operations."""
    async with SkysparkClient(
        base_url=TEST_URL,
        project=TEST_PROJECT,
        username=TEST_USER,
        password=TEST_PASS,
    ) as client:
        # Try to read non-existent entity
        result = await client.read_by_id("invalid_id_12345")
        assert result is None
        print("\n✓ Handled non-existent entity correctly")

        # Try to delete non-existent entity (should raise error)
        with pytest.raises((EntityNotFoundError, CommitError)):
            await client.delete_entity("invalid_id_12345")
        print("✓ Raised appropriate error for invalid delete")
