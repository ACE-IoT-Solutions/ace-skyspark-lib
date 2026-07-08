"""Test real ACE IoT → SkySpark sync using ace-skyspark-lib.

Fetches real samples from the ACE IoT API and writes them to SkySpark,
exactly as the Prefect flow does — without needing to publish a new
library version or inject fake data.

The point mapping is built by reading hisPoints directly from SkySpark
and matching on the ace_topic tag, so it is always current and does not
depend on the cached entity refs stored in ACE point KV tags.

Usage:
    python test_sync.py [--lookback N] [--dry-run] [--site SITE]

Credentials via .env or environment:
    SKYSPARK_URL        SkySpark API base URL
    SKYSPARK_PROJECT    SkySpark project name
    SKYSPARK_USERNAME   SkySpark username
    SKYSPARK_PASSWORD   SkySpark password
    ACE_API_URL         ACE IoT API base (default: https://flightdeck.aceiot.cloud/api)
    ACE_API_KEY         ACE IoT API key
    ACE_SITE_SLUG       Comma-separated ACE site names
    LOOKBACK_MINUTES    Minutes of data to fetch (default: 5)
"""

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from aceiot_models.api import APIClient
from ace_skyspark_lib import SkysparkClient
from ace_skyspark_lib.models.history import HistorySample

SKYSPARK_URL     = os.getenv("SKYSPARK_URL",     "http://100.66.218.17:8484/api")
SKYSPARK_PROJECT = os.getenv("SKYSPARK_PROJECT", "atw_concourse_expansion")
SKYSPARK_USER    = os.getenv("SKYSPARK_USERNAME", "mahoneyc")
SKYSPARK_PASS    = os.getenv("SKYSPARK_PASSWORD", "")
ACE_API_URL      = os.getenv("ACE_API_URL",      "https://flightdeck.aceiot.cloud/api")
ACE_API_KEY      = os.getenv("ACE_API_KEY",      "")
ACE_SITE_NAMES   = [s.strip() for s in os.getenv("ACE_SITE_SLUG", "mead_hunt_atw_phone_room").split(",") if s.strip()]
LOOKBACK_MINUTES = int(os.getenv("LOOKBACK_MINUTES", "5"))
CHUNK_SIZE       = int(os.getenv("CHUNK_SIZE", "500"))


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _normalize_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _coerce_value(value, kind: str = "") -> float | bool | str:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        coerced: float | bool | str = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if text.lower() in ("true", "false"):
            coerced = text.lower() == "true"
        else:
            try:
                coerced = float(text)
            except ValueError:
                coerced = value
    else:
        coerced = value
    # Bool-kind SkySpark points reject Number values — coerce 0/1 floats to bool
    if kind == "Bool" and isinstance(coerced, float):
        coerced = coerced != 0.0
    return coerced


def _tag_str(value) -> str:
    if isinstance(value, dict):
        return str(value.get("val", ""))
    text = str(value) if value is not None else ""
    # Strip Haystack Zinc string type prefix ("s:foo" → "foo")
    return text[2:] if text.startswith("s:") else text


def _point_id(point: dict) -> str | None:
    ref = point.get("id") or point.get("_id")
    if not ref:
        return None
    if isinstance(ref, dict):
        ref = ref.get("val", "")
    ref = str(ref).lstrip("@").split(" ")[0]
    if ":r:" in ref:
        ref = ref.split(":r:", 1)[1]
    return ref or None


async def _build_skyspark_mapping(sky: SkysparkClient) -> dict[str, dict]:
    """Return {ace_topic: {pid, kind}} by reading hisPoints from SkySpark.

    Uses the ace_topic tag written by the Prefect flow onto each SkySpark point.
    Includes the point kind so Bool-kind points get correct value coercion.
    Always current — no dependency on entity refs cached in ACE KV tags.
    """
    print(f"Querying SkySpark {SKYSPARK_PROJECT} for hisPoints...")
    points = await sky.read_points(his_only=True)
    print(f"  Got {len(points)} hisPoints")
    mapping: dict[str, dict] = {}
    for point in points:
        pid = _point_id(point)
        ace_topic = _tag_str(point.get("ace_topic"))
        if pid and ace_topic:
            mapping[ace_topic] = {"pid": pid, "kind": _tag_str(point.get("kind"))}
    print(f"  {len(mapping)} have ace_topic tags (mapped to ACE point names)\n")
    return mapping


