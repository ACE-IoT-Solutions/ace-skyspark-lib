"""Query operations for reading and filtering entities."""

from typing import Any

import structlog

from ace_skyspark_lib.formats.zinc import ZincEncoder
from ace_skyspark_lib.http.session import SessionManager
from ace_skyspark_lib.models.entities import Point

logger = structlog.get_logger()


class QueryOperations:
    """Read and filter operations for entities."""

    def __init__(self, session_manager: SessionManager) -> None:
        """Initialize query operations.

        Args:
            session_manager: HTTP session manager
        """
        self.session = session_manager

    async def read_by_filter(self, filter_expr: str) -> list[dict[str, Any]]:
        """Execute read operation with filter.

        Args:
            filter_expr: Haystack filter expression (e.g., "point and siteRef==@site123")

        Returns:
            List of entity dictionaries

        Raises:
            ServerError: If server returns error
        """
        logger.info("read_by_filter", filter=filter_expr)

        zinc_grid = ZincEncoder.encode_read_by_filter(filter_expr)
        response = await self.session.post_zinc("read", zinc_grid)

        rows = response.get("rows", [])
        logger.info("read_by_filter_complete", count=len(rows))
        return rows

    async def read_by_id(self, entity_id: str) -> dict[str, Any] | None:
        """Read single entity by ID.

        Args:
            entity_id: Entity ID (without @ prefix)

        Returns:
            Entity dictionary or None if not found
        """
        results = await self.read_by_filter(f"id==@{entity_id}")
        return results[0] if results else None

    async def read_by_ids(self, entity_ids: list[str]) -> list[dict[str, Any]]:
        """Read multiple entities by IDs.

        Args:
            entity_ids: List of entity IDs

        Returns:
            List of entity dictionaries
        """
        if not entity_ids:
            return []

        # Build filter: id==@id1 or id==@id2 or ...
        filter_parts = [f"id==@{eid}" for eid in entity_ids]
        filter_expr = " or ".join(filter_parts)

        return await self.read_by_filter(filter_expr)

    async def read_sites(self) -> list[dict[str, Any]]:
        """Read all sites in project.

        Returns:
            List of site dictionaries
        """
        return await self.read_by_filter("site")

    async def read_equipment(
        self,
        site_ref: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read equipment with optional site filter.

        Args:
            site_ref: Optional site ID to filter by

        Returns:
            List of equipment dictionaries
        """
        filter_expr = "equip"
        if site_ref:
            filter_expr += f" and siteRef==@{site_ref}"

        return await self.read_by_filter(filter_expr)

    async def read_points(
        self,
        site_ref: str | None = None,
        equip_ref: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read points with optional filters.

        Args:
            site_ref: Optional site ID to filter by
            equip_ref: Optional equipment ID to filter by

        Returns:
            List of point dictionaries
        """
        filter_expr = "point"
        if site_ref:
            filter_expr += f" and siteRef==@{site_ref}"
        if equip_ref:
            filter_expr += f" and equipRef==@{equip_ref}"

        return await self.read_by_filter(filter_expr)

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
        rows = await self.read_points(site_ref=site_ref, equip_ref=equip_ref)
        return [Point.from_zinc_dict(row) for row in rows]

    async def get_project_timezone(self) -> str:
        """Get the project's default timezone.

        Returns:
            Timezone string (e.g., "New_York", "Chicago", "UTC")

        Raises:
            ValueError: If timezone cannot be determined
        """
        logger.info("get_project_timezone")

        # Query the about endpoint to get project info
        response = await self.session.get_json("about")

        # Extract timezone from response (it's in the rows array)
        rows = response.get("rows", [])
        if not rows:
            msg = "Could not determine project timezone from SkySpark (no rows in about response)"
            logger.error("project_timezone_not_found", response=response)
            raise ValueError(msg)

        # Get timezone from first row
        tz = rows[0].get("tz")
        if isinstance(tz, dict):
            # Handle SkySpark datetime dict format: {"_kind": "dateTime", "val": "...", "tz": "UTC"}
            # In this case, tz is just a string like "UTC"
            tz = tz.get("val") or tz.get("tz")

        if not tz:
            msg = "Could not determine project timezone from SkySpark"
            logger.error("project_timezone_not_found", response=response)
            raise ValueError(msg)

        logger.info("project_timezone_found", tz=tz)
        return str(tz)
