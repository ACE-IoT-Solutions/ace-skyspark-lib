"""Main SkySpark client class."""

import httpx
import structlog

from ace_skyspark_lib.auth.authenticator import ScramAuthenticator
from ace_skyspark_lib.auth.token_manager import TokenManager
from ace_skyspark_lib.http.session import SessionManager
from ace_skyspark_lib.models.entities import Equipment, Point, Site
from ace_skyspark_lib.models.history import HistorySample, HistoryWriteResult
from ace_skyspark_lib.operations.entity_ops import EntityOperations
from ace_skyspark_lib.operations.history_ops import HistoryOperations
from ace_skyspark_lib.operations.query_ops import QueryOperations

logger = structlog.get_logger()


class SkysparkClient:
    """Async client for SkySpark API operations."""

    def __init__(
        self,
        base_url: str,
        project: str,
        username: str,
        password: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        pool_size: int = 10,
    ) -> None:
        """Initialize SkySpark client.

        Args:
            base_url: Base URL for SkySpark server (e.g., http://server:8080/api)
            project: Project name in SkySpark
            username: Username for authentication
            password: Password for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            pool_size: Connection pool size
        """
        self.base_url = base_url.rstrip("/")
        self.project = project
        self.username = username
        self.password = password
        self.timeout = timeout
        self.max_retries = max_retries
        self.pool_size = pool_size

        # Will be initialized in __aenter__
        self._auth_session: httpx.AsyncClient | None = None
        self._api_session: httpx.AsyncClient | None = None
        self._token_manager: TokenManager | None = None
        self._session_manager: SessionManager | None = None
        self._query: QueryOperations | None = None
        self._entities: EntityOperations | None = None
        self._history: HistoryOperations | None = None

    async def __aenter__(self) -> "SkysparkClient":
        """Async context manager entry."""
        logger.info(
            "skyspark_client_init",
            base_url=self.base_url,
            project=self.project,
            username=self.username,
        )

        # Create separate HTTP sessions for auth and API calls
        # This is required because SkySpark rejects reused connections after auth
        self._auth_session = httpx.AsyncClient(
            timeout=self.timeout,
            limits=httpx.Limits(max_connections=self.pool_size),
        )
        self._api_session = httpx.AsyncClient(
            timeout=self.timeout,
            limits=httpx.Limits(max_connections=self.pool_size),
        )

        # Set up authentication
        authenticator = ScramAuthenticator(
            base_url=self.base_url,
            project=self.project,
            username=self.username,
            password=self.password,
            session=self._auth_session,
        )
        self._token_manager = TokenManager(authenticator)

        # Authenticate immediately
        await self._token_manager.get_token()
        logger.info("skyspark_client_authenticated")

        # Create session manager with API session
        self._session_manager = SessionManager(
            session=self._api_session,
            base_url=self.base_url,
            project=self.project,
            token_provider=self._token_manager,
            max_retries=self.max_retries,
        )

        # Initialize operations
        self._query = QueryOperations(self._session_manager)
        self._entities = EntityOperations(self._session_manager)
        self._history = HistoryOperations(self._session_manager)

        return self

    async def __aexit__(self, exc_type: type, exc_val: Exception, exc_tb: object) -> None:
        """Async context manager exit."""
        if self._auth_session:
            await self._auth_session.aclose()
        if self._api_session:
            await self._api_session.aclose()
        logger.info("skyspark_client_closed")

    # Query operations
    async def read(self, filter_expr: str) -> list[dict]:
        """Execute read operation with filter.

        Args:
            filter_expr: Haystack filter expression

        Returns:
            List of entity dictionaries
        """
        if not self._query:
            msg = "Client not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)
        return await self._query.read_by_filter(filter_expr)

    async def read_by_id(self, entity_id: str) -> dict | None:
        """Read single entity by ID.

        Args:
            entity_id: Entity ID

        Returns:
            Entity dictionary or None if not found
        """
        if not self._query:
            msg = "Client not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)
        return await self._query.read_by_id(entity_id)

    async def read_sites(self) -> list[dict]:
        """Read all sites in project.

        Returns:
            List of site dictionaries
        """
        if not self._query:
            msg = "Client not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)
        return await self._query.read_sites()

    async def read_equipment(self, site_ref: str | None = None) -> list[dict]:
        """Read equipment with optional site filter.

        Args:
            site_ref: Optional site ID to filter by

        Returns:
            List of equipment dictionaries
        """
        if not self._query:
            msg = "Client not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)
        return await self._query.read_equipment(site_ref=site_ref)

    async def read_points(
        self,
        site_ref: str | None = None,
        equip_ref: str | None = None,
    ) -> list[dict]:
        """Read points with optional filters.

        Args:
            site_ref: Optional site ID to filter by
            equip_ref: Optional equipment ID to filter by

        Returns:
            List of point dictionaries
        """
        if not self._query:
            msg = "Client not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)
        return await self._query.read_points(site_ref=site_ref, equip_ref=equip_ref)

    async def read_points_as_models(
        self,
        site_ref: str | None = None,
        equip_ref: str | None = None,
    ) -> list[Point]:
        """Read points and convert to Point models.

        Args:
            site_ref: Optional site ID to filter by
            equip_ref: Optional equipment ID to filter by

        Returns:
            List of Point models
        """
        if not self._query:
            msg = "Client not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)
        return await self._query.read_points_as_models(site_ref=site_ref, equip_ref=equip_ref)

    # Entity operations
    async def create_sites(self, sites: list[Site]) -> list[dict]:
        """Create multiple sites.

        Args:
            sites: List of Site models to create

        Returns:
            List of created site dictionaries with IDs
        """
        if not self._entities:
            msg = "Client not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)
        return await self._entities.create_sites(sites)

    async def create_equipment(self, equipment: list[Equipment]) -> list[dict]:
        """Create multiple equipment.

        Args:
            equipment: List of Equipment models to create

        Returns:
            List of created equipment dictionaries with IDs
        """
        if not self._entities:
            msg = "Client not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)
        return await self._entities.create_equipment(equipment)

    async def create_points(self, points: list[Point]) -> list[dict]:
        """Create multiple points.

        Args:
            points: List of Point models to create

        Returns:
            List of created point dictionaries with IDs
        """
        if not self._entities:
            msg = "Client not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)
        return await self._entities.create_points(points)

    async def update_points(self, points: list[Point]) -> list[dict]:
        """Update multiple points.

        Args:
            points: List of Point models to update (must have IDs)

        Returns:
            List of updated point dictionaries
        """
        if not self._entities:
            msg = "Client not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)
        return await self._entities.update_points(points)

    async def delete_entity(self, entity_id: str) -> None:
        """Delete entity by ID.

        Args:
            entity_id: Entity ID to delete
        """
        if not self._entities:
            msg = "Client not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)
        await self._entities.delete_entity(entity_id)

    # History operations
    async def write_history(
        self,
        samples: list[HistorySample],
        use_rpc: bool = True,
    ) -> HistoryWriteResult:
        """Write history samples.

        Args:
            samples: List of history samples to write
            use_rpc: Use RPC evalAll method (default True for compatibility)

        Returns:
            HistoryWriteResult with success status
        """
        if not self._history:
            msg = "Client not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)
        return await self._history.write_samples(samples, use_rpc=use_rpc)

    async def write_history_chunked(
        self,
        samples: list[HistorySample],
        chunk_size: int = 1000,
        max_concurrent: int = 3,
    ) -> list[HistoryWriteResult]:
        """Write large batches with chunking and parallelization.

        Args:
            samples: All samples to write
            chunk_size: Size of each chunk
            max_concurrent: Maximum concurrent chunk writes

        Returns:
            List of HistoryWriteResult for each chunk
        """
        if not self._history:
            msg = "Client not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)
        return await self._history.write_samples_chunked(
            samples,
            chunk_size=chunk_size,
            max_concurrent=max_concurrent,
        )
