"""Turn classification.

Phase 0 read every input as a fresh claim to oppose. That gated the headline
behaviour — you agree, it flips anyway — behind a `/concede` command, misread
counter-arguments as new claims, and spent a full reasoning call solemnly
vacuity-attacking the word "hello".

Classification runs on the cheap utility model before anything expensive, and
short-circuits asides entirely, so it lowers average cost per turn rather than
raising it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..core.claim import TurnKind
from ..llm.provider import LLMError, LLMProvider, Role


class TurnClass(BaseModel):
    kind: TurnKind
    reason: str = Field(description="At most ten words")


SYSTEM = """\
You label one message in an ongoing debate. The debate has two sides: the user,
and an engine that always argues the opposite of whatever the user holds.

- claim      — the user states a position, or changes the subject to a new one.
- counter    — the user pushes back on what the engine just argued. Disagreement,
               objection, a rebuttal, "that's wrong because...", or evidence
               offered against the engine's point.
- concession — the user agrees with the engine, concedes, or abandons their
               position. "fair enough", "ok you're right", "I take it back",
               "good point, I agree".
- aside      — greeting, thanks, small talk, or a question about how the tool
               works rather than about the topic.

Distinguishing counter from concession matters most. Partial agreement that
still resists — "sure, but..." — is a counter, not a concession. Only label
concession when the user has actually given up their side.

With no prior turn, the only possible labels are claim and aside.
"""


async def classify(
    llm: LLMProvider, text: str, ledger_context: str, has_history: bool
) -> TurnClass:
    """Label a turn. Falls back to `claim`, which is the safe default.

    Misreading a claim as an aside would drop it silently; misreading an aside
    as a claim merely wastes one call. So failures resolve toward claim.
    """
    if not has_history:
        prompt = f"No prior turn. Message:\n{text}"
    else:
        prompt = f"Debate so far:\n{ledger_context}\n\nLatest message:\n{text}"

    try:
        result = await llm.structured(
            role=Role.UTILITY,
            system=SYSTEM,
            user=prompt,
            model=TurnClass,
            max_tokens=512,
            temperature=0.0,
        )
    except LLMError:
        return TurnClass(kind=TurnKind.CLAIM, reason="classifier unavailable")

    if not has_history and result.kind in (TurnKind.COUNTER, TurnKind.CONCESSION):
        # Nothing to counter or concede to yet.
        return TurnClass(kind=TurnKind.CLAIM, reason="no prior turn")
    return result
