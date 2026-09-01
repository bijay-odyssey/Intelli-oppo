"""Typed representations of a position and the engine's answer to it.

Invariant II — scoped claim discipline — lives here. Every verdict the engine
issues carries an explicit (metric, domain, horizon) triple, and that triple is
printed. Two opposite conclusions under two different triples are not a
contradiction; they are a partition of the claim space. That is what makes
unlimited opposition formally consistent, and what makes the flip legal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from .moves import MoveId

_WORD = re.compile(r"[A-Za-z0-9'-]+")


class ClaimShape(StrEnum):
    """Whether the user offered a choice or an assertion.

    This distinction is load-bearing. A comparative claim ("A is better than B")
    has a genuine opposite side to argue. A bare assertion ("2 + 2 = 4") does
    not — and forcing one into a winner/loser pair makes the engine invent a
    losing option, which for a settled fact means printing its negation. That is
    Invariant I violated in the headline, whatever the points below it say.
    """

    COMPARATIVE = "comparative"
    """A versus B. Argue for the side the user is against."""

    ASSERTION = "assertion"
    """A single proposition. Oppose the argument, not the proposition."""


class Pivot(StrEnum):
    """The four legal ways to reverse position after the user concedes.

    A pivot the ledger cannot support is not legal. Reversing without one is a
    coin flip with a vocabulary, and the user sees through it immediately.
    """

    NONE = "none"

    CONCESSION_OVERREACH = "concession_overreach"
    """They accepted more than the argument licensed. It was scoped to one
    metric; they dropped the claim entirely."""

    PREMISE_CONSEQUENCE = "premise_consequence"
    """To agree they took on a premise, and that premise entails their original
    position. The concession trap: plant it in turn one, spring it in turn two."""

    SCOPE_RETURN = "scope_return"
    """They generalized past the boundary of the regime the engine established,
    and outside it the original claim holds."""

    SYMMETRY = "symmetry"
    """Apply the winning move against the new position. If it survives there but
    not here, that asymmetry is itself the argument."""


def word_count(text: str) -> int:
    return len(_WORD.findall(text))


@dataclass(frozen=True)
class Scope:
    """The region of claim space a verdict is standing in."""

    metric: str
    domain: str
    horizon: str

    def render(self) -> str:
        return f"{self.metric} · {self.domain} · {self.horizon}"

    def key(self) -> tuple[str, str, str]:
        """Normalized form, for detecting when two verdicts occupy one cell."""
        return (
            self.metric.strip().casefold(),
            self.domain.strip().casefold(),
            self.horizon.strip().casefold(),
        )


@dataclass(frozen=True)
class Point:
    """One numbered argument, tagged with the move that produced it."""

    move: MoveId
    text: str


@dataclass(frozen=True)
class Verdict:
    """The engine's position for a single turn."""

    scope: Scope
    points: tuple[Point, ...]
    challenge: str
    winner: str = ""
    """The option the engine backs. Empty on a meta-opposition turn."""

    loser: str = ""
    granted: str = ""
    """What the engine concedes outright. Invariant I: never deny a true fact,
    deny that it does the work. Empty when nothing needed granting."""

    position: str = ""
    """Free-form headline, used when there is no winner/loser pair to print."""

    shape: ClaimShape = ClaimShape.COMPARATIVE

    @property
    def is_meta(self) -> bool:
        """True when the engine granted the claim and attacked the argument."""
        return not (self.winner and self.loser)

    @property
    def headline(self) -> str:
        if self.is_meta:
            return self.position or "Not disputing the claim. Disputing the argument."
        return f"{self.winner} ≻ {self.loser}"

    @property
    def body_words(self) -> int:
        """Words in the parts subject to the output cap."""
        return sum(word_count(p.text) for p in self.points) + word_count(self.challenge)


@dataclass(frozen=True)
class Turn:
    """One exchange, recorded for the ledger."""

    user_text: str
    user_favors: str
    verdict: Verdict
    conceded: bool = False
    """True when the user agreed and the engine had to pivot."""

    pivot: Pivot = Pivot.NONE
    """Which of the four legal pivots fired, when conceded is True."""


@dataclass
class Debate:
    """Mutable state for a single debate session."""

    turns: list[Turn] = field(default_factory=list)

    @property
    def opening_claim(self) -> str:
        return self.turns[0].user_text if self.turns else ""
