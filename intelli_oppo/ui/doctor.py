"""Setup verification.

Every failure mode here used to surface late and unhelpfully: a wrong Python
version as an import error deep in a dependency, a missing key as a traceback
on the first turn, a model the account cannot reach as a 404 mid-debate.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from ..config import ConfigError, Settings
from ..llm.provider import Role
from ..llm.router import ModelRouter

MIN_PYTHON = (3, 11)
RECOMMENDED_PYTHON = (3, 12)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""


def _python() -> Check:
    v = sys.version_info
    version = f"{v.major}.{v.minor}.{v.micro}"
    if v[:2] < MIN_PYTHON:
        return Check(
            "python",
            False,
            f"{version} — too old",
            "onnxruntime requires 3.11+. Install Python 3.12 and rebuild the venv.",
        )
    note = "" if v[:2] >= RECOMMENDED_PYTHON else " (3.12 recommended)"
    return Check("python", True, version + note)


def _dependencies() -> Check:
    missing = []
    for module in ("groq", "pydantic", "rich", "dotenv"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        return Check(
            "dependencies",
            False,
            f"missing: {', '.join(missing)}",
            'pip install -e ".[dev]"',
        )
    return Check("dependencies", True, "installed")


def _settings() -> tuple[Check, Settings | None]:
    try:
        settings = Settings.load()
    except ConfigError as exc:
        return (
            Check(
                "api key",
                False,
                "GROQ_TOKEN not set",
                str(exc).replace("\n", " ").strip(),
            ),
            None,
        )
    masked = settings.groq_token[:7] + "…" + settings.groq_token[-4:]
    return Check("api key", True, masked), settings


async def _reachable(settings: Settings, router: ModelRouter) -> list[Check]:
    """Actually call the API. A key that parses is not a key that works."""
    from ..llm.groq_provider import GroqProvider

    provider = GroqProvider(settings.groq_token, router)
    checks: list[Check] = []
    try:
        available = {m.id for m in (await provider._client.models.list()).data}
        checks.append(Check("api reachable", True, f"{len(available)} models visible"))

        for role in Role:
            model = router.model_for(role)
            if model in available:
                checks.append(Check(f"model · {role.value}", True, model))
            else:
                checks.append(
                    Check(
                        f"model · {role.value}",
                        False,
                        f"{model} not available to this account",
                        f"set IO_MODEL_{role.name} to a model you can reach",
                    )
                )

    except Exception as exc:
        checks.append(
            Check(
                "api reachable",
                False,
                str(exc)[:120],
                "check the key at https://console.groq.com/keys and your network",
            )
        )
        await provider.aclose()
        return checks

    try:
        # Generous budget: these are reasoning models, and they spend part of it
        # on hidden reasoning before emitting a single visible token. A tight
        # cap comes back empty and looks like an outage.
        reply = await provider.complete(
            role=Role.UTILITY,
            system="Reply with the single word: ready",
            user="ready?",
            max_tokens=512,
        )
        checks.append(
            Check("live call", True, f"{provider.last.render()} → {reply.strip()[:20]}")
        )
    except Exception as exc:
        checks.append(
            Check("live call", False, str(exc)[:120], "retry; the free tier throttles")
        )
    finally:
        await provider.aclose()
    return checks


async def run(ui) -> int:
    """Print a setup report. Returns a process exit code."""
    g = ui.g
    ui.print()
    ui.print("[anti]Intelli-Oppo[/anti] [faint]— setup check[/faint]")
    ui.print()

    checks = [_python(), _dependencies()]
    key_check, settings = _settings()
    checks.append(key_check)

    if settings is not None:
        checks.extend(await _reachable(settings, ModelRouter.from_env()))

    for check in checks:
        ui.check(check.name, check.ok, check.detail, check.fix)

    failed = [c for c in checks if not c.ok]
    ui.print()
    if failed:
        ui.print(f"[anti]{len(failed)} problem(s).[/anti] [faint]Fixes above.[/faint]")
        return 1
    ui.print(
        "[gate]All good.[/gate] [faint]Run `python -m intelli_oppo --demo` "
        "to watch it work, or `python -m intelli_oppo` to argue with it.[/faint]"
    )
    ui.print(
        f"[faint]There is no server to start {g.dash} this is a CLI that calls "
        f"a remote API.[/faint]"
    )
    return 0
