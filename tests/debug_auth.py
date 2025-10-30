"""Debug authentication to find correct endpoint."""

import asyncio
import os
from base64 import urlsafe_b64encode

import aiohttp
from dotenv import load_dotenv

load_dotenv()

TEST_URL = os.getenv("TEST_SKYSPARK_URL")
TEST_USER = os.getenv("TEST_SKYSPARK_USER")


async def test_endpoints() -> None:
    """Test different endpoint configurations."""
    base_url = TEST_URL.rstrip("/")

    # Try different URL configurations
    urls_to_try = [
        (f"{base_url}/api/demo/about", "API with demo project"),
        (f"{base_url}/demo/about", "Direct with demo project"),
        (f"{base_url}/api/about", "API without project"),
        (f"{base_url}/about", "Direct without project"),
    ]

    b64_username = urlsafe_b64encode(TEST_USER.encode("utf-8")).decode("utf-8").rstrip("=")

    async with aiohttp.ClientSession() as session:
        for url, desc in urls_to_try:
            print(f"\nTrying: {desc}")
            print(f"URL: {url}")

            headers = {"Authorization": f"HELLO username={b64_username}"}

            try:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    print(f"Status: {response.status}")
                    print(f"Headers: {dict(response.headers)}")
                    if response.status == 200:
                        www_auth = response.headers.get("www-authenticate")
                        print(f"www-authenticate: {www_auth}")
                        if www_auth:
                            print("✓ AUTHENTICATION ENDPOINT FOUND!")
                    elif response.status == 401:
                        www_auth = response.headers.get("www-authenticate")
                        print(f"www-authenticate: {www_auth}")
                        text = await response.text()
                        print(f"Response body: {text[:500]}")
                    else:
                        text = await response.text()
                        print(f"Response: {text[:200]}")
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_endpoints())
