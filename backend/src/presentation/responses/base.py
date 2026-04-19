from typing import Any

import msgspec


class SuccessResponse(msgspec.Struct):
    success: bool = True
    data: Any | None = None
    message: str | None = None


class ErrorResponse(msgspec.Struct):
    error_code: str
    message: str
    success: bool = False
    details: Any | None = None
