"""Query operations for reading and filtering entities."""

from typing import Any

import structlog

from ace_skyspark_lib.exceptions import ServerError
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

    @staticmethod
    def _raise_for_read_error(
        response: dict[str, Any],
        *,
        event: str,
        default_message: str,
        **log_fields: Any,
    ) -> None:
        """Raise a structured exception when SkySpark returns an error grid."""
        meta = response.get("meta", {})
        if not isinstance(meta, dict) or not meta.get("err"):
            return

        error_msg = str(meta.get("dis", default_message))
        error_type = str(meta["errType"]) if meta.get("errType") else None
        trace_value = meta.get("errTrace") or meta.get("trace")
        trace = str(trace_value) if trace_value else None
        logger.error(event, error=error_msg, error_type=error_type, **log_fields)
        raise ServerError(error_msg, error_type=error_type, trace=trace)

    async def read_by_filter(self, filter_expr: str) -> list[dict[str, Any]]:
        """Execute read operation with filter.

        Args:
            filter_expr: Haystack filter expression (e.g., "point and siteRef==@site123")

        Returns:
            List of entity dictionaries

        Raises:
            ServerError: If server returns error
        """
        filter_preview = filter_expr
        if len(filter_preview) > 500:
            filter_preview = filter_preview[:500] + "..."
        logger.info(
            "read_by_filter",
            filter=filter_preview,
            filter_length=len(filter_expr),
        )

        zinc_grid = ZincEncoder.encode_read_by_filter(filter_expr)
        response = await self.session.post_zinc("read", zinc_grid)

        self._raise_for_read_error(
            response,
            event="read_by_filter_failed",
            default_message="SkySpark read failed",
            filter_length=len(filter_expr),
        )

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
        results = await self.read_by_ids([entity_id])
        return results[0] if results and results[0] else None

    async def read_by_ids(self, entity_ids: list[str]) -> list[dict[str, Any]]:
        """Read multiple entities by IDs.

        Args:
            entity_ids: List of entity IDs

        Returns:
            Entity dictionaries in request order. Missing entities are represented
            by empty dictionaries.
        """
        if not entity_ids:
            return []

        logger.info("read_by_ids", count=len(entity_ids))
        response = await self.session.post_zinc("read", ZincEncoder.encode_read_by_ids(entity_ids))

        self._raise_for_read_error(
            response,
            event="read_by_ids_failed",
            default_message="SkySpark read by IDs failed",
            count=len(entity_ids),
        )

        rows = response.get("rows", [])
        logger.info("read_by_ids_complete", count=len(rows))
        return rows

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
        his_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Read points with optional filters.

        Args:
            site_ref: Optional site ID to filter by
            equip_ref: Optional equipment ID to filter by
            his_only: If True, only return historized points

        Returns:
            List of point dictionaries
        """
        filter_expr = "point"
        if his_only:
            filter_expr += " and his"
        if site_ref:
            filter_expr += f" and siteRef==@{site_ref}"
        if equip_ref:
            filter_expr += f" and equipRef==@{equip_ref}"

        return await self.read_by_filter(filter_expr)

    async def read_points_as_models(
        self,
        site_ref: str | None = None,
        equip_ref: str | None = None,
        his_only: bool = False,
    ) -> list[Point]:
        """Read points and convert to Point models.

        Args:
            site_ref: Optional site ID to filter by
            equip_ref: Optional equipment ID to filter by
            his_only: If True, only return historized points

        Returns:
            List of Point models
        """
        rows = await self.read_points(site_ref=site_ref, equip_ref=equip_ref, his_only=his_only)
        return [Point.from_zinc_dict(row) for row in rows]

    async def get_project_timezone(self) -> str:
        """Get the project's default timezone.

        Checks for timezone in this order:
        1. Project entity's tz tag (if project entity exists with 'proj' marker)
        2. About endpoint's tz field (server default)

        Returns:
            Timezone string (e.g., "New_York", "Chicago", "UTC")

        Raises:
            ValueError: If timezone cannot be determined
        """
        logger.info("get_project_timezone")

        # Try to get timezone from project entity first
        try:
            project_entities = await self.read_by_filter("proj")
            if project_entities:
                proj_tz = project_entities[0].get("tz")
                if proj_tz:
                    logger.info(
                        "project_timezone_found_from_entity",
                        tz=proj_tz,
                        source="project_entity",
                    )
                    return str(proj_tz)
                logger.debug("project_entity_found_but_no_tz", entity=project_entities[0])
        except Exception as e:
            logger.warning("failed_to_read_project_entity", error=str(e))

        # Fall back to about endpoint (server default timezone)
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

        logger.info("project_timezone_found_from_about", tz=tz, source="about_endpoint")
        return str(tz)
