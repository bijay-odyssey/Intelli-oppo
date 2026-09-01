"""Provider-agnostic LLM interface.

Groq is the only backend today, but every call site goes through `LLMProvider`
and addresses models by *role* rather than by name. Adding Gemini or a local
Ollama backend means implementing `complete` and nothing else.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class Role(StrEnum):
    """What a call is for. The router maps these to concrete models."""

    UTILITY = "utility"
    """Parse, classify, plan, compress. Cheap and fast."""

    REASONING = "reasoning"
    """Build arguments and red-team them. The expensive one."""

    VERIFIER = "verifier"
    """Entailment and fallacy checks. Deliberately a different model family
    from REASONING — a same-family verifier shares the builder's blind spots."""

    SAFEGUARD = "safeguard"
    """Protected-proposition classification."""


class LLMError(RuntimeError):
    """Any failure reaching or parsing a model response."""


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Build a JSON schema a strict-mode API will accept.

    Strict mode demands every object declare `additionalProperties: false` and
    list all of its properties as required. Pydantic does neither by default,
    and emits keywords (`default`, `format`) that strict mode rejects.
    """
    return _strictify(model.model_json_schema())


_DROP = ("default", "format", "$comment", "examples")


def _strictify(node: Any) -> Any:
    if isinstance(node, list):
        return [_strictify(item) for item in node]
    if not isinstance(node, dict):
        return node

    out = {k: _strictify(v) for k, v in node.items() if k not in _DROP}
    if out.get("type") == "object" and "properties" in out:
        out["additionalProperties"] = False
        out["required"] = list(out["properties"])
    return out


class LLMProvider(ABC):
    """Minimal surface every backend must implement."""

    @abstractmethod
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
        """Return raw completion text."""

    @abstractmethod
    async def aclose(self) -> None:
        """Release the underlying client."""

    async def structured(
        self,
        *,
        role: Role,
        system: str,
        user: str,
        model: type[T],
        max_tokens: int = 2048,
        temperature: float = 0.6,
        retries: int = 1,
    ) -> T:
        """Complete into a validated Pydantic model.

        Strict schemas make malformed output rare but not impossible — enums in
        particular still get freelanced occasionally. One retry carries the
        validation error back to the model, which fixes it reliably.
        """
        schema = strict_schema(model)
        prompt = user
        last: Exception | None = None

        for _ in range(retries + 1):
            raw = await self.complete(
                role=role,
                system=system,
                user=prompt,
                schema=schema,
                schema_name=model.__name__.lower(),
                max_tokens=max_tokens,
                temperature=temperature,
            )
            try:
                return model.model_validate(json.loads(raw))
            except (json.JSONDecodeError, ValidationError) as exc:
                last = exc
                prompt = (
                    f"{user}\n\n"
                    f"Your previous answer was rejected: {exc}\n"
                    f"Return JSON matching the schema exactly."
                )

        raise LLMError(f"could not obtain valid {model.__name__}: {last}")
