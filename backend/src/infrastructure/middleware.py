import logging

import msgspec
from litestar.exceptions import HTTPException
from litestar.middleware import AbstractMiddleware
from litestar.status_codes import HTTP_500_INTERNAL_SERVER_ERROR
from litestar.types import Receive, Scope, Send

from backend.src.infrastructure.exceptions import ApiException
from backend.src.presentation.responses import ErrorResponse

logger = logging.getLogger(__name__)

_CONTENT_TYPE_HEADER = (b"content-type", b"application/json")


class ErrorHandlerMiddleware(AbstractMiddleware):
    """Uniform JSON error responses for every unhandled exception."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            await self._handle(exc, send)

    async def _handle(self, exc: Exception, send: Send) -> None:
        status_code: int
        error_response: ErrorResponse

        if isinstance(exc, ApiException):
            is_serious = exc.status_code >= 500
            status_code = exc.status_code
            error_response = ErrorResponse(
                error_code=exc.error_code,
                message=exc.message,
                details=exc.details or None,
            )
        elif isinstance(exc, HTTPException):
            is_serious = exc.status_code >= 500
            status_code = exc.status_code
            error_response = ErrorResponse(
                error_code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
            )
        else:
            is_serious = True
            status_code = HTTP_500_INTERNAL_SERVER_ERROR
            error_response = ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
            )

        if is_serious:
            logger.exception("Unhandled server error", exc_info=exc)
        else:
            logger.warning("Client error: %s %s", error_response.error_code, error_response.message)

        body: bytes = msgspec.json.encode(msgspec.to_builtins(error_response))
        content_length = str(len(body)).encode()

        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    _CONTENT_TYPE_HEADER,
                    (b"content-length", content_length),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})
