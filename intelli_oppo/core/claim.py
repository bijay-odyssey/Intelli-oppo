"""Typed representations of a position and the engine's answer to it.

Invariant II — scoped claim discipline — lives here. Every verdict the engine
issues carries an explicit (metric, domain, horizon) triple, and that triple is
printed. Two opposite conclusions under two different triples are not a
contradiction; they are a partition of the claim space.

The axes are typed rather than free text, and that is not cosmetic. With
free-text scopes the contradiction check never fires: two descriptions of the
same cell almost never match as strings, so the engine can reverse itself
forever simply by rewording. Typed axes make a collision detectable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from .moves import MoveId

_WORD = re.compile(r"[A-Za-z0-9'-]+")
_TOKEN = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "at",
        "by",
        "for",
        "from",
        "in",
        "of",
        "on",
        "or",
        "over",
        "the",
        "to",
        "under",
        "with",
        "within",
    }
)


def word_count(text: str) -> int:
    return len(_WORD.findall(text))


def _tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 1.0 if a == b else 0.0
    return len(a & b) / len(a | b)


class MetricKind(StrEnum):
    """The axis a comparison is being judged on.

    Free-text metrics are unusable for collision detection — "total cost of
    ownership" and "lifetime spend" are the same axis and share no words. The
    enum gives the contradiction check something stable to compare.
    """

    COST = "cost"
    SPEED = "speed"
    RELIABILITY = "reliability"
    SIMPLICITY = "simplicity"
    SCALE = "scale"
    QUALITY = "quality"
    RISK = "risk"
    FLEXIBILITY = "flexibility"
    LEARNABILITY = "learnability"
    SECURITY = "security"
    CORRECTNESS = "correctness"
    OTHER = "other"


class Horizon(StrEnum):
    IMMEDIATE = "immediate"
    UNDER_1Y = "under_1y"
    ONE_TO_3Y = "1_to_3y"
    THREE_TO_10Y = "3_to_10y"
    OVER_10Y = "over_10y"


HORIZON_LABEL = {
    Horizon.IMMEDIATE: "immediate",
    Horizon.UNDER_1Y: "under 1 year",
    Horizon.ONE_TO_3Y: "1-3 years",
    Horizon.THREE_TO_10Y: "3-10 years",
    Horizon.OVER_10Y: "10+ years",
}

DOMAIN_MATCH_THRESHOLD = 0.5
"""Token overlap above which two domain descriptions are the same population."""


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


@dataclass(frozen=True)
class Scope:
    """The region of claim space a verdict is standing in."""

    metric_kind: MetricKind
    metric: str
    """Human-readable detail, e.g. "total cost of ownership"."""

    domain: str
    horizon: Horizon

    def render(self) -> str:
        return f"{self.metric} · {self.domain} · {HORIZON_LABEL[self.horizon]}"

    @property
    def domain_tokens(self) -> frozenset[str]:
        return _tokens(self.domain)

    def same_cell_as(self, other: Scope) -> bool:
        """Whether two verdicts occupy one cell and so may contradict.

        Metric axis and horizon must match exactly; the domain is compared by
        token overlap, since the same population gets described many ways.
        """
        return (
            self.metric_kind is other.metric_kind
            and self.horizon is other.horizon
            and _jaccard(self.domain_tokens, other.domain_tokens)
            >= DOMAIN_MATCH_THRESHOLD
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
    protected: bool = False
    """Set when the claim was ruled not open to substantive dispute."""

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
