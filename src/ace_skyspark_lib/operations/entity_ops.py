"""Entity CRUD operations."""

from typing import Any

import structlog

from ace_skyspark_lib.exceptions import CommitError, EntityNotFoundError
from ace_skyspark_lib.formats.zinc import ZincEncoder
from ace_skyspark_lib.http.session import SessionManager
from ace_skyspark_lib.models.entities import Equipment, Point, Site

logger = structlog.get_logger()


class EntityOperations:
    """CRUD operations for SkySpark entities."""

    def __init__(self, session_manager: SessionManager) -> None:
        """Initialize entity operations.

        Args:
            session_manager: HTTP session manager
        """
        self.session = session_manager

    async def create_sites(self, sites: list[Site]) -> list[dict[str, Any]]:
        """Create multiple sites.

        Args:
            sites: List of Site models to create

        Returns:
            List of created site dictionaries with IDs

        Raises:
            CommitError: If commit operation fails
        """
        if not sites:
            return []

        logger.info("create_sites", count=len(sites))

        zinc_grid = ZincEncoder.encode_commit_add_sites(sites)
        response = await self.session.post_zinc("commit", zinc_grid)

        # Check for error
        if response.get("meta", {}).get("err"):
            error_msg = response.get("meta", {}).get("dis", "Unknown error")
            logger.error("create_sites_failed", error=error_msg)
            raise CommitError(error_msg)

        rows = response.get("rows", [])
        logger.info("create_sites_complete", count=len(rows))
        return rows

    async def create_equipment(self, equipment: list[Equipment]) -> list[dict[str, Any]]:
        """Create multiple equipment.

        Args:
            equipment: List of Equipment models to create

        Returns:
            List of created equipment dictionaries with IDs

        Raises:
            CommitError: If commit operation fails
        """
        if not equipment:
            return []

        logger.info("create_equipment", count=len(equipment))

        zinc_grid = ZincEncoder.encode_commit_add_equipment(equipment)
        response = await self.session.post_zinc("commit", zinc_grid)

        if response.get("meta", {}).get("err"):
            error_msg = response.get("meta", {}).get("dis", "Unknown error")
            logger.error("create_equipment_failed", error=error_msg)
            raise CommitError(error_msg)

        rows = response.get("rows", [])
        logger.info("create_equipment_complete", count=len(rows))
        return rows

    async def update_equipment(self, equipment: list[Equipment]) -> list[dict[str, Any]]:
        """Update multiple equipment.

        Args:
            equipment: List of Equipment models to update (must have IDs)

        Returns:
            List of updated equipment dictionaries

        Raises:
            CommitError: If commit operation fails
            ValueError: If any equipment is missing an ID
        """
        if not equipment:
            return []

        # Validate all equipment have IDs
        for equip in equipment:
            if not equip.id:
                msg = f"Equipment {equip.dis} must have an ID for update operations"
                raise ValueError(msg)

        logger.info("update_equipment", count=len(equipment))

        zinc_grid = ZincEncoder.encode_commit_update_equipment(equipment)
        logger.debug("update_equipment_zinc_grid", grid=zinc_grid)
        response = await self.session.post_zinc("commit", zinc_grid)

        if response.get("meta", {}).get("err"):
            error_msg = response.get("meta", {}).get("dis", "Unknown error")
            logger.error("update_equipment_failed", error=error_msg)
            raise CommitError(error_msg)

        rows = response.get("rows", [])
        logger.info("update_equipment_complete", count=len(rows))
        return rows

    async def create_points(self, points: list[Point]) -> list[dict[str, Any]]:
        """Create multiple points.

        Args:
            points: List of Point models to create

        Returns:
            List of created point dictionaries with IDs

        Raises:
            CommitError: If commit operation fails
        """
        if not points:
            return []

        logger.info("create_points", count=len(points))

        zinc_grid = ZincEncoder.encode_commit_add_points(points)
        response = await self.session.post_zinc("commit", zinc_grid)

        if response.get("meta", {}).get("err"):
            error_msg = response.get("meta", {}).get("dis", "Unknown error")
            logger.error("create_points_failed", error=error_msg)
            raise CommitError(error_msg)

        rows = response.get("rows", [])
        logger.info("create_points_complete", count=len(rows))
        return rows

    async def update_points(self, points: list[Point]) -> list[dict[str, Any]]:
        """Update multiple points.

        Args:
            points: List of Point models to update (must have IDs)

        Returns:
            List of updated point dictionaries

        Raises:
            CommitError: If commit operation fails
            ValueError: If any point is missing an ID
        """
        if not points:
            return []

        # Validate all points have IDs
        for point in points:
            if not point.id:
                msg = f"Point {point.dis} must have an ID for update operations"
                raise ValueError(msg)

        logger.info("update_points", count=len(points))

        zinc_grid = ZincEncoder.encode_commit_update_points(points)
        response = await self.session.post_zinc("commit", zinc_grid)

        if response.get("meta", {}).get("err"):
            error_msg = response.get("meta", {}).get("dis", "Unknown error")
            logger.error("update_points_failed", error=error_msg)
            raise CommitError(error_msg)

        rows = response.get("rows", [])
        logger.info("update_points_complete", count=len(rows))
        return rows

    async def delete_entity(self, entity_id: str | dict[str, Any]) -> None:
        """Delete entity by ID.

        SkySpark requires the mod field for optimistic locking - we need to read
        the entity first to get its current mod timestamp.

        Args:
            entity_id: Entity ID to delete (string or dict from SkySpark response)

        Raises:
            CommitError: If delete operation fails
            EntityNotFoundError: If entity does not exist
        """
        logger.info("delete_entity", entity_id=entity_id)

        # Extract ID from dict if needed (SkySpark returns refs as dicts)
        if isinstance(entity_id, dict):
            entity_id = entity_id.get("val", "").lstrip("@")
        elif isinstance(entity_id, str):
            entity_id = entity_id.lstrip("@")

        # Read the entity first to get the mod field (required for optimistic locking)
        read_grid = 'ver:"3.0"\n'
        read_grid += "filter\n"
        read_grid += f'"id==@{entity_id}"\n'

        read_response = await self.session.post_zinc("read", read_grid)
        rows = read_response.get("rows", [])

        if not rows:
            raise EntityNotFoundError(f"Entity {entity_id} not found")

        entity = rows[0]
        mod_field = entity.get("mod", "")

        # Extract mod timestamp - it comes as a dict {"_kind": "dateTime", "val": "...", "tz": "..."}
        if isinstance(mod_field, dict):
            mod_val = mod_field.get("val", "")
            mod_tz = mod_field.get("tz", "UTC")
            mod_timestamp = f"{mod_val} {mod_tz}"
        else:
            mod_timestamp = str(mod_field)

        # Build delete grid with id and mod columns
        zinc_grid = 'ver:"3.0" commit:"remove"\n'
        zinc_grid += "id, mod\n"
        zinc_grid += f"@{entity_id}, {mod_timestamp}\n"

        response = await self.session.post_zinc("commit", zinc_grid)

        if response.get("meta", {}).get("err"):
            error_msg = response.get("meta", {}).get("dis", "Unknown error")
            logger.error("delete_entity_failed", error=error_msg, entity_id=entity_id)

            # Check if it's a "not found" error
            if "not found" in error_msg.lower():
                raise EntityNotFoundError(f"Entity {entity_id} not found")

            raise CommitError(error_msg)

        logger.info("delete_entity_complete", entity_id=entity_id)

    async def delete_entities(self, entity_ids: list[str]) -> None:
        """Delete multiple entities by ID.

        Args:
            entity_ids: List of entity IDs to delete

        Raises:
            CommitError: If delete operation fails
        """
        if not entity_ids:
            return

        logger.info("delete_entities", count=len(entity_ids))

        zinc_grid = 'ver:"3.0" commit:"remove"\n'
        zinc_grid += "id\n"
        for entity_id in entity_ids:
            zinc_grid += f"@{entity_id}\n"

        response = await self.session.post_zinc("commit", zinc_grid)

        if response.get("meta", {}).get("err"):
            error_msg = response.get("meta", {}).get("dis", "Unknown error")
            logger.error("delete_entities_failed", error=error_msg)
            raise CommitError(error_msg)

        logger.info("delete_entities_complete", count=len(entity_ids))
