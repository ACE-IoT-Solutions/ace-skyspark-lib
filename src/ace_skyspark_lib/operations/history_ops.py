"""History write operations with batching and chunking."""

import asyncio
import math
import re
from collections import defaultdict
from collections.abc import Generator
from datetime import datetime
from functools import cache
from itertools import islice
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import structlog

from ace_skyspark_lib.exceptions import HistoryWriteError
from ace_skyspark_lib.formats.zinc import ZincEncoder
from ace_skyspark_lib.http.session import SessionManager
from ace_skyspark_lib.models.history import (
    HistoryReadResponse,
    HistorySample,
    HistoryWriteResult,
)

logger = structlog.get_logger()

_POINT_REF_IN_ERROR = re.compile(r'\[@([^\s\]",]+)')
_POINT_SCOPED_HIS_WRITE_ERRORS = ("HisConfigErr", "UnknownRecErr", "HisWriteErr")


class HistoryOperations:
    """History write operations with batching and retry."""

    def __init__(self, session_manager: SessionManager) -> None:
        """Initialize history operations.

        Args:
            session_manager: HTTP session manager
        """
        self.session = session_manager
        self._preferred_write_method = "auto"
        self._rejected_point_ids: set[str] = set()

    @property
    def preferred_write_method(self) -> str:
        """Return the method that subsequent writes will use for this session."""
        return self._preferred_write_method

    @property
    def rejected_point_ids(self) -> frozenset[str]:
        """Return point IDs suppressed after attributable write failures."""
        return frozenset(self._rejected_point_ids)

    async def read_history(
        self,
        point_id: str,
        start_time: datetime,
        end_time: datetime,
        page: int = 1,
        per_page: int = 1000,
    ) -> HistoryReadResponse:
        """Read history samples for a point using paginated endpoint.

        Args:
            point_id: Point ID (without @)
            start_time: Start of range
            end_time: End of range
            page: Page number
            per_page: Samples per page

        Returns:
            Paginated HistoryReadResponse
        """
        logger.info(
            "read_history",
            point_id=point_id,
            start=start_time.isoformat(),
            end=end_time.isoformat(),
            page=page,
            per_page=per_page,
        )

        params = {
            "id": f"@{point_id}",
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "page": page,
            "per_page": per_page,
        }

        response = await self.session.get_json("timeseries", params=params)

        # Standard ACE PaginatedResponse format
        # {
        #   "page": 1,
        #   "pages": 10,
        #   "per_page": 1000,
        #   "total": 10000,
        #   "items": [{"pointId": "...", "timestamp": "...", "value": ...}, ...]
        # }
        return HistoryReadResponse.model_validate(response)

    async def read_history_all(
        self,
        point_id: str,
        start_time: datetime,
        end_time: datetime,
        per_page: int = 5000,
    ) -> list[HistorySample]:
        """Read all history samples for a point across all pages.

        Args:
            point_id: Point ID
            start_time: Start of range
            end_time: End of range
            per_page: Samples per page to use for each request

        Returns:
            Flattened list of all HistorySamples
        """
        all_samples: list[HistorySample] = []
        current_page = 1

        while True:
            response = await self.read_history(
                point_id=point_id,
                start_time=start_time,
                end_time=end_time,
                page=current_page,
                per_page=per_page,
            )

            all_samples.extend(response.items)

            if current_page >= response.pages:
                break

            current_page += 1

        logger.info(
            "read_history_all_complete",
            point_id=point_id,
            total_samples=len(all_samples),
            pages=current_page,
        )
        return all_samples

    async def write_samples(
        self,
        samples: list[HistorySample],
        use_rpc: bool = False,
        max_request_size: int = 1000,
    ) -> HistoryWriteResult:
        """Write history samples.

        Args:
            samples: List of history samples to write
            use_rpc: Use the legacy RPC evalAll method instead of batch hisWrite
            max_request_size: Maximum samples in each HTTP hisWrite request

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
        if max_request_size <= 0:
            msg = "max_request_size must be greater than zero"
            raise ValueError(msg)

        known_rejected_samples = [
            sample for sample in samples if sample.point_id in self._rejected_point_ids
        ]
        if known_rejected_samples:
            logger.warning(
                "write_samples_skipped_rejected_points",
                point_ids=sorted({sample.point_id for sample in known_rejected_samples}),
                skipped_samples=len(known_rejected_samples),
                session_rejected_points=len(self._rejected_point_ids),
            )

        finite_samples = [
            sample
            for sample in samples
            if not (isinstance(sample.value, float) and not math.isfinite(sample.value))
        ]
        skipped_nonfinite = len(samples) - len(finite_samples)
        if skipped_nonfinite:
            logger.warning(
                "write_samples_skipped_nonfinite",
                skipped=skipped_nonfinite,
                total=len(samples),
            )
        valid_samples = [
            sample for sample in finite_samples if sample.point_id not in self._rejected_point_ids
        ]
        if not valid_samples:
            return HistoryWriteResult(
                success=True,
                samplesWritten=0,
                details={
                    "method": self._preferred_write_method,
                    "preferred_method": self._preferred_write_method,
                    "rejected_point_ids": sorted(self._rejected_point_ids),
                    "skipped_known_rejected_samples": len(known_rejected_samples),
                    "session_rejected_point_ids": sorted(self._rejected_point_ids),
                },
            )

        selected_method = "rpc" if use_rpc else self._preferred_write_method

        logger.info(
            "write_samples",
            count=len(valid_samples),
            method=selected_method,
            skipped_known_rejected_samples=len(known_rejected_samples),
        )

        if selected_method != "auto":
            try:
                result = await self._write_samples_with_method(
                    selected_method,
                    valid_samples,
                    max_request_size,
                )
            except Exception as error:
                logger.error(
                    "write_samples_failed",
                    method=selected_method,
                    error=str(error),
                )
                result = HistoryWriteResult(
                    success=False,
                    samplesWritten=0,
                    error=str(error),
                    details={"method": selected_method},
                )
            return self._finalize_write_result(
                result,
                valid_samples,
                len(known_rejected_samples),
            )

        fallback_errors: list[str] = []
        try:
            result = await self._write_samples_http(valid_samples, max_request_size)
            result.details["method"] = "batch_http"
            self._preferred_write_method = "batch_http"
            return self._finalize_write_result(
                result,
                valid_samples,
                len(known_rejected_samples),
            )
        except Exception as error:
            fallback_errors.append(f"batch_http: {error}")
            logger.warning("write_samples_fallback", failed_method="batch_http", error=str(error))

        try:
            result = await self._write_samples_rpc(valid_samples)
            if result.success:
                result.details.update({"method": "rpc", "fallback_errors": fallback_errors.copy()})
                self._preferred_write_method = "rpc"
                return self._finalize_write_result(
                    result,
                    valid_samples,
                    len(known_rejected_samples),
                )
            rpc_error = result.error or "legacy bulk evalAll returned an unsuccessful result"
            fallback_errors.append(f"rpc: {rpc_error}")
            logger.warning("write_samples_fallback", failed_method="rpc", error=rpc_error)
        except Exception as error:
            fallback_errors.append(f"rpc: {error}")
            logger.warning("write_samples_fallback", failed_method="rpc", error=str(error))

        try:
            result = await self._write_samples_single_http(valid_samples, max_request_size)
            result.details.update(
                {"method": "single_http", "fallback_errors": fallback_errors.copy()}
            )
            self._preferred_write_method = "single_http"
            return self._finalize_write_result(
                result,
                valid_samples,
                len(known_rejected_samples),
            )
        except Exception as error:
            fallback_errors.append(f"single_http: {error}")
            logger.error("write_samples_failed", method="single_http", error=str(error))
            result = HistoryWriteResult(
                success=False,
                samplesWritten=0,
                error="; ".join(fallback_errors),
                details={"method": "single_http", "fallback_errors": fallback_errors},
            )
            return self._finalize_write_result(
                result,
                valid_samples,
                len(known_rejected_samples),
            )

    async def _write_samples_with_method(
        self,
        method: str,
        samples: list[HistorySample],
        max_request_size: int,
    ) -> HistoryWriteResult:
        """Execute exactly one selected write strategy without fallback."""
        if method == "batch_http":
            result = await self._write_samples_http(samples, max_request_size)
        elif method == "rpc":
            result = await self._write_samples_rpc(samples)
        elif method == "single_http":
            result = await self._write_samples_single_http(samples, max_request_size)
        else:
            msg = f"Unknown history write method: {method}"
            raise ValueError(msg)
        result.details["method"] = method
        return result

    def _finalize_write_result(
        self,
        result: HistoryWriteResult,
        samples: list[HistorySample],
        skipped_known_rejected_samples: int,
    ) -> HistoryWriteResult:
        """Persist point rejections and annotate the result with session state."""
        rejected_ids = {
            str(point_id)
            for key in ("rejected_point_ids", "failed_point_ids")
            for point_id in result.details.get(key, [])
        }
        self._rejected_point_ids.update(rejected_ids)
        result.details.setdefault(
            "rejected_samples",
            sum(sample.point_id in rejected_ids for sample in samples),
        )
        result.details.update(
            {
                "preferred_method": self._preferred_write_method,
                "skipped_known_rejected_samples": skipped_known_rejected_samples,
                "session_rejected_point_ids": sorted(self._rejected_point_ids),
            }
        )
        return result

    async def _write_samples_rpc(self, samples: list[HistorySample]) -> HistoryWriteResult:
        """Write samples using RPC evalAll method.

        Args:
            samples: History samples to write

        Returns:
            HistoryWriteResult
        """
        zinc_grid = ZincEncoder.encode_his_write_rpc(samples)
        logger.debug(
            "write_samples_rpc_request",
            sample_count=len(samples),
            zinc_size=len(zinc_grid),
        )
        response = await self.session.post_zinc("evalAll", zinc_grid)

        # Check for grid-level error (structured response path)
        if response.get("meta", {}).get("err"):
            error_msg = response.get("meta", {}).get("dis", "Unknown error")
            logger.error("write_samples_rpc_grid_error", error=error_msg)
            raise HistoryWriteError(error_msg)

        # evalAll returns a multi-grid text blob (one Zinc grid per expression), not
        # a structured rows list. Detect per-expression errors by scanning for errType:.
        response_text = response.get("text", "")
        if response_text:
            grids = [g.strip() for g in response_text.split("\n\n") if g.strip()]
            failed_samples: list[dict[str, object]] = []
            samples_written = 0
            for index, sample in enumerate(samples):
                if index >= len(grids):
                    excerpt = "Missing evalAll response grid"
                elif "errType:" in grids[index]:
                    excerpt = grids[index][:400].replace("\n", " ")
                else:
                    samples_written += 1
                    continue

                failure = {
                    "point_id": sample.point_id,
                    "timestamp": sample.timestamp.isoformat(),
                    "error": excerpt,
                }
                failed_samples.append(failure)
                logger.warning("write_samples_rpc_sample_failed", **failure)

            if len(grids) > len(samples):
                logger.warning(
                    "write_samples_rpc_extra_grids",
                    expected=len(samples),
                    received=len(grids),
                )

            if failed_samples:
                log = logger.warning if samples_written else logger.error
                log(
                    "write_samples_rpc_errors",
                    failed=len(failed_samples),
                    succeeded=samples_written,
                    total=len(samples),
                    failed_point_ids=[failure["point_id"] for failure in failed_samples],
                )
                # Partial RPC success is terminal: successful expressions have already
                # written their samples, and retrying the entire input would duplicate
                # work and eventually degrade to one request per point.
                return HistoryWriteResult(
                    success=samples_written > 0,
                    samplesWritten=samples_written,
                    error=None if samples_written else str(failed_samples[0]["error"])[:300],
                    details={
                        "failed_samples": failed_samples,
                        "failed_point_ids": list(
                            dict.fromkeys(str(failure["point_id"]) for failure in failed_samples)
                        ),
                        "response_grid_count": len(grids),
                    },
                )
            logger.info("write_samples_rpc_complete", count=len(samples))
            return HistoryWriteResult(success=True, samplesWritten=len(samples))

        # Structured response fallback (non-evalAll paths)
        rows = response.get("rows", [])
        row_errors = []
        for i, row in enumerate(rows):
            if isinstance(row, dict) and row.get("err"):
                sample = samples[i] if i < len(samples) else None
                row_errors.append(
                    {
                        "row_index": i,
                        "error": row.get("dis", "unknown row error"),
                        "point_id": sample.point_id if sample else "unknown",
                        "timestamp": sample.timestamp.isoformat() if sample else "unknown",
                    }
                )

        if row_errors:
            logger.error(
                "write_samples_rpc_row_errors",
                failed=len(row_errors),
                total=len(samples),
                first_errors=row_errors[:5],
            )
            raise HistoryWriteError(
                f"{len(row_errors)}/{len(samples)} hisWrite calls failed; "
                f"first error: {row_errors[0]['error']}"
            )

        logger.info("write_samples_rpc_complete", count=len(samples), rows_returned=len(rows))
        return HistoryWriteResult(success=True, samplesWritten=len(samples))

    async def _write_samples_http(
        self,
        samples: list[HistorySample],
        max_request_size: int,
    ) -> HistoryWriteResult:
        """Write samples using timezone-aware standard batch hisWrite requests.

        Args:
            samples: History samples to write

        Returns:
            HistoryWriteResult
        """
        point_ids = list(dict.fromkeys(sample.point_id for sample in samples))
        point_timezones = await self._read_point_timezones(point_ids)

        by_timezone: dict[str, list[HistorySample]] = defaultdict(list)
        for sample in samples:
            timezone_name = point_timezones[sample.point_id]
            timezone = _resolve_timezone(timezone_name, sample.timestamp)
            by_timezone[timezone_name].append(
                sample.model_copy(update={"timestamp": sample.timestamp.astimezone(timezone)})
            )

        request_count = 0
        rejected_point_ids: set[str] = set()
        rejection_errors: list[str] = []
        for timezone_name, timezone_samples in by_timezone.items():
            timezone_samples.sort(key=lambda sample: (sample.timestamp, sample.point_id))
            for request_samples in self._chunk_list(timezone_samples, max_request_size):
                pending_samples = [
                    sample
                    for sample in request_samples
                    if sample.point_id not in rejected_point_ids
                ]
                while pending_samples:
                    zinc_grid = ZincEncoder.encode_his_write_batch(pending_samples, timezone_name)
                    logger.debug(
                        "write_samples_http_request",
                        timezone=timezone_name,
                        sample_count=len(pending_samples),
                        point_count=len({sample.point_id for sample in pending_samples}),
                        zinc_size=len(zinc_grid),
                    )
                    response = await self.session.post_zinc("hisWrite", zinc_grid)
                    request_count += 1
                    try:
                        self._raise_for_his_write_error(response)
                    except HistoryWriteError as error:
                        error_text = str(error)
                        failed_point_ids = self._point_ids_from_his_write_error(
                            error_text,
                            {sample.point_id for sample in pending_samples},
                        )
                        if not failed_point_ids:
                            raise
                        rejected_point_ids.update(failed_point_ids)
                        rejection_errors.append(error_text)
                        pending_samples = [
                            sample
                            for sample in pending_samples
                            if sample.point_id not in failed_point_ids
                        ]
                        logger.warning(
                            "write_samples_http_skipping_points",
                            point_ids=sorted(failed_point_ids),
                            skipped_samples=sum(
                                sample.point_id in failed_point_ids for sample in samples
                            ),
                            remaining_samples=len(pending_samples),
                            error=error_text,
                        )
                        continue
                    break

        rejected_samples = sum(sample.point_id in rejected_point_ids for sample in samples)

        logger.info(
            "write_samples_http_complete",
            count=len(samples) - rejected_samples,
            rejected_samples=rejected_samples,
            rejected_points=len(rejected_point_ids),
            requests=request_count,
            timezones=list(by_timezone),
        )
        return HistoryWriteResult(
            success=True,
            samplesWritten=len(samples) - rejected_samples,
            error="; ".join(dict.fromkeys(rejection_errors)) or None,
            details={
                "requests": request_count,
                "timezones": list(by_timezone),
                "rejected_point_ids": sorted(rejected_point_ids),
                "rejected_samples": rejected_samples,
            },
        )

    @staticmethod
    def _point_ids_from_his_write_error(
        error: str,
        candidate_point_ids: set[str],
    ) -> set[str]:
        """Extract safely attributable point refs from a point-scoped error."""
        if not any(error_type in error for error_type in _POINT_SCOPED_HIS_WRITE_ERRORS):
            return set()
        return {
            point_id
            for point_id in _POINT_REF_IN_ERROR.findall(error)
            if point_id in candidate_point_ids
        }

    async def _write_samples_single_http(
        self,
        samples: list[HistorySample],
        max_request_size: int,
    ) -> HistoryWriteResult:
        """Write one point per standard Zinc hisWrite request as a final fallback."""
        point_ids = list(dict.fromkeys(sample.point_id for sample in samples))
        point_timezones = await self._read_point_timezones(point_ids)
        by_point: dict[str, list[HistorySample]] = defaultdict(list)
        for sample in samples:
            timezone_name = point_timezones[sample.point_id]
            timezone = _resolve_timezone(timezone_name, sample.timestamp)
            by_point[sample.point_id].append(
                sample.model_copy(update={"timestamp": sample.timestamp.astimezone(timezone)})
            )

        request_count = 0
        for point_id, point_samples in by_point.items():
            timezone_name = point_timezones[point_id]
            for request_samples in self._chunk_list(point_samples, max_request_size):
                zinc_grid = ZincEncoder.encode_his_write_single(
                    point_id,
                    request_samples,
                    timezone_name,
                )
                logger.debug(
                    "write_samples_single_http_request",
                    point_id=point_id,
                    timezone=timezone_name,
                    sample_count=len(request_samples),
                    zinc_size=len(zinc_grid),
                )
                response = await self.session.post_zinc("hisWrite", zinc_grid)
                self._raise_for_his_write_error(response)
                request_count += 1

        logger.info(
            "write_samples_single_http_complete",
            count=len(samples),
            requests=request_count,
            points=len(by_point),
        )
        return HistoryWriteResult(
            success=True,
            samplesWritten=len(samples),
            details={"requests": request_count, "points": len(by_point)},
        )

    async def _read_point_timezones(self, point_ids: list[str]) -> dict[str, str]:
        """Read and validate configured timezones for a set of points."""
        response = await self.session.post_zinc(
            "read",
            ZincEncoder.encode_read_by_ids(point_ids),
        )
        if response.get("meta", {}).get("err"):
            error_msg = response.get("meta", {}).get("dis", "Unable to read point timezones")
            raise HistoryWriteError(str(error_msg))

        rows = response.get("rows", [])
        point_timezones: dict[str, str] = {}
        for index, point_id in enumerate(point_ids):
            row = rows[index] if index < len(rows) else None
            timezone_name = row.get("tz") if isinstance(row, dict) else None
            if isinstance(timezone_name, dict):
                timezone_name = timezone_name.get("val") or timezone_name.get("tz")
            if not timezone_name:
                msg = f"Point @{point_id} was not found or has no configured timezone"
                raise HistoryWriteError(msg)
            point_timezones[point_id] = str(timezone_name)
        return point_timezones

    @staticmethod
    def _raise_for_his_write_error(response: dict[str, object]) -> None:
        """Raise for structured or Zinc-text error grids."""
        meta = response.get("meta")
        if isinstance(meta, dict) and meta.get("err"):
            raise HistoryWriteError(str(meta.get("dis", "Unknown hisWrite error")))
        response_text = response.get("text")
        if isinstance(response_text, str) and (
            "errType:" in response_text or " err" in response_text
        ):
            excerpt = response_text[:400].replace("\n", " ")
            raise HistoryWriteError(excerpt)

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
        if chunk_size <= 0:
            msg = "chunk_size must be greater than zero"
            raise ValueError(msg)
        if max_concurrent <= 0:
            msg = "max_concurrent must be greater than zero"
            raise ValueError(msg)

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
                return await self.write_samples(chunk, max_request_size=chunk_size)

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


@cache
def _timezone_candidates(timezone_name: str) -> tuple[str, ...]:
    """Map a Haystack city timezone name to installed IANA timezone keys."""
    if "/" in timezone_name or timezone_name == "UTC":
        return (timezone_name,)
    suffix = f"/{timezone_name}"
    return tuple(sorted(zone for zone in available_timezones() if zone.endswith(suffix)))


def _resolve_timezone(timezone_name: str, timestamp: datetime) -> ZoneInfo:
    """Resolve Haystack timezone names, preferring the timestamp's own zone."""
    timestamp_zone = getattr(timestamp.tzinfo, "key", None) or getattr(
        timestamp.tzinfo, "zone", None
    )
    if isinstance(timestamp_zone, str) and (
        timestamp_zone == timezone_name or timestamp_zone.endswith(f"/{timezone_name}")
    ):
        return ZoneInfo(timestamp_zone)

    candidates = _timezone_candidates(timezone_name)
    if len(candidates) != 1:
        if not candidates:
            msg = f"Unknown point timezone {timezone_name!r}"
        else:
            msg = f"Ambiguous point timezone {timezone_name!r}: {', '.join(candidates)}"
        raise HistoryWriteError(msg)
    try:
        return ZoneInfo(candidates[0])
    except ZoneInfoNotFoundError as error:
        msg = f"Unknown point timezone {timezone_name!r}"
        raise HistoryWriteError(msg) from error
