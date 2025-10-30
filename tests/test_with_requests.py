"""Test with requests library to see if it works."""

import asyncio
import os

import aiohttp
import requests
from dotenv import load_dotenv

from ace_skyspark_lib.auth.authenticator import ScramAuthenticator

load_dotenv()

TEST_URL = os.getenv("TEST_SKYSPARK_URL")
TEST_USER = os.getenv("TEST_SKYSPARK_USER")
TEST_PASS = os.getenv("TEST_SKYSPARK_PASS")


async def test_with_requests_lib() -> None:
    """Get token with async, then test with requests."""
    base_url = TEST_URL.rstrip("/")
    if not base_url.endswith("/api"):
        base_url = f"{base_url}/api"

    # Get token async
    async with aiohttp.ClientSession() as session:
        authenticator = ScramAuthenticator(
            base_url=base_url,
            project="demo",
            username=TEST_USER,
            password=TEST_PASS,
            session=session,
        )
        token = await authenticator.authenticate()

    print(f"Got token: {token}")

    # Now use requests (sync)
    url = f"{base_url}/demo/commit"
    grid = 'ver:"3.0" commit:"add"\ndis\n"Test Site Sync"\n'

    headers = {
        "Authorization": f"Bearer authToken={token}",
        "Content-Type": "text/zinc",
        "Accept": "application/json",
    }

    print(f"\nUsing requests library to POST to: {url}")
    response = requests.post(url, data=grid, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")


if __name__ == "__main__":
    asyncio.run(test_with_requests_lib())
