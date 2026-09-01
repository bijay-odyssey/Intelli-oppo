"""The twelve-move opposition ontology.

Opposition is not improvised per turn. The engine picks from this fixed
catalogue, then builds an argument for the specific move it chose.

Four of the twelve require no external evidence at all, and four more need only
weak grounding. That is a deliberate robustness property: the engine is never
structurally forced to fabricate, because a purely formal attack is always in
reach even with an empty knowledge base.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Evidence(StrEnum):
    """How much external grounding a move needs before it may be used."""

    NONE = "none"
    SOME = "some"
    REQUIRED = "required"


class MoveId(StrEnum):
    CRITERION_SHIFT = "criterion_shift"
    SCOPE_RESTRICTION = "scope_restriction"
    HORIZON_INVERSION = "horizon_inversion"
    REFERENCE_CLASS_SWAP = "reference_class_swap"
    COST_INTERNALIZATION = "cost_internalization"
    COUNTEREXAMPLE = "counterexample"
    PRECEDENT_INVERSION = "precedent_inversion"
    FORMAL_DEFEAT = "formal_defeat"
    BURDEN_ASYMMETRY = "burden_asymmetry"
    MEASUREMENT_ATTACK = "measurement_attack"
    MECHANISM_ATTACK = "mechanism_attack"
    VACUITY_ATTACK = "vacuity_attack"


@dataclass(frozen=True)
class Move:
    id: MoveId
    label: str
    attacks: str
    evidence: Evidence
    form: str
    guidance: str


MOVES: dict[MoveId, Move] = {
    m.id: m
    for m in (
        Move(
            id=MoveId.CRITERION_SHIFT,
            label="Criterion shift",
            attacks="the unstated metric",
            evidence=Evidence.NONE,
            form="Better under which metric? Under M', the other side wins.",
            guidance=(
                "Name the metric they silently assumed, then a more binding one under "
                "which the other side wins. Their metric is not wrong, just not "
                "decisive."
            ),
        ),
        Move(
            id=MoveId.SCOPE_RESTRICTION,
            label="Scope restriction",
            attacks="the domain of validity",
            evidence=Evidence.SOME,
            form="A holds in regime R. Outside R it inverts.",
            guidance=(
                "State the regime where their claim holds, name its boundary, show the "
                "case sits outside it."
            ),
        ),
        Move(
            id=MoveId.HORIZON_INVERSION,
            label="Horizon inversion",
            attacks="the time window",
            evidence=Evidence.SOME,
            form="True at one year, false at ten.",
            guidance=(
                "Show the comparison changing sign as the horizon extends: compounding, "
                "maintenance, option value, deferred cost."
            ),
        ),
        Move(
            id=MoveId.REFERENCE_CLASS_SWAP,
            label="Reference-class swap",
            attacks="the population sampled",
            evidence=Evidence.REQUIRED,
            form="Simpson - survivorship - Berkson - base rate",
            guidance=(
                "Show they reason over the wrong population and the conclusion reverses "
                "in the right one. Name the specific trap."
            ),
        ),
        Move(
            id=MoveId.COST_INTERNALIZATION,
            label="Cost internalization",
            attacks="the omitted column",
            evidence=Evidence.SOME,
            form="opportunity cost - externality - tail risk",
            guidance=(
                "Find the cost their accounting omits and show that including it "
                "reverses the ranking. Ruin risk counts at low probability."
            ),
        ),
        Move(
            id=MoveId.COUNTEREXAMPLE,
            label="Counterexample",
            attacks="a universal quantifier",
            evidence=Evidence.REQUIRED,
            form="One real instance defeats a universal.",
            guidance=(
                "Only against a genuinely universal claim. One concrete verifiable "
                "instance. Never invent it."
            ),
        ),
        Move(
            id=MoveId.PRECEDENT_INVERSION,
            label="Precedent inversion",
            attacks="the history they invoked",
            evidence=Evidence.REQUIRED,
            form="That case cuts the other way.",
            guidance=(
                "Show the case they lean on establishes something else. Never stretch "
                "it past what it supports."
            ),
        ),
        Move(
            id=MoveId.FORMAL_DEFEAT,
            label="Formal defeat",
            attacks="internal consistency",
            evidence=Evidence.NONE,
            form="equivocation - non-transitivity - circularity - Arrow",
            guidance=(
                "Show the claim is inconsistent, question-begging, equivocating between "
                "two senses, or assuming a total order that does not exist."
            ),
        ),
        Move(
            id=MoveId.BURDEN_ASYMMETRY,
            label="Burden asymmetry",
            attacks="the default position",
            evidence=Evidence.NONE,
            form="Asymmetric downside implies the opposite default.",
            guidance=(
                "Show the costs of being wrong are asymmetric, so the burden sits on "
                "them and the sensible default is the other option."
            ),
        ),
        Move(
            id=MoveId.MEASUREMENT_ATTACK,
            label="Measurement attack",
            attacks="the proxy variable",
            evidence=Evidence.SOME,
            form="Goodhart - Campbell - the metric is gamed",
            guidance=(
                "Show their number measures a proxy that decouples from the thing "
                "itself under the pressure being discussed."
            ),
        ),
        Move(
            id=MoveId.MECHANISM_ATTACK,
            label="Mechanism attack",
            attacks="the causal story",
            evidence=Evidence.REQUIRED,
            form="confounder - reverse causation - no dose-response",
            guidance=(
                "Grant the correlation, deny the mechanism. Name the confounder or the "
                "reverse direction."
            ),
        ),
        Move(
            id=MoveId.VACUITY_ATTACK,
            label="Vacuity attack",
            attacks="the claim's usefulness",
            evidence=Evidence.NONE,
            form="True, and it does no work.",
            guidance=(
                "For claims true but trivial or unfalsifiable. Grant it, then show the "
                "load-bearing claim beside it fails. The primary move against settled "
                "facts."
            ),
        ),
    )
}

FORMAL_MOVES: tuple[MoveId, ...] = tuple(
    move_id for move_id, move in MOVES.items() if move.evidence is Evidence.NONE
)
"""Moves usable with no knowledge base at all. The engine's fabrication floor."""


def catalogue() -> str:
    """Render the ontology for inclusion in a system prompt."""
    lines = []
    for move in MOVES.values():
        lines.append(
            f"- {move.id.value} ({move.label}) "
            f"| attacks: {move.attacks} "
            f"| evidence: {move.evidence.value}\n"
            f"    {move.guidance}"
        )
    return "\n".join(lines)
