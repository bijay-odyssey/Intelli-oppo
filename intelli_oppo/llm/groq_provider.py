"""Groq backend."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from groq import APIError, AsyncGroq

from .provider import LLMError, LLMProvider, Role
from .router import ModelRouter


@dataclass
class CallStats:
    model: str = ""
    latency_ms: int = 0
    completion_tokens: int = 0

    def render(self) -> str:
        if not self.model:
            return "no calls yet"
        rate = (
            f"{self.completion_tokens / (self.latency_ms / 1000):.0f} tok/s"
            if self.latency_ms
            else "-"
        )
        return (
            f"{self.model} · {self.latency_ms}ms · {self.completion_tokens} tok · {rate}"
        )


class GroqProvider(LLMProvider):
    def __init__(
        self,
        token: str,
        router: ModelRouter | None = None,
        timeout: float = 60.0,
    ) -> None:
        if not token:
            raise LLMError("GROQ_TOKEN is empty — copy .env.example to .env")
        # The free tier is 8k tokens/minute and a turn costs ~3k, so 429s are
        # routine rather than exceptional. The SDK honours `retry-after`.
        self._client = AsyncGroq(api_key=token, timeout=timeout, max_retries=4)
        self._router = router or ModelRouter.from_env()
        self.last = CallStats()

    @property
    def router(self) -> ModelRouter:
        return self._router

    async def complete(
        self,
        *,
        role: Role,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        schema_name: str = "response",
        max_tokens: int = 2048,
        temperature: float = 0.6,
    ) -> str:
        model = self._router.model_for(role)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
        }
        if schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            }

        started = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(**kwargs)
        except APIError as exc:
            if getattr(exc, "status_code", None) == 429:
                raise LLMError(
                    "rate limited — the free tier allows 8k tokens per minute "
                    "and a turn costs about 3k. Wait a moment and try again."
                ) from exc
            raise LLMError(f"{model}: {exc}") from exc
        except Exception as exc:  # network, timeout, SDK-level failures
            raise LLMError(f"{model}: {exc}") from exc

        elapsed = int((time.perf_counter() - started) * 1000)
        usage = getattr(response, "usage", None)
        self.last = CallStats(
            model=model,
            latency_ms=elapsed,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )

        content = response.choices[0].message.content
        if not content:
            # Reasoning models spend max_completion_tokens on hidden reasoning
            # before emitting anything, so an empty body usually means the
            # budget ran out rather than a refusal.
            raise LLMError(
                f"{model} returned no content — try raising max_tokens "
                f"(currently {max_tokens})"
            )
        return content

    async def aclose(self) -> None:
        await self._client.close()
