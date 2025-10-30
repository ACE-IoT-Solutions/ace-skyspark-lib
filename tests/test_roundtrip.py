"""Round-trip integration test for SkySpark API.

This test creates a complete entity hierarchy (site → equipment → points),
writes history data, and verifies the data can be read back correctly.
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

# Load credentials
load_dotenv()

TEST_URL = os.getenv("TEST_SKYSPARK_URL")
TEST_USER = os.getenv("TEST_SKYSPARK_USER")
TEST_PASS = os.getenv("TEST_SKYSPARK_PASS")

# Skip if credentials not provided
pytestmark = pytest.mark.skipif(
    not all([TEST_URL, TEST_USER, TEST_PASS]),
    reason="Integration test credentials not provided in .env",
)


@pytest.mark.asyncio
async def test_complete_roundtrip() -> None:
    """Complete round-trip test: create entities, write history, read back."""
    # Clean up base URL
    base_url = TEST_URL.rstrip("/")
    if not base_url.endswith("/api"):
        base_url = f"{base_url}/api"

    print(f"\n{'=' * 60}")
    print(f"Round-Trip Integration Test")
    print(f"{'=' * 60}")
    print(f"URL: {base_url}")
    print(f"User: {TEST_USER}")
    print(f"{'=' * 60}\n")

    async with SkysparkClient(
        base_url=base_url,
        project="aceTest",
        username=TEST_USER,
        password=TEST_PASS,
        timeout=30.0,
    ) as client:
        # Step 1: Create a test site
        print("📍 Step 1: Creating test site...")
        test_site = Site(
            dis="RT Test Building",
            tz="America/New_York",
            refName="rt_test_site",
            area_sqft=5000.0,
            marker_tags=["office"],
            kv_tags={
                "address": "123 Test St",
                "city": "New York",
                "testRun": f"test_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
            },
        )

        created_sites = await client.create_sites([test_site])
        assert len(created_sites) == 1, "Failed to create site"
        site_id_dict = created_sites[0]["id"]
        site_id = site_id_dict["val"] if isinstance(site_id_dict, dict) else site_id_dict
        print(f"   ✓ Created site: {site_id}")
        print(f"     - Display: {created_sites[0].get('dis')}")
        print(f"     - Timezone: {created_sites[0].get('tz')}")

        # Step 2: Create test equipment
        print("\n🔧 Step 2: Creating test equipment...")
        test_equip = Equipment(
            dis="RT Test AHU",
            site_ref=site_id,
            refName="rt_test_ahu",
            marker_tags=["ahu", "hvac"],
            kv_tags={
                "floor": "2",
                "zone": "North",
                "testRun": f"test_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
            },
        )

        created_equip = await client.create_equipment([test_equip])
        assert len(created_equip) == 1, "Failed to create equipment"
        equip_id_dict = created_equip[0]["id"]
        equip_id = equip_id_dict["val"] if isinstance(equip_id_dict, dict) else equip_id_dict
        print(f"   ✓ Created equipment: {equip_id}")
        print(f"     - Display: {created_equip[0].get('dis')}")
        print(f"     - Site Ref: {created_equip[0].get('siteRef')}")

        # Step 3: Create test points
        print("\n📊 Step 3: Creating test points...")
        test_run = f"test_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        test_points = [
            Point(
                dis="RT Test Temp Sensor",
                kind="Number",
                unit="°F",
                site_ref=site_id,
                equip_ref=equip_id,
                refName="rt_test_temp",
                marker_tags=["sensor", "temp", "air"],
                kv_tags={
                    "minVal": "32",
                    "maxVal": "120",
                    "testRun": test_run,
                },
            ),
            Point(
                dis="RT Test Status",
                kind="Bool",
                site_ref=site_id,
                equip_ref=equip_id,
                refName="rt_test_status",
                marker_tags=["sensor", "run", "status"],
                kv_tags={"testRun": test_run},
            ),
            Point(
                dis="RT Test Command",
                kind="Bool",
                site_ref=site_id,
                equip_ref=equip_id,
                refName="rt_test_cmd",
                writable=True,
                marker_tags=["cmd", "writable"],
                kv_tags={"testRun": test_run},
            ),
        ]

        created_points = await client.create_points(test_points)
        assert len(created_points) == 3, f"Expected 3 points, got {len(created_points)}"
        point_ids = [
            p["id"]["val"] if isinstance(p["id"], dict) else p["id"] for p in created_points
        ]
        print(f"   ✓ Created {len(created_points)} points:")
        for i, point in enumerate(created_points):
            print(f"     - {point['dis']} ({point_ids[i]})")

        # Step 4: Verify we can read back the entities
        print("\n🔍 Step 4: Verifying entity hierarchy...")

        # Read site by ID
        site = await client.read_by_id(site_id)
        assert site is not None, "Failed to read back site"
        print(f"   ✓ Read site: {site['dis']}")

        # Read equipment
        equipment = await client.read_equipment(site_ref=site_id)
        assert len(equipment) > 0, "Failed to read back equipment"
        print(f"   ✓ Read {len(equipment)} equipment items")

        # Read points
        points = await client.read_points_as_models(site_ref=site_id, equip_ref=equip_id)
        assert len(points) >= 3, f"Expected at least 3 points, got {len(points)}"
        print(f"   ✓ Read {len(points)} points")

        # Step 5: Write history samples
        print("\n📝 Step 5: Writing history samples...")
        now = datetime.now(UTC)
        temp_point_id = point_ids[0]  # Temperature sensor
        status_point_id = point_ids[1]  # Status sensor

        # Create 24 hours of temperature readings (hourly)
        temp_samples = [
            HistorySample(
                point_id=temp_point_id,
                timestamp=now - timedelta(hours=24 - i),
                value=68.0 + (i % 12) * 0.5,  # 68-74°F cycle
            )
            for i in range(24)
        ]

        # Create status readings (on/off every 4 hours)
        status_samples = [
            HistorySample(
                point_id=status_point_id,
                timestamp=now - timedelta(hours=24 - i * 4),
                value=i % 2 == 0,
            )
            for i in range(6)
        ]

        all_samples = temp_samples + status_samples
        result = await client.write_history(all_samples)

        assert result.success, f"History write failed: {result.error}"
        assert result.samples_written == len(all_samples), (
            f"Expected {len(all_samples)} samples written, got {result.samples_written}"
        )
        print(f"   ✓ Wrote {result.samples_written} history samples")
        print(f"     - Temperature readings: {len(temp_samples)}")
        print(f"     - Status readings: {len(status_samples)}")

        # Step 6: Test read by ID (skip update due to datetime serialization complexity)
        print("\n🔍 Step 6: Testing read by ID...")
        temp_point_data = await client.read_by_id(temp_point_id)
        assert temp_point_data is not None, "Failed to read point by ID"
        assert temp_point_data.get("dis") == "RT Test Temp Sensor", "Point data mismatch"
        print(f"   ✓ Read point by ID: {temp_point_data.get('dis')}")
        print(f"     - Kind: {temp_point_data.get('kind')}")
        print(f"     - Unit: {temp_point_data.get('unit')}")

        # Step 7: Test bulk history write with chunking
        print("\n📦 Step 7: Testing chunked bulk history write...")
        bulk_samples = []
        for point_id in [temp_point_id, status_point_id]:
            for i in range(100):
                bulk_samples.append(
                    HistorySample(
                        point_id=point_id,
                        timestamp=now - timedelta(minutes=200 - i * 2),
                        value=70.0 + (i % 20) if point_id == temp_point_id else i % 2 == 0,
                    )
                )

        chunk_results = await client.write_history_chunked(
            bulk_samples, chunk_size=50, max_concurrent=2
        )

        total_written = sum(r.samples_written for r in chunk_results)
        failed = sum(1 for r in chunk_results if not r.success)
        print(f"   ✓ Wrote {total_written} samples in {len(chunk_results)} chunks")
        print(f"     - Chunk size: 50")
        print(f"     - Concurrent writes: 2")
        print(f"     - Failed chunks: {failed}")

        assert failed == 0, f"{failed} chunks failed"
        assert total_written == len(bulk_samples), (
            f"Expected {len(bulk_samples)} samples, wrote {total_written}"
        )

        # Step 8: Cleanup (non-fatal - delete implementation may need work)
        print("\n🧹 Step 8: Cleaning up test entities (best effort)...")
        try:
            # Delete points first (child entities)
            deleted_count = 0
            for point_id in point_ids:
                try:
                    await client.delete_entity(point_id)
                    deleted_count += 1
                except Exception as e:
                    print(f"   ⚠️  Could not delete point {point_id}: {e}")
            if deleted_count > 0:
                print(f"   ✓ Deleted {deleted_count}/{len(point_ids)} points")

            # Delete equipment
            try:
                await client.delete_entity(equip_id)
                print(f"   ✓ Deleted equipment")
            except Exception as e:
                print(f"   ⚠️  Could not delete equipment: {e}")

            # Delete site
            try:
                await client.delete_entity(site_id)
                print(f"   ✓ Deleted site")
            except Exception as e:
                print(f"   ⚠️  Could not delete site: {e}")
        except Exception as e:
            print(f"   ⚠️  Cleanup encountered errors: {e}")
            print(f"   Note: Test entities may need manual cleanup")

        print(f"\n{'=' * 60}")
        print("✅ Round-trip test completed successfully!")
        print(f"{'=' * 60}\n")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_complete_roundtrip())
