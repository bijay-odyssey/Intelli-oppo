"""Interactive REPL."""

from __future__ import annotations

import asyncio
import sys

from ..core.claim import Response, TurnKind
from ..llm.groq_provider import GroqProvider
from ..llm.provider import LLMError
from ..reason.engine import OppositionEngine
from .console import Renderer

HELP = """\
  /scope     the metric, domain and horizon it is currently standing in
  /ledger    every scoped commitment, and any contradictions
  /concede   force the flip (it also detects agreement on its own)
  /moves     the twelve-move opposition ontology
  /models    which model is doing what
  /reset     clear the ledger and start a new debate
  /quit      exit
"""

PROMPT = "you  > "


class Reader:
    """Line input that degrades instead of crashing.

    `prompt_toolkit` demands a real console and raises `NoConsoleScreenBufferError`
    otherwise, which took out piped input, Git Bash on Windows, CI and Docker.
    History and editing are worth having when a console exists, but they are not
    worth being unable to run at all.
    """

    def __init__(self, renderer: Renderer, force_plain: bool = False) -> None:
        self._ui = renderer
        self._session = None
        if force_plain or not sys.stdin.isatty():
            return
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import InMemoryHistory

            self._session = PromptSession(history=InMemoryHistory())
        except Exception:
            self._session = None

    @property
    def interactive(self) -> bool:
        return self._session is not None

    async def read(self, prompt: str) -> str:
        if self._session is not None:
            try:
                return await self._session.prompt_async(prompt)
            except (EOFError, KeyboardInterrupt):
                raise
            except Exception:
                # The console turned out to be unusable after all. Drop to
                # plain reading for the rest of the session rather than dying.
                self._session = None
        return await self._plain(prompt)

    async def _plain(self, prompt: str) -> str:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            raise EOFError
        text = line.rstrip("\r\n")
        # Echo it, so a piped run still reads as a transcript.
        self._ui.echo_input(prompt, text)
        return text


class Repl:
    def __init__(
        self,
        engine: OppositionEngine,
        renderer: Renderer,
        provider: GroqProvider,
        reader: Reader | None = None,
    ) -> None:
        self.engine = engine
        self.ui = renderer
        self.provider = provider
        self.reader = reader or Reader(renderer)

    def banner(self) -> None:
        g = self.ui.g
        self.ui.print()
        self.ui.print("[anti]Intelli-Oppo[/anti] [faint]0.1.0[/faint]")
        self.ui.print(
            "[faint]It always takes the other side. State a claim, or /help.[/faint]"
        )
        self.ui.print(
            f"[faint]Every verdict names the scope it holds in {g.dash} "
            f"that is what keeps it honest.[/faint]"
        )
        self.ui.print()

    async def _think(self, coro):
        if not self.reader.interactive:
            return await coro
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
                reply = Response(
                    kind=TurnKind.CONCESSION,
                    turn=await self._think(self.engine.concede()),
                )
            else:
                reply = await self._think(self.engine.respond(text))
        except LLMError as exc:
            self.ui.error(str(exc))
            return True

        if reply.is_aside:
            self.ui.aside(reply.text)
        else:
            self.ui.verdict(reply.turn)
        self.ui.info(f"  {self.provider.last.render()}")
        self.ui.print()
        return True

    async def run(self) -> None:
        self.banner()
        while True:
            try:
                text = await self.reader.read(PROMPT)
            except (EOFError, KeyboardInterrupt):
                break
            if not text.strip():
                continue
            if not await self.handle(text):
                break
        self.ui.print()
        self.ui.info("done")
