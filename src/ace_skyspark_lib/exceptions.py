"""Custom exception hierarchy for ace-skyspark-lib."""


class SkysparkError(Exception):
    """Base exception for all SkySpark client errors."""


class AuthenticationError(SkysparkError):
    """Authentication failed."""


class SkysparkConnectionError(SkysparkError):
    """Connection to SkySpark server failed."""


class ValidationError(SkysparkError):
    """Data validation failed."""

    def __init__(self, message: str, errors: list[dict] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


class EntityNotFoundError(SkysparkError):
    """Entity not found on server."""


class CommitError(SkysparkError):
    """Commit operation failed."""


class HistoryWriteError(SkysparkError):
    """History write operation failed."""


class ServerError(SkysparkError):
    """Server returned an error response."""

    def __init__(
        self, message: str, error_type: str | None = None, trace: str | None = None
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.trace = trace
