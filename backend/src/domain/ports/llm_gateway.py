from typing import Protocol

import msgspec


class Message(msgspec.Struct):
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str


class ToolCall(msgspec.Struct):
    id: str
    name: str
    arguments: dict


class LLMResponse(msgspec.Struct):
    content: str | None
    tool_calls: list[ToolCall]


class ILLMGateway(Protocol):
    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse: ...
