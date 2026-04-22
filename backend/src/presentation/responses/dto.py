from collections.abc import Collection
from typing import Any, cast

from litestar.dto import DTOConfig, MsgspecDTO

from backend.src.presentation.responses.base import SuccessResponse


class SuccessResponseDTO(MsgspecDTO[SuccessResponse]):
    config = DTOConfig()

    def data_to_encodable_type(self, data: SuccessResponse | Collection[Any]) -> dict[str, Any]:
        if isinstance(data, Collection) and not isinstance(data, str | bytes):
            return {"items": [self._encode(cast(SuccessResponse, item)) for item in data]}
        return self._encode(cast(SuccessResponse, data))

    def _encode(self, data: SuccessResponse) -> dict[str, Any]:
        import msgspec

        raw = msgspec.to_builtins(data)
        return self._to_camel(raw)

    def _to_camel(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {self._camel_key(k): self._to_camel(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._to_camel(i) for i in obj]
        return obj

    @staticmethod
    def _camel_key(key: str) -> str:
        if "_" not in key:
            return key
        parts = key.split("_")
        return parts[0] + "".join(p.capitalize() for p in parts[1:])
