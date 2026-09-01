"""Interactive REPL."""

from __future__ import annotations

import asyncio

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from ..config import ConfigError, Settings
from ..core.claim import Turn
from ..llm.groq_provider import GroqProvider
from ..llm.provider import LLMError
from ..llm.router import ModelRouter
from ..reason.engine import OppositionEngine
from .console import Renderer

HELP = """\
  /scope     the metric, domain and horizon it is currently standing in
  /ledger    every scoped commitment, and any contradictions
  /concede   agree with it, and watch the pivot fire
  /moves     the twelve-move opposition ontology
  /models    which model is doing what
  /reset     clear the ledger and start a new debate
  /quit      exit
"""


class Repl:
    def __init__(
        self,
        engine: OppositionEngine,
        renderer: Renderer,
        provider: GroqProvider,
    ) -> None:
        self.engine = engine
        self.ui = renderer
        self.provider = provider
        self.session: PromptSession[str] = PromptSession(history=InMemoryHistory())

    def banner(self) -> None:
        g = self.ui.g
        self.ui.print()
        self.ui.print("[anti]Intelli-Oppo[/anti] [faint]0.1.0 — phase 0[/faint]")
        self.ui.print(
            "[faint]It always takes the other side. State a claim, or /help.[/faint]"
        )
        self.ui.print(
            f"[faint]Every verdict names the scope it holds in {g.dash} "
            f"that is what keeps it honest.[/faint]"
        )
        self.ui.print()

    async def _think(self, coro) -> Turn:
        with self.ui.console.status("[faint]thinking[/faint]", spinner="dots"):
            return await coro

    async def handle(self, text: str) -> bool:
        """Returns False when the session should end."""
        command = text.strip().lower()

        if command in ("/quit", "/exit", "/q"):
            return False
        if command in ("/help", "/h", "/?"):
            self.ui.print()
            self.ui.print(HELP)
            return True
        if command == "/scope":
            self.ui.scope(self.engine.ledger)
            return True
        if command == "/ledger":
            self.ui.ledger(self.engine.ledger)
            return True
        if command == "/moves":
            self.ui.moves()
            return True
        if command == "/models":
            self.ui.print()
            self.ui.print(self.provider.router.render())
            self.ui.print()
            self.ui.info(f"last call: {self.provider.last.render()}")
            self.ui.print()
            return True
        if command == "/reset":
            self.engine.ledger.clear()
            self.ui.info("ledger cleared")
            return True

        try:
            if command == "/concede":
                turn = await self._think(self.engine.concede())
            else:
                turn = await self._think(self.engine.respond(text))
        except LLMError as exc:
            self.ui.error(str(exc))
            return True

        self.ui.verdict(turn)
        self.ui.info(f"  {self.provider.last.render()}")
        self.ui.print()
        return True

    async def run(self) -> None:
        self.banner()
        while True:
            try:
                text = await self.session.prompt_async("you  > ")
            except (EOFError, KeyboardInterrupt):
                break
            if not text.strip():
                continue
            if not await self.handle(text):
                break
        self.ui.print()
        self.ui.info("done")


async def _main() -> int:
    try:
        settings = Settings.load()
    except ConfigError as exc:
        print(f"\n{exc}\n")
        return 1

    renderer = Renderer(force_ascii=settings.ascii_only)
    provider = GroqProvider(settings.groq_token, ModelRouter.from_env())
    engine = OppositionEngine(provider, settings)

    try:
        await Repl(engine, renderer, provider).run()
    finally:
        await provider.aclose()
    return 0


def main() -> int:
    try:
        return asyncio.run(_main())
    except KeyboardInterrupt:
        return 130
