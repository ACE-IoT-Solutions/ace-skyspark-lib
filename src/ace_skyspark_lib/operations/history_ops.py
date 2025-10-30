"""History write operations with batching and chunking."""

import asyncio
from collections.abc import Generator
from itertools import islice

import structlog

from ace_skyspark_lib.exceptions import HistoryWriteError
from ace_skyspark_lib.formats.zinc import ZincEncoder
from ace_skyspark_lib.http.session import SessionManager
from ace_skyspark_lib.models.history import HistorySample, HistoryWriteResult

logger = structlog.get_logger()


class HistoryOperations:
    """History write operations with batching and retry."""

    def __init__(self, session_manager: SessionManager) -> None:
        """Initialize history operations.

        Args:
            session_manager: HTTP session manager
        """
        self.session = session_manager

    async def write_samples(
        self,
        samples: list[HistorySample],
        use_rpc: bool = True,
    ) -> HistoryWriteResult:
        """Write history samples.

        Args:
            samples: List of history samples to write
            use_rpc: Use RPC evalAll method (default True for compatibility)

        Returns:
            HistoryWriteResult with success status and count

        Raises:
            HistoryWriteError: If write operation fails
        """
        if not samples:
            return HistoryWriteResult(
                success=True,
                samplesWritten=0,
            )

        logger.info("write_samples", count=len(samples), method="rpc" if use_rpc else "http")

        try:
            if use_rpc:
                return await self._write_samples_rpc(samples)
            return await self._write_samples_http(samples)

        except Exception as e:
            logger.error("write_samples_failed", error=str(e))
            return HistoryWriteResult(
                success=False,
                samplesWritten=0,
                error=str(e),
            )

    async def _write_samples_rpc(self, samples: list[HistorySample]) -> HistoryWriteResult:
        """Write samples using RPC evalAll method.

        Args:
            samples: History samples to write

        Returns:
            HistoryWriteResult
        """
        zinc_grid = ZincEncoder.encode_his_write_rpc(samples)
        response = await self.session.post_zinc("evalAll", zinc_grid)

        # Check for errors in response
        if response.get("meta", {}).get("err"):
            error_msg = response.get("meta", {}).get("dis", "Unknown error")
            raise HistoryWriteError(error_msg)

        logger.info("write_samples_rpc_complete", count=len(samples))
        return HistoryWriteResult(
            success=True,
            samplesWritten=len(samples),
        )

    async def _write_samples_http(self, samples: list[HistorySample]) -> HistoryWriteResult:
        """Write samples using modern HTTP API (placeholder for future implementation).

        Args:
            samples: History samples to write

        Returns:
            HistoryWriteResult
        """
        # TODO: Implement modern HTTP API batch hisWrite when available
        # For now, fall back to RPC method
        logger.warning("http_method_not_implemented", fallback="rpc")
        return await self._write_samples_rpc(samples)

    async def write_samples_chunked(
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
        if not samples:
            return []

        logger.info(
            "write_samples_chunked",
            total=len(samples),
            chunk_size=chunk_size,
            max_concurrent=max_concurrent,
        )

        # Group samples by point_id and sort by timestamp
        by_point: dict[str, list[HistorySample]] = {}
        for sample in samples:
            if sample.point_id not in by_point:
                by_point[sample.point_id] = []
            by_point[sample.point_id].append(sample)

        # Sort each point's samples chronologically
        for point_samples in by_point.values():
            point_samples.sort(key=lambda s: s.timestamp)

        # Flatten back to single list (now sorted)
        sorted_samples = []
        for point_samples in by_point.values():
            sorted_samples.extend(point_samples)

        # Split into chunks
        chunks = list(self._chunk_list(sorted_samples, chunk_size))
        logger.info("chunks_created", count=len(chunks))

        # Process chunks with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        results: list[HistoryWriteResult] = []

        async def process_chunk(chunk: list[HistorySample]) -> HistoryWriteResult:
            async with semaphore:
                return await self.write_samples(chunk)

        # Execute all chunks
        chunk_results = await asyncio.gather(
            *[process_chunk(chunk) for chunk in chunks],
            return_exceptions=True,
        )

        # Convert exceptions to failed results
        for result in chunk_results:
            if isinstance(result, BaseException):
                results.append(
                    HistoryWriteResult(
                        success=False,
                        samplesWritten=0,
                        error=str(result),
                    )
                )
            elif isinstance(result, HistoryWriteResult):
                results.append(result)

        # Log summary
        total_written = sum(r.samples_written for r in results)
        failed_count = sum(1 for r in results if not r.success)

        logger.info(
            "write_samples_chunked_complete",
            total_written=total_written,
            chunks=len(results),
            failed=failed_count,
        )

        return results

    @staticmethod
    def _chunk_list(
        items: list[HistorySample], size: int
    ) -> Generator[list[HistorySample], None, None]:
        """Split list into chunks of given size.

        Args:
            items: List to chunk
            size: Chunk size

        Yields:
            Chunks of items
        """
        iterator = iter(items)
        while chunk := list(islice(iterator, size)):
            yield chunk
