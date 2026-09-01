"""The invariants that are enforced in code, not asked for in a prompt.

A live run put `2+2≠4 ≻ 2+2=4` on the verdict line — Invariant I violated in the
headline while the points below it correctly granted the fact. And a flip
produced `winner="you", loser="user"`. Prompt text alone did not prevent either.
"""

import pytest

from intelli_oppo.config import Settings
from intelli_oppo.core import ClaimShape, MoveId, Pivot
from intelli_oppo.llm.provider import LLMProvider
from intelli_oppo.reason.engine import OppositionEngine, PointOut, VerdictOut


class StubProvider(LLMProvider):
    async def complete(self, **kwargs) -> str:  # pragma: no cover - never called
        raise AssertionError("guard tests must not hit the network")

    async def aclose(self) -> None:
        pass


@pytest.fixture
def engine() -> OppositionEngine:
    return OppositionEngine(StubProvider(), Settings(groq_token="stub"))


def out(**overrides) -> VerdictOut:
    base = dict(
        shape=ClaimShape.COMPARATIVE,
        user_favors="monolith",
        granted="",
        position="",
        winner="microservices",
        loser="monolith",
        metric="merge-queue throughput",
        domain="org > 50 eng",
        horizon="3y",
        points=[PointOut(move=MoveId.CRITERION_SHIFT, text="metric is wrong")],
        challenge="which metric?",
        pivot=Pivot.NONE,
    )
    return VerdictOut(**{**base, **overrides})


def test_clean_comparative_passes(engine):
    assert engine.fault(out(), must_not_back="monolith") is None


def test_rejects_backing_the_side_already_held(engine):
    fault = engine.fault(out(winner="monolith", loser="microservices"), "monolith")
    assert fault is not None
    assert "not opposition" in fault


def test_rejects_participants_as_subjects(engine):
    """The observed failure: winner='you', loser='user'."""
    fault = engine.fault(out(winner="you", loser="user"), "monolith")
    assert fault is not None
    assert "participants" in fault


def test_rejects_identical_winner_and_loser(engine):
    fault = engine.fault(out(winner="monolith", loser="Monolith"), "")
    assert fault is not None
    assert "same option" in fault


def test_rejects_empty_subjects_on_comparative(engine):
    assert engine.fault(out(winner="", loser=""), "") is not None


def test_assertion_needs_a_position(engine):
    fault = engine.fault(out(shape=ClaimShape.ASSERTION, winner="", loser=""), "")
    assert fault is not None
    assert "position" in fault


def test_assertion_with_position_passes_without_subjects(engine):
    """A settled fact has no losing option, so demanding one is what made the
    engine print the negation of arithmetic."""
    verdict = out(
        shape=ClaimShape.ASSERTION,
        winner="",
        loser="",
        granted="2 + 2 = 4",
        position="Not disputing that. Disputing that your argument earns it.",
    )
    assert engine.fault(verdict, must_not_back="") is None
