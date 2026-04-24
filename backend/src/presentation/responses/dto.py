from collections.abc import Collection
from typing import Any

import msgspec
from litestar.dto import DTOConfig, MsgspecDTO

from backend.src.presentation.responses.base import SuccessResponse


class SuccessResponseDTO(MsgspecDTO[SuccessResponse]):
    config = DTOConfig()

    def data_to_encodable_type(self, data: SuccessResponse | Collection[Any]) -> dict[str, Any]:
        if isinstance(data, Collection) and not isinstance(data, str | bytes | SuccessResponse):
            return {"items": [msgspec.to_builtins(item) for item in data]}
        assert isinstance(data, SuccessResponse)
        return msgspec.to_builtins(data)  # type: ignore[return-value]
