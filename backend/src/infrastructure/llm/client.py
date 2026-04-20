import json
import time

import openai
import structlog

from backend.src.domain.ports.llm_gateway import ILLMGateway, LLMResponse, Message, ToolCall
from backend.src.infrastructure.exceptions import LLMError

logger = structlog.get_logger(__name__)


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

        try:
            prompt_tokens_estimate = sum(len(m.content or "") for m in messages) // 4
            logger.info(
                "llm_request",
                integration="openai",
                model=self._model,
                prompt_tokens=prompt_tokens_estimate,
            )
            t0 = time.monotonic()
            response = await self._client.chat.completions.create(**kwargs)
        except openai.APITimeoutError as exc:
            logger.warning("llm_error", integration="openai", error=str(exc))
            raise LLMError(f"LLM request timed out: {exc}") from exc
        except openai.APIStatusError as exc:
            logger.warning("llm_error", integration="openai", error=str(exc))
            raise LLMError(f"LLM API error {exc.status_code}: {exc.message}") from exc
        except openai.APIError as exc:
            logger.warning("llm_error", integration="openai", error=str(exc))
            raise LLMError(f"LLM API error: {exc}") from exc

        latency_ms = round((time.monotonic() - t0) * 1000)
        logger.info("llm_response", integration="openai", latency_ms=latency_ms)

        msg = response.choices[0].message
        if msg is None:
            raise LLMError("LLM returned empty response")

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
