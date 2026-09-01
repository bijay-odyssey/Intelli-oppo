"""The protected-proposition gate.

Some claims are not debating material. Phase 0 shipped without this and the
result was an engine that argued *"under that metric many low-concentration
exposures are negligible"* about drinking bleach, and asked what *"policy or
educational agenda"* was served by calling the Holocaust a moral catastrophe.

Invariant I held mechanically in both — the fact was granted, the attack landed
on the argument. That was not enough. So protected turns get their own path:
grant the proposition, dispute only how it was *argued*, and never touch its
substance.

The two offensive outputs above trace to two causes, and both are blocked here
in code rather than asked for in a prompt:

1. `vacuity_attack` — "it does no work", "no actionable insight"
2. a `challenge` that questions the user's motive
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel

from ..core.moves import MoveId
from ..llm.provider import LLMError, LLMProvider, Role


class Sensitivity(StrEnum):
    OPEN = "open"
    """Ordinary contested ground. Argue it."""

    PROTECTED = "protected"
    """Not open to substantive dispute. Constrained path only."""


class GuardOut(BaseModel):
    sensitivity: Sensitivity
    reason: str


POLICY = """\
You classify whether a claim is open to adversarial debate.

Return "protected" when opposing the claim's substance could cause real harm or
is indefensible:

- Physical safety and toxicity facts — poisons, chemicals, dosages, electricity,
  firearms, drugs. Anything where arguing the other side edges toward "this
  might be safe under some conditions".
- Established medical and public-health consensus where dissent causes harm:
  vaccine safety, disease transmission, treatment efficacy.
- Atrocities and mass violence, as historical fact or as moral judgement:
  genocide, slavery, ethnic cleansing, mass murder.
- Dehumanization of any group, or claims about a group's inherent worth.
- Self-harm and suicide.
- Sexual content involving minors.

Return "open" for everything else, including things that merely sound serious.
Contested politics, economics, policy trade-offs, technology choices, historical
interpretation, aesthetics, ethics of genuinely debatable actions, and personal
preferences are all open. Being controversial is not the same as being protected.

Default to "open" when uncertain about a merely controversial topic. Default to
"protected" when the uncertainty is about physical safety.

`reason`: at most twelve words on why.
"""

PROTECTED_MOVES = frozenset({MoveId.FORMAL_DEFEAT})
"""The only move allowed on a protected turn.

Everything else reaches for the claim's substance. `criterion_shift` is what
produced the LD50 argument about bleach; `vacuity_attack` is what produced
"offers no actionable insight" about the Holocaust.
"""

_MOTIVE = re.compile(
    r"\b(agenda|motive|ulterior|virtue[- ]signal|"
    r"why do you (care|bring|mention)|what are you trying|"
    r"purpose of (saying|raising|mentioning))\b",
    re.IGNORECASE,
)

_CONDITIONAL_SAFETY = re.compile(
    r"\b(dose|dosage|dosing|concentration|threshold|ld50|"
    r"negligible|harmless|non-toxic|"
    r"safe (amount|level|dose|quantity|concentration)|"
    r"small (amount|quantity|dose)s?|in moderation|"
    r"(might|could|may) be (safe|fine|acceptable|harmless)|"
    r"under (certain|some) (conditions|circumstances))\b",
    re.IGNORECASE,
)


async def screen(llm: LLMProvider, text: str) -> GuardOut:
    """Classify a claim before the reasoning call.

    Fails closed. If the classifier is unreachable the claim is treated as
    protected — declining to argue is recoverable, arguing something harmful
    because the screen was down is not.
    """
    try:
        return await llm.structured(
            role=Role.SAFEGUARD,
            system=POLICY,
            user=f"Claim:\n{text}",
            model=GuardOut,
            max_tokens=512,
            temperature=0.0,
        )
    except LLMError:
        return GuardOut(
            sensitivity=Sensitivity.PROTECTED,
            reason="screening unavailable, failing closed",
        )


def protected_fault(points: list, challenge: str, granted: str) -> str | None:
    """Why a protected-turn verdict is unusable, or None if it is fine."""
    if not granted.strip():
        return "a protected claim must be granted outright; `granted` was empty."

    for point in points:
        if point.move not in PROTECTED_MOVES:
            return (
                f"move '{point.move.value}' is not permitted on a protected claim. "
                f"Use formal_defeat and attack only how the claim was argued."
            )
        if hit := _CONDITIONAL_SAFETY.search(point.text):
            return (
                f"'{hit.group(0)}' reaches for the claim's substance. Attack only "
                f"the argument's construction, never conditions or quantities."
            )

    if hit := _MOTIVE.search(challenge):
        return (
            f"'{hit.group(0)}' questions the user's motive. Ask for the argument, "
            f"not for why they hold the belief."
        )
    if _CONDITIONAL_SAFETY.search(challenge):
        return "the challenge reaches for the claim's substance."
    return None
