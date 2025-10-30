"""SCRAM-SHA-256 authentication for SkySpark."""

from base64 import urlsafe_b64decode, urlsafe_b64encode

import httpx
import structlog
from scramp import ScramClient

from ace_skyspark_lib.exceptions import AuthenticationError

logger = structlog.get_logger()


class ScramAuthenticator:
    """SCRAM-SHA-256 authentication handler."""

    def __init__(
        self,
        base_url: str,
        project: str,
        username: str,
        password: str,
        session: httpx.AsyncClient,
    ) -> None:
        """Initialize authenticator.

        Args:
            base_url: Base URL for SkySpark server
            project: Project name
            username: Username for authentication
            password: Password for authentication
            session: Active httpx AsyncClient
        """
        self.base_url = base_url.rstrip("/")
        self.project = project
        self.username = username
        self.password = password
        self.session = session

    async def authenticate(self) -> str:
        """Perform full SCRAM handshake.

        Returns:
            Authentication token

        Raises:
            AuthenticationError: If authentication fails
        """
        logger.info("scram_auth_starting", username=self.username)

        try:
            # Step 1: HELLO
            handshake_token = await self._hello()
            logger.debug("scram_hello_complete", handshake_token=handshake_token[:20])

            # Step 2: CLIENT-FIRST
            handshake_token, server_first = await self._client_first(handshake_token)
            logger.debug("scram_client_first_complete")

            # Step 3: CLIENT-FINAL
            auth_token = await self._client_final(handshake_token, server_first)
            logger.info("scram_auth_complete")

            return auth_token

        except Exception as e:
            logger.error("scram_auth_failed", error=str(e))
            msg = f"SCRAM authentication failed: {e}"
            raise AuthenticationError(msg) from e

    async def _hello(self) -> str:
        """SCRAM step 1: send HELLO, get handshake token.

        Returns:
            Handshake token

        Raises:
            AuthenticationError: If HELLO fails
        """
        b64_username = urlsafe_b64encode(self.username.encode("utf-8")).decode("utf-8").rstrip("=")

        url = f"{self.base_url}/{self.project}/about"
        headers = {"Authorization": f"HELLO username={b64_username}"}

        response = await self.session.get(url, headers=headers)
        # SCRAM HELLO should return 401 with www-authenticate header
        if response.status_code not in (200, 401):
            msg = f"HELLO failed with status {response.status_code}"
            raise AuthenticationError(msg)

        www_auth = response.headers.get("www-authenticate")
        if not www_auth:
            msg = "No www-authenticate header in HELLO response"
            raise AuthenticationError(msg)

        # Extract handshakeToken
        try:
            # Remove "scram " prefix if present
            auth_str = www_auth
            if auth_str.lower().startswith("scram "):
                auth_str = auth_str[6:]

            parts = dict(part.strip().split("=", 1) for part in auth_str.split(","))
            handshake_token = parts.get("handshakeToken", "")
            if not handshake_token:
                msg = f"No handshakeToken in HELLO response: {www_auth}"
                raise AuthenticationError(msg)

            logger.debug("scram_hello_complete", handshake_token=handshake_token)
            return handshake_token
        except (IndexError, ValueError) as e:
            msg = f"Failed to parse handshakeToken from: {www_auth}"
            raise AuthenticationError(msg) from e

    async def _client_first(self, handshake_token: str) -> tuple[str, str]:
        """SCRAM step 2: send client-first message.

        Args:
            handshake_token: Token from HELLO response

        Returns:
            Tuple of (new_handshake_token, server_first_message)

        Raises:
            AuthenticationError: If client-first fails
        """
        scram_client = ScramClient(["SCRAM-SHA-256"], self.username, self.password)
        client_first = scram_client.get_client_first()

        b64_client_first = (
            urlsafe_b64encode(client_first.encode("utf-8")).decode("utf-8").rstrip("=")
        )

        url = f"{self.base_url}/{self.project}/about"
        auth_header = (
            f"SCRAM handshakeToken={handshake_token}, hash=SHA-256, data={b64_client_first}"
        )
        headers = {"Authorization": auth_header}

        response = await self.session.get(url, headers=headers)
        if response.status_code != 401:  # 401 is expected for SCRAM challenge
            msg = f"CLIENT-FIRST failed with status {response.status_code}"
            raise AuthenticationError(msg)

        www_auth = response.headers.get("www-authenticate")
        if not www_auth:
            msg = "No www-authenticate header in CLIENT-FIRST response"
            raise AuthenticationError(msg)

        logger.debug("client_first_response", www_auth=www_auth)

        # Extract new handshakeToken and server data
        try:
            # Remove "scram " prefix if present
            auth_str = www_auth
            if auth_str.lower().startswith("scram "):
                auth_str = auth_str[6:]

            parts = dict(part.strip().split("=", 1) for part in auth_str.split(","))
            new_handshake_token = parts.get("handshakeToken", "")
            b64_server_first = parts.get("data", "")

            logger.debug(
                "client_first_parsed",
                handshake_token=new_handshake_token,
                data_len=len(b64_server_first),
            )

            # Decode server-first message
            # Add padding if needed
            padding = "=" * (4 - len(b64_server_first) % 4)
            server_first = urlsafe_b64decode(b64_server_first + padding).decode("utf-8")

            logger.debug("server_first_decoded", server_first=server_first)

            # Store for client-final step
            self._scram_client = scram_client
            scram_client.set_server_first(server_first)

            return new_handshake_token, server_first

        except (KeyError, ValueError) as e:
            msg = f"Failed to parse CLIENT-FIRST response: {www_auth}"
            raise AuthenticationError(msg) from e

    async def _client_final(self, handshake_token: str, _server_first: str) -> str:
        """SCRAM step 3: send client-final, get auth token.

        Args:
            handshake_token: Token from CLIENT-FIRST response
            _server_first: Server-first message (unused but kept for signature)

        Returns:
            Authentication token

        Raises:
            AuthenticationError: If client-final fails
        """
        client_final = self._scram_client.get_client_final()

        b64_client_final = (
            urlsafe_b64encode(client_final.encode("utf-8")).decode("utf-8").rstrip("=")
        )

        url = f"{self.base_url}/{self.project}/about"
        auth_header = (
            f"SCRAM handshakeToken={handshake_token}, hash=SHA-256, data={b64_client_final}"
        )
        headers = {"Authorization": auth_header}

        response = await self.session.get(url, headers=headers)
        if response.status_code != 200:
            msg = f"CLIENT-FINAL failed with status {response.status_code}"
            raise AuthenticationError(msg)

        auth_info = response.headers.get("authentication-info")
        if not auth_info:
            msg = "No authentication-info header in CLIENT-FINAL response"
            raise AuthenticationError(msg)

        # Extract authToken and server verification
        try:
            parts = dict(part.split("=", 1) for part in auth_info.split(", "))
            auth_token = parts.get("authToken", "")
            b64_server_final = parts.get("data", "")

            # Verify server final
            padding = "=" * (4 - len(b64_server_final) % 4)
            server_final = urlsafe_b64decode(b64_server_final + padding).decode("utf-8")
            self._scram_client.set_server_final(server_final)

            return auth_token

        except (KeyError, ValueError) as e:
            msg = f"Failed to parse CLIENT-FINAL response: {auth_info}"
            raise AuthenticationError(msg) from e
