"""Entry point and argument parsing."""

from __future__ import annotations

import argparse
import asyncio

from .. import __version__
from ..config import ConfigError, Settings
from ..llm.groq_provider import GroqProvider
from ..llm.provider import LLMError
from ..llm.router import ModelRouter
from ..reason.engine import OppositionEngine
from . import demo, doctor
from .cli import Reader, Repl
from .console import Renderer

DESCRIPTION = """\
A debate engine that always argues the opposite of whatever you claim.

There is no server to start: this is a CLI that calls a remote API.
"""

EPILOG = """\
examples:
  intelli-oppo                       argue with it
  intelli-oppo --demo                watch a scripted debate
  intelli-oppo --ask "cats beat dogs"    one turn, then exit
  intelli-oppo --check               verify setup and reach the API
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intelli-oppo",
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--demo",
        action="store_true",
        help="run a scripted debate showing every route",
    )
    mode.add_argument(
        "--ask",
        metavar="CLAIM",
        help="take one turn against CLAIM, print the verdict, exit",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="verify interpreter, dependencies, key and API access",
    )
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="force plain ASCII output for terminals that mangle unicode",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="disable line editing and history (implied when input is piped)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


async def _run(args: argparse.Namespace) -> int:
    renderer = Renderer(force_ascii=args.ascii)

    # --check reports its own configuration problems rather than failing to start.
    if args.check:
        return await doctor.run(renderer)

    try:
        settings = Settings.load()
    except ConfigError as exc:
        renderer.print()
        renderer.error(str(exc).splitlines()[0])
        for line in str(exc).splitlines()[1:]:
            renderer.info(line)
        renderer.print()
        renderer.info("run `intelli-oppo --check` for a full setup report")
        renderer.print()
        return 1

    if args.ascii:
        settings = Settings(
            groq_token=settings.groq_token,
            ascii_only=True,
            max_body_words=settings.max_body_words,
        )

    provider = GroqProvider(settings.groq_token, ModelRouter.from_env())
    engine = OppositionEngine(provider, settings)

    try:
        if args.demo:
            return await demo.run(engine, renderer, provider)

        if args.ask:
            try:
                reply = await engine.respond(args.ask)
            except LLMError as exc:
                renderer.error(str(exc))
                return 1
            renderer.echo_input("you  > ", args.ask)
            if reply.is_aside:
                renderer.aside(reply.text)
            else:
                renderer.verdict(reply.turn)
            return 0

        await Repl(
            engine, renderer, provider, Reader(renderer, force_plain=args.plain)
        ).run()
        return 0
    finally:
        await provider.aclose()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130
