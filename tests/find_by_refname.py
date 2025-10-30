"""Test finding entities by refName."""

import asyncio
import os

from dotenv import load_dotenv

from ace_skyspark_lib import SkysparkClient

load_dotenv()

TEST_URL = os.getenv("TEST_SKYSPARK_URL")
TEST_USER = os.getenv("TEST_SKYSPARK_USER")
TEST_PASS = os.getenv("TEST_SKYSPARK_PASS")


async def test_refname_search() -> None:
    """Test different ways to search by refName."""
    base_url = TEST_URL.rstrip("/")
    if not base_url.endswith("/api"):
        base_url = f"{base_url}/api"

    async with SkysparkClient(
        base_url=base_url,
        project="aceTest",
        username=TEST_USER,
        password=TEST_PASS,
        timeout=30.0,
    ) as client:
        print("\n" + "=" * 60)
        print("Testing refName search strategies")
        print("=" * 60)

        # Get all sites first
        print("\n1. Getting all sites...")
        all_sites = await client.read("site")
        print(f"   Found {len(all_sites)} sites")

        # Show refNames
        ace_sites = [s for s in all_sites if "ACE Test" in s.get("dis", "")]
        print(f"\n2. ACE Test sites:")
        for site in ace_sites:
            site_id = site["id"]["val"] if isinstance(site["id"], dict) else site["id"]
            print(f"   - {site.get('dis')}")
            print(f"     ID: {site_id}")
            print(f"     refName: {site.get('refName', 'N/A')}")

        # Test: Can we filter by refName programmatically?
        print(f"\n3. Filtering in Python (after fetching all):")
        target_refname = "ace_test_site_001"
        matching = [s for s in all_sites if s.get("refName") == target_refname]
        print(f"   Sites with refName='{target_refname}': {len(matching)}")
        if matching:
            for site in matching:
                site_id = site["id"]["val"] if isinstance(site["id"], dict) else site["id"]
                print(f"   - {site_id}: {site.get('dis')}")

        print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(test_refname_search())
