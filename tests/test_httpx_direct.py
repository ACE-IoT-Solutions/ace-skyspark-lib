"""Test httpx directly to see if it works."""

import asyncio
import os

import httpx
from dotenv import load_dotenv

from ace_skyspark_lib.auth.authenticator import ScramAuthenticator

load_dotenv()

TEST_URL = os.getenv("TEST_SKYSPARK_URL")
TEST_USER = os.getenv("TEST_SKYSPARK_USER")
TEST_PASS = os.getenv("TEST_SKYSPARK_PASS")


async def test_direct() -> None:
    """Test direct httpx call after getting token."""
    base_url = TEST_URL.rstrip("/")
    if not base_url.endswith("/api"):
        base_url = f"{base_url}/api"

    # Get auth token with one client
    async with httpx.AsyncClient() as auth_session:
        authenticator = ScramAuthenticator(
            base_url=base_url,
            project="demo",
            username=TEST_USER,
            password=TEST_PASS,
            session=auth_session,
        )
        token = await authenticator.authenticate()
        print(f"Got token: {token}")

    # Make API call with a FRESH client
    async with httpx.AsyncClient() as api_session:
        url = f"{base_url}/demo/commit"
        grid = 'ver:"3.0" commit:"add"\ndis\n"Test Site HTTPX Fresh"\n'

        headers = {
            "Authorization": f"Bearer authToken={token}",
            "Content-Type": "text/zinc",
            "Accept": "application/json",
        }

        print(f"\nPOSTing to: {url}")
        print(f"Headers: {headers}")
        print(f"Grid: {grid[:50]}...")

        response = await api_session.post(url, content=grid, headers=headers)
        print(f"\nStatus: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        text = response.text
        print(f"Response body: {text[:500]}")


if __name__ == "__main__":
    asyncio.run(test_direct())