def _fetch_timeseries(
    ace_client: APIClient, site_name: str, start: datetime, end: datetime
) -> list[dict]:
    result = ace_client.get_site_timeseries_paginated(
        site_name, _iso(start), _iso(end), page_size=10000, raw_data=False,
    )
    return result.get("point_samples", [])


async def run(site_names: list[str], lookback: int, dry_run: bool, chunk_size: int = CHUNK_SIZE) -> None:
    end   = _utc_now().replace(second=0, microsecond=0)
    start = end - timedelta(minutes=lookback)
    print(f"Window: {_iso(start)} → {_iso(end)}  ({lookback} min)")
    print(f"Sites:  {', '.join(site_names)}\n")

    ace = APIClient(base_url=ACE_API_URL, api_key=ACE_API_KEY)

    async with SkysparkClient(
        base_url=SKYSPARK_URL,
        project=SKYSPARK_PROJECT,
        username=SKYSPARK_USER,
        password=SKYSPARK_PASS,
    ) as sky:
        # Build mapping from SkySpark (always current, no KV tag dependency)
        sky_mapping = await _build_skyspark_mapping(sky)

        # Fetch timeseries from ACE IoT
        all_samples: list[dict] = []
        for site_name in site_names:
            print(f"[{site_name}] Fetching timeseries {_iso(start)} → {_iso(end)} ...")
            samples = _fetch_timeseries(ace, site_name, start, end)
            print(f"[{site_name}] Got {len(samples)} raw samples")
            all_samples.extend(samples)

        # Map ACE samples → HistorySample using SkySpark point IDs
        history: list[HistorySample] = []
        unmapped = 0
        for sample in all_samples:
            name = sample.get("name")
            ref_info = sky_mapping.get(name) if name else None
            if not ref_info:
                unmapped += 1
                continue
            ts_str = sample.get("time")
            if not ts_str:
                unmapped += 1
                continue
            history.append(HistorySample(
                point_id=ref_info["pid"],
                timestamp=_normalize_dt(ts_str),
                value=_coerce_value(sample.get("value"), ref_info.get("kind", "")),
            ))

        print(f"\nSamples to write: {len(history)}  (unmapped/skipped: {unmapped})")

        if unmapped:
            unmapped_names = [
                s.get("name") for s in all_samples
                if s.get("name") and not sky_mapping.get(s["name"])
            ]
            unique_unmapped = sorted(set(unmapped_names))
            print(f"\nFirst 5 unmapped ACE point names:")
            for n in unique_unmapped[:5]:
                print(f"  {n!r}")
            print(f"First 5 SkySpark ace_topic keys (mapping):")
            for k in list(sky_mapping)[:5]:
                print(f"  {k!r}")

        if not history:
            print("Nothing to write.")
            return

        if dry_run:
            print("\n[DRY RUN] Not writing to SkySpark.")
            print("First 5 HistorySamples:")
            for item in history[:5]:
                print(f"  point_id={item.point_id}  ts={item.timestamp.isoformat()}  value={item.value!r}")
            return

        # Chunk writes to match Prefect flow behaviour and avoid large single requests
        chunks = [history[i:i + chunk_size] for i in range(0, len(history), chunk_size)]
        total_written = 0
        total_failed = 0
        for idx, chunk in enumerate(chunks):
            result = await sky.write_history(chunk)
            written = result.samples_written
            failed = len(chunk) - written
            total_written += written
            total_failed += failed
            status = "OK" if not result.error else "WARN"
            print(f"  chunk {idx + 1}/{len(chunks)}: [{status}] written={written} failed={failed}"
                  + (f"  error={result.error[:120]}" if result.error else ""))
        print(f"\nTotal: written={total_written}  failed={total_failed}")


def main() -> None:
    if not SKYSPARK_PASS:
        print("ERROR: set SKYSPARK_PASSWORD")
        sys.exit(1)
    if not ACE_API_KEY:
        print("ERROR: set ACE_API_KEY")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Test ACE IoT → SkySpark sync")
    parser.add_argument("--lookback", type=int, default=LOOKBACK_MINUTES,
                        help="Minutes of history to fetch (default: %(default)s)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and map data but don't write to SkySpark")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE,
                        help="Samples per evalAll call (default: %(default)s)")
    parser.add_argument("--site", dest="sites", action="append",
                        help="ACE site name (repeatable; overrides ACE_SITE_SLUG env)")
    args = parser.parse_args()

    site_names = args.sites or ACE_SITE_NAMES
    asyncio.run(run(site_names, args.lookback, args.dry_run, args.chunk_size))


if __name__ == "__main__":
    main()
