"""Check for duplicate entities in aceTest project."""

import asyncio
import os

from dotenv import load_dotenv

from ace_skyspark_lib import SkysparkClient

load_dotenv()

TEST_URL = os.getenv("TEST_SKYSPARK_URL")
TEST_USER = os.getenv("TEST_SKYSPARK_USER")
TEST_PASS = os.getenv("TEST_SKYSPARK_PASS")


async def check_entities() -> None:
    """Check what entities exist in aceTest."""
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
        # Find all sites with our test refName
        print("\n" + "=" * 60)
        print("Checking for RT Test entities in aceTest project")
        print("=" * 60)

        # Check sites
        sites = await client.read("site")
        rt_sites = [s for s in sites if "RT Test" in s.get("dis", "")]
        print(f"\n📍 Found {len(rt_sites)} sites with 'RT Test' in name:")
        for site in rt_sites:
            site_id = site["id"]["val"] if isinstance(site["id"], dict) else site["id"]
            print(f"   - {site.get('dis')} ({site_id})")
            print(f"     refName: {site.get('refName', 'N/A')}")
            print(f"     mod: {site.get('mod', 'N/A')}")

        # Check equipment
        equips = await client.read("equip")
        rt_equips = [e for e in equips if "RT Test" in e.get("dis", "")]
        print(f"\n🔧 Found {len(rt_equips)} equipment with 'RT Test' in name:")
        for equip in rt_equips:
            equip_id = equip["id"]["val"] if isinstance(equip["id"], dict) else equip["id"]
            print(f"   - {equip.get('dis')} ({equip_id})")
            print(f"     refName: {equip.get('refName', 'N/A')}")
            site_ref = equip.get("siteRef", {})
            if isinstance(site_ref, dict):
                print(f"     siteRef: {site_ref.get('val', 'N/A')}")

        # Check points
        points = await client.read("point")
        rt_points = [p for p in points if "RT Test" in p.get("dis", "")]
        print(f"\n📊 Found {len(rt_points)} points with 'RT Test' in name:")
        for point in rt_points:
            point_id = point["id"]["val"] if isinstance(point["id"], dict) else point["id"]
            print(f"   - {point.get('dis')} ({point_id})")
            print(f"     refName: {point.get('refName', 'N/A')}")
            site_ref = point.get("siteRef", {})
            equip_ref = point.get("equipRef", {})
            if isinstance(site_ref, dict):
                print(f"     siteRef: {site_ref.get('val', 'N/A')}")
            if isinstance(equip_ref, dict):
                print(f"     equipRef: {equip_ref.get('val', 'N/A')}")

        # Check for duplicates by refName
        print("\n" + "=" * 60)
        print("Duplicate Analysis by refName")
        print("=" * 60)

        # Group by refName
        site_by_refname = {}
        for site in rt_sites:
            refname = site.get("refName", "N/A")
            if refname not in site_by_refname:
                site_by_refname[refname] = []
            site_by_refname[refname].append(site)

        equip_by_refname = {}
        for equip in rt_equips:
            refname = equip.get("refName", "N/A")
            if refname not in equip_by_refname:
                equip_by_refname[refname] = []
            equip_by_refname[refname].append(equip)

        point_by_refname = {}
        for point in rt_points:
            refname = point.get("refName", "N/A")
            if refname not in point_by_refname:
                point_by_refname[refname] = []
            point_by_refname[refname].append(point)

        # Report duplicates
        print(f"\n📍 Site refName duplicates:")
        for refname, items in site_by_refname.items():
            if len(items) > 1:
                print(f"   ⚠️  '{refname}': {len(items)} duplicates")
                for item in items:
                    item_id = item["id"]["val"] if isinstance(item["id"], dict) else item["id"]
                    print(f"      - {item_id} (created: {item.get('mod', 'unknown')})")
            else:
                print(f"   ✓ '{refname}': unique")

        print(f"\n🔧 Equipment refName duplicates:")
        for refname, items in equip_by_refname.items():
            if len(items) > 1:
                print(f"   ⚠️  '{refname}': {len(items)} duplicates")
                for item in items:
                    item_id = item["id"]["val"] if isinstance(item["id"], dict) else item["id"]
                    print(f"      - {item_id} (created: {item.get('mod', 'unknown')})")
            else:
                print(f"   ✓ '{refname}': unique")

        print(f"\n📊 Point refName duplicates:")
        for refname, items in point_by_refname.items():
            if len(items) > 1:
                print(f"   ⚠️  '{refname}': {len(items)} duplicates")
                for item in items:
                    item_id = item["id"]["val"] if isinstance(item["id"], dict) else item["id"]
                    print(f"      - {item_id} (created: {item.get('mod', 'unknown')})")
            else:
                print(f"   ✓ '{refname}': unique")

        print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(check_entities())
