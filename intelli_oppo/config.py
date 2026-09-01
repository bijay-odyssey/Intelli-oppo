"""Runtime settings, loaded from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    groq_token: str
    ascii_only: bool = False
    max_body_words: int = 90
    """Hard cap on the argument body. Enforced in code, not requested in a prompt."""

    @classmethod
    def load(cls) -> Settings:
        load_dotenv(PROJECT_ROOT / ".env")

        token = os.getenv("GROQ_TOKEN", "").strip()
        if not token:
            raise ConfigError(
                "GROQ_TOKEN is not set.\n"
                "  copy .env.example to .env and add your key\n"
                "  get one at https://console.groq.com/keys"
            )

        return cls(
            groq_token=token,
            ascii_only=os.getenv("IO_ASCII", "").strip() not in ("", "0", "false"),
            max_body_words=int(os.getenv("IO_MAX_WORDS", "90")),
        )
