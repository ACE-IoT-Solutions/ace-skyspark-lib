"""Integration tests for hisWrite against SkySpark.

Usage:
    python test_hiswrite.py single          # sanity check: normal, inf, nan on one point
    python test_hiswrite.py all             # write one sample to every hisPoint
    python test_hiswrite.py inf             # test inf/nan handling on one point
    python test_hiswrite.py point <id>      # write one sample to a specific point ID

Credentials via .env or environment:
    SKYSPARK_URL, SKYSPARK_PROJECT, SKYSPARK_USERNAME, SKYSPARK_PASSWORD
    TEST_POINT_ID   (default point for 'single' and 'inf' tests)
    TEST_VALUE      (numeric value to write, default 0.0)
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from ace_skyspark_lib import SkysparkClient
from ace_skyspark_lib.models.history import HistorySample

BASE_URL       = os.getenv("SKYSPARK_URL", "http://100.66.218.17:8484/api")
PROJECT        = os.getenv("SKYSPARK_PROJECT", "atw_concourse_expansion")
USERNAME       = os.getenv("SKYSPARK_USERNAME", "mahoneyc")
PASSWORD       = os.getenv("SKYSPARK_PASSWORD", "")
TEST_POINT_ID  = os.getenv("TEST_POINT_ID", "31bf1b6d-fc5e99af")
TEST_VALUE     = float(os.getenv("TEST_VALUE", "0.0"))


def _point_id(point: dict) -> str | None:
    ref = point.get("id") or point.get("_id")
    if not ref:
        return None
    # Haystack JSON encodes refs as {"_kind": "ref", "val": "p:proj:r:uuid", "dis": "..."}
    if isinstance(ref, dict):
        ref = ref.get("val", "")
    ref = str(ref).lstrip("@").split(" ")[0]
    if ":r:" in ref:
        ref = ref.split(":r:", 1)[1]
    return ref or None


async def test_single(client: SkysparkClient, point_id: str) -> None:
    """Write a normal value, then inf, then nan — verifies basic path and filtering."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    print(f"\n[normal] point={point_id} value={TEST_VALUE}")
    r = await client.write_history([HistorySample(point_id=point_id, timestamp=now, value=TEST_VALUE)])
    print(f"  success={r.success}  written={r.samples_written}  error={r.error}")

    print(f"\n[inf]    point={point_id}")
    r = await client.write_history([HistorySample(point_id=point_id, timestamp=now, value=float("inf"))])
    print(f"  success={r.success}  written={r.samples_written}  error={r.error}")

    print(f"\n[nan]    point={point_id}")
    r = await client.write_history([HistorySample(point_id=point_id, timestamp=now, value=float("nan"))])
    print(f"  success={r.success}  written={r.samples_written}  error={r.error}")


async def test_inf(client: SkysparkClient, point_id: str) -> None:
    """Only test inf/nan filtering."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    for label, val in [("inf", float("inf")), ("-inf", float("-inf")), ("nan", float("nan"))]:
        print(f"\n[{label}] point={point_id}")
        r = await client.write_history([HistorySample(point_id=point_id, timestamp=now, value=val)])
        print(f"  success={r.success}  written={r.samples_written}  error={r.error}")


async def test_point(client: SkysparkClient, point_id: str) -> None:
    """Write one sample to a specific point and print the full result."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    print(f"\nWriting {TEST_VALUE} → {point_id} at {now.isoformat()}")
    r = await client.write_history([HistorySample(point_id=point_id, timestamp=now, value=TEST_VALUE)])
    print(f"  success={r.success}  written={r.samples_written}  error={r.error}")


async def test_all(client: SkysparkClient) -> None:
    """Write one sample to every hisPoint and report successes/failures."""
    print("Fetching all historized points...")
    points = await client.read_points(his_only=True)
    print(f"Found {len(points)} hisPoints\n")

    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    succeeded, failed, skipped = [], [], []

    try:
        for i, point in enumerate(points):
            pid = _point_id(point)
            _dis = point.get("dis", point.get("navName", "?"))
            dis = _dis.get("val", str(_dis)) if isinstance(_dis, dict) else str(_dis)
            _kind = point.get("kind", "?")
            kind = _kind.get("val", str(_kind)) if isinstance(_kind, dict) else str(_kind)

            if not pid:
                skipped.append((dis, "could not extract point ID"))
                continue

            r = await client.write_history([HistorySample(point_id=pid, timestamp=now, value=TEST_VALUE)])

            if r.success and r.samples_written > 0 and not r.error:
                status = "OK  "
                succeeded.append((dis, pid))
            elif r.error:
                status = "FAIL"
                failed.append((dis, pid, r.error))
            else:
                status = "SKIP"
                skipped.append((dis, "inf/nan filtered"))

            print(f"[{i+1:4d}/{len(points)}] {status}  {dis:<50} {pid}  kind={kind}")
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n\n[interrupted]")

    print(f"\n{'='*70}")
    print(f"Results: {len(succeeded)} OK, {len(failed)} failed, {len(skipped)} skipped")

    if failed:
        print(f"\nFailed ({len(failed)}):")
        for dis, pid, err in failed:
            print(f"  {dis} ({pid})")
            print(f"    {err[:200]}")

    if skipped:
        print(f"\nSkipped ({len(skipped)}):")
        for dis, reason in skipped:
            print(f"  {dis}: {reason}")


async def main(args: argparse.Namespace) -> None:
    if not PASSWORD:
        print("ERROR: set SKYSPARK_PASSWORD in env or .env file")
        sys.exit(1)

    print(f"Connecting to {BASE_URL}/{PROJECT} as {USERNAME}")

    async with SkysparkClient(base_url=BASE_URL, project=PROJECT, username=USERNAME, password=PASSWORD) as client:
        if args.test == "single":
            await test_single(client, TEST_POINT_ID)
        elif args.test == "inf":
            await test_inf(client, TEST_POINT_ID)
        elif args.test == "all":
            await test_all(client)
        elif args.test == "point":
            await test_point(client, args.point_id)

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SkySpark hisWrite integration tests")
    sub = parser.add_subparsers(dest="test", required=True)

    sub.add_parser("single", help="normal + inf + nan on TEST_POINT_ID")
    sub.add_parser("inf",    help="inf / -inf / nan filtering on TEST_POINT_ID")
    sub.add_parser("all",    help="write one sample to every hisPoint in the project")

    p = sub.add_parser("point", help="write one sample to a specific point ID")
    p.add_argument("point_id", help="bare UUID, e.g. 31bf1b6d-fc5e99af")

    asyncio.run(main(parser.parse_args()))
