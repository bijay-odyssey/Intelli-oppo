"""Role-to-model routing.

Groq has no embedding model, so retrieval stays local (see Phase 2). What it
does have is two distinct model families behind one key, which is why VERIFIER
points at Qwen while REASONING points at GPT-OSS. That split is the cheapest
hallucination defence available: a verifier from the builder's own family tends
to rubber-stamp the builder's reasoning.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .provider import Role

DEFAULTS: dict[Role, str] = {
    Role.UTILITY: "openai/gpt-oss-20b",
    Role.REASONING: "openai/gpt-oss-120b",
    Role.VERIFIER: "qwen/qwen3.8-27b",
    Role.SAFEGUARD: "openai/gpt-oss-safeguard-20b",
}

_ENV_PREFIX = "IO_MODEL_"


@dataclass(frozen=True)
class ModelRouter:
    models: dict[Role, str]

    @classmethod
    def from_env(cls) -> ModelRouter:
        """Defaults, with `IO_MODEL_<ROLE>` overriding any of them."""
        resolved = dict(DEFAULTS)
        for role in Role:
            override = os.getenv(f"{_ENV_PREFIX}{role.name}")
            if override:
                resolved[role] = override
        return cls(models=resolved)

    def model_for(self, role: Role) -> str:
        return self.models[role]

    def render(self) -> str:
        width = max(len(r.value) for r in Role)
        return "\n".join(f"{role.value:<{width}}  {self.models[role]}" for role in Role)
