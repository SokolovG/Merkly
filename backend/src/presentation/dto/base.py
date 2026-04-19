from typing import TypeVar

import msgspec
from litestar.dto import DTOConfig, MsgspecDTO

T = TypeVar("T", bound=msgspec.Struct)


class BaseMsgspecDTO(MsgspecDTO[T]):  # type: ignore[type-arg]
    config = DTOConfig(rename_strategy="camel")
