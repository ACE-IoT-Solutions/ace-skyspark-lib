"""Integration test for point update operations with mod field.

This test verifies that points can be read, modified, and updated without
the mod field causing encoding errors.
"""

import asyncio
import os

import pytest
from dotenv import load_dotenv

from ace_skyspark_lib import SkysparkClient

# Load environment variables
load_dotenv()

TEST_URL = os.getenv("TEST_SKYSPARK_URL")
TEST_USER = os.getenv("TEST_SKYSPARK_USER")
TEST_PASS = os.getenv("TEST_SKYSPARK_PASS")


@pytest.mark.asyncio
async def test_point_update_with_mod_field():
    """Test that points with mod field can be updated successfully."""
    if not all([TEST_URL, TEST_USER, TEST_PASS]):
        pytest.skip("Test credentials not configured in .env")

    async with SkysparkClient(
        base_url=f"{TEST_URL}api",
        project="aceTest",
        username=TEST_USER,
        password=TEST_PASS,
        timeout=30.0,
    ) as client:
        # Read points as models (this will include mod field from SkySpark)
        points = await client.read_points_as_models()

        if not points:
            pytest.skip("No points found in aceTest project")

        # Take first point
        point = points[0]
        print(f"\n✓ Read point: {point.dis} (ID: {point.id})")
        print(f"  refName: {point.ref_name}")

        # Modify the point - add a marker tag to verify update works
        # Note: Tag removal by omission is not supported in Haystack/SkySpark.
        # Omitted tags are left unchanged, not removed.
        test_tag = "test_update_tag"

        if test_tag not in point.marker_tags:
            point.marker_tags.append(test_tag)
            print(f"  Adding '{test_tag}' tag")

            # Update the point (this should work even though mod was in the original data)
            try:
                result = await client.update_points([point])
                print(f"✓ Successfully updated point")
                print(f"  Response: {result}")
            except Exception as e:
                pytest.fail(f"Failed to update point: {e}")

            # Verify the update by reading back
            updated_points = await client.read_points_as_models(equip_ref=point.equip_ref)
            updated_point = next((p for p in updated_points if p.id == point.id), None)

            if updated_point:
                assert test_tag in updated_point.marker_tags, f"Tag {test_tag} not found after update"
                print(f"✓ Verified update - tag was added")
        else:
            # Tag already present - just do a no-op update to verify mod field handling
            print(f"  Tag '{test_tag}' already present - testing no-op update")
            try:
                result = await client.update_points([point])
                print(f"✓ Successfully updated point (no-op)")
            except Exception as e:
                pytest.fail(f"Failed to update point: {e}")


async def main():
    """Run the test manually."""
    await test_point_update_with_mod_field()


if __name__ == "__main__":
    asyncio.run(main())
