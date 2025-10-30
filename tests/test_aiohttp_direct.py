"""Test aiohttp directly to isolate the issue."""

import asyncio
import os

import aiohttp
from dotenv import load_dotenv

from ace_skyspark_lib.auth.authenticator import ScramAuthenticator

load_dotenv()

TEST_URL = os.getenv("TEST_SKYSPARK_URL")
TEST_USER = os.getenv("TEST_SKYSPARK_USER")
TEST_PASS = os.getenv("TEST_SKYSPARK_PASS")


async def test_direct() -> None:
    """Test direct aiohttp call after getting token."""
    base_url = TEST_URL.rstrip("/")
    if not base_url.endswith("/api"):
        base_url = f"{base_url}/api"

    async with aiohttp.ClientSession() as session:
        # Get auth token
        authenticator = ScramAuthenticator(
            base_url=base_url,
            project="demo",
            username=TEST_USER,
            password=TEST_PASS,
            session=session,
        )
        token = await authenticator.authenticate()
        print(f"Got token: {token}")

        # Now try direct POST
        url = f"{base_url}/demo/commit"
        grid = 'ver:"3.0" commit:"add"\ndis\n"Test Site"\n'

        headers = {
            "Authorization": f"Bearer authToken={token}",
            "Content-Type": "text/zinc",
            "Accept": "application/json",
        }

        print(f"\nPOSTing to: {url}")
        print(f"Headers: {headers}")
        print(f"Grid: {grid[:50]}...")

        async with session.post(url, data=grid, headers=headers) as response:
            print(f"\nStatus: {response.status}")
            print(f"Response headers: {dict(response.headers)}")
            text = await response.text()
            print(f"Response body: {text[:500]}")


if __name__ == "__main__":
    asyncio.run(test_direct())
