import json

import openai

from src.domain.ports.llm_gateway import ILLMGateway, LLMResponse, Message, ToolCall


class LLMClient:
    """Universal LLM client using the OpenAI-compatible API format.

    Works with any provider that speaks OpenAI format:
    - OpenAI:   base_url=https://api.openai.com/v1
    - Groq:     base_url=https://api.groq.com/openai/v1
    - Together: base_url=https://api.together.xyz/v1
    - Ollama:   base_url=http://localhost:11434/v1, api_key=ollama
    - Mistral:  base_url=https://api.mistral.ai/v1
    - Any other OpenAI-compatible endpoint
    """

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._model = model

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self._model,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )

        return LLMResponse(content=msg.content, tool_calls=tool_calls)


_: ILLMGateway = LLMClient.__new__(LLMClient)
