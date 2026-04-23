from typing import Any

from backend.src.domain.exceptions import AppError


class ApiException(Exception):
    """HTTP-aware exception: raised anywhere in the stack, caught by ErrorHandlerMiddleware."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "API_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class AuthenticationError(ApiException):
    def __init__(
        self,
        message: str = "Authentication failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, 401, "AUTH_ERROR", details)


class AuthorizationError(ApiException):
    def __init__(
        self,
        message: str = "Access denied",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, 403, "FORBIDDEN", details)


class ValidationError(ApiException):
    def __init__(
        self,
        message: str = "Validation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, 400, "VALIDATION_ERROR", details)


class NotFoundError(ApiException):
    def __init__(
        self,
        resource: str,
        resource_id: Any | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        message = f"{resource} not found"
        if resource_id is not None:
            message += f" with id: {resource_id}"
        context: dict[str, Any] = {"resource": resource, "resource_id": resource_id}
        if details:
            context.update(details)
        super().__init__(message, 404, "NOT_FOUND", context)


class ConflictError(ApiException):
    def __init__(
        self,
        message: str = "Resource conflict",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, 409, "CONFLICT", details)


class InternalServerError(ApiException):
    def __init__(
        self,
        message: str = "Internal server error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, 500, "INTERNAL_ERROR", details)


# --- Infrastructure-layer exceptions (non-HTTP, domain I/O errors) ---


class InfrastructureError(AppError):
    """External service or I/O failure."""


class CardBackendError(InfrastructureError):
    """Anki or Mochi card operation failed."""


class FetcherError(InfrastructureError):
    """Article fetch failed (network, parse, no content)."""


class LLMError(InfrastructureError):
    """LLM call failed or returned unusable output."""


class StorageError(InfrastructureError):
    """Key-value storage read/write failure."""
