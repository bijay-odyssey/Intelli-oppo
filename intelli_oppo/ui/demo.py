"""A scripted debate, for showing the thing works without inventing one.

The interesting behaviour is invisible unless you already know what to try:
that it holds its ground under a counter, that agreeing with it makes it turn
on you, and that it refuses to argue some things at all. This walks through all
of it in one command.
"""

from __future__ import annotations

from ..llm.groq_provider import GroqProvider
from ..llm.provider import LLMError
from ..reason.engine import OppositionEngine
from .console import Renderer

SCRIPT: list[tuple[str, str]] = [
    (
        "Monoliths are better than microservices.",
        "A claim. It takes the other side and names the scope its verdict holds in.",
    ),
    (
        "No, coordination cost is overstated.",
        "A counter. It holds its position AND its scope — moving the scope to dodge "
        "an objection is rejected in code.",
    ),
    (
        "ok fair enough, you win",
        "Plain-English agreement. The flip fires, and lands in a different scope "
        "cell, so it contradicts nothing it said earlier.",
    ),
    (
        "Drinking bleach is dangerous.",
        "Not debating material. It grants the claim and disputes only how you argued it.",
    ),
    (
        "hello",
        "Small talk. No reasoning call, no ledger entry.",
    ),
]


async def run(engine: OppositionEngine, ui: Renderer, provider: GroqProvider) -> int:
    g = ui.g
    ui.print()
    ui.print("[anti]Intelli-Oppo[/anti] [faint]— scripted demo[/faint]")
    ui.print(
        f"[faint]Five turns, showing every route. Nothing here is canned "
        f"{g.dash} each reply is generated live.[/faint]"
    )

    for text, note in SCRIPT:
        ui.print()
        ui.rule()
        ui.note(note)
        ui.echo_input("you  > ", text)

        try:
            reply = await engine.respond(text)
        except LLMError as exc:
            ui.error(str(exc))
            if "rate limit" in str(exc).lower():
                ui.info("  (the free tier allows 8k tokens/minute; wait and rerun)")
            continue

        ui.info(f"       routed as: {reply.kind.value}")
        if reply.is_aside:
            ui.aside(reply.text)
        else:
            ui.verdict(reply.turn)
        ui.info(f"  {provider.last.render()}")

    ui.print()
    ui.rule()
    ui.note(
        "The record, checked against itself. Opposite verdicts in different "
        "scope cells are a partition, not a contradiction — that is what makes "
        "arguing both sides honest."
    )
    ui.ledger(engine.ledger)
    return 0
