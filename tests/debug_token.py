"""Debug token format."""

import asyncio
import os

from dotenv import load_dotenv

from ace_skyspark_lib import SkysparkClient

load_dotenv()

TEST_URL = os.getenv("TEST_SKYSPARK_URL")
TEST_USER = os.getenv("TEST_SKYSPARK_USER")
TEST_PASS = os.getenv("TEST_SKYSPARK_PASS")


async def debug_token() -> None:
    """Check what token we get from authentication."""
    base_url = TEST_URL.rstrip("/")
    if not base_url.endswith("/api"):
        base_url = f"{base_url}/api"

    async with SkysparkClient(
        base_url=base_url,
        project="demo",
        username=TEST_USER,
        password=TEST_PASS,
    ) as client:
        # Access internal token manager to see token
        token = client._token_manager.get_cached_token()
        print(f"\nToken received from authentication:")
        print(f"Length: {len(token)}")
        print(f"Token: {token}")
        print(f"\nFirst 50 chars: {token[:50]}")
        print(f"Last 50 chars: {token[-50:]}")


if __name__ == "__main__":
    asyncio.run(debug_token())
