"""The invariants that are enforced in code, not asked for in a prompt.

Every case here corresponds to something a live run actually produced.
"""

import pytest

from intelli_oppo.config import Settings
from intelli_oppo.core import (
    ClaimDomain,
    ClaimShape,
    Decidability,
    Horizon,
    MetricKind,
    MoveId,
    Pivot,
)
from intelli_oppo.core.moves import FORMAL_MOVES
from intelli_oppo.llm.provider import LLMProvider
from intelli_oppo.reason import PROTECTED_MOVES, protected_fault
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
        claim_domain=ClaimDomain.EMPIRICAL,
        decidability=Decidability.CONTESTED,
        granted="",
        position="",
        winner="microservices",
        loser="monolith",
        metric_kind=MetricKind.SPEED,
        metric="merge-queue throughput",
        domain="org > 50 eng",
        horizon=Horizon.ONE_TO_3Y,
        points=[PointOut(move=MoveId.CRITERION_SHIFT, text="metric is wrong")],
        challenge="which metric?",
        pivot=Pivot.NONE,
    )
    return VerdictOut(**{**base, **overrides})


# ── opposition and subject invariants ─────────────────────────────────


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
        decidability=Decidability.SETTLED,
        granted="2 + 2 = 4",
        position="Not disputing that. Disputing that your argument earns it.",
        points=[PointOut(move=MoveId.VACUITY_ATTACK, text="true but does no work")],
    )
    assert engine.fault(verdict, must_not_back="") is None


# ── decidability-gated move eligibility ────────────────────────────────
# Issue #1 asked for a staged pipeline (separate classify/plan/build calls) so
# that "the engine cannot argue against settled science." Measured live, that
# split cost 60-110% more tokens per turn than one call, because each
# GPT-OSS reasoning call pays a fixed hidden-thinking tax regardless of prompt
# size, and three calls pays it three times. The classification survives as
# two extra fields on the SAME call; these tests are what issue #1 actually
# wanted, delivered without the extra calls.


def test_settled_claim_may_only_use_formal_moves(engine):
    verdict = out(
        shape=ClaimShape.ASSERTION,
        winner="",
        loser="",
        decidability=Decidability.SETTLED,
        granted="the earth orbits the sun",
        position="Granted, and it settles nothing you need.",
        points=[PointOut(move=MoveId.REFERENCE_CLASS_SWAP, text="wrong population")],
    )
    fault = engine.fault(verdict, must_not_back="")
    assert fault is not None
    assert "reference_class_swap" in fault


def test_tautological_claim_is_restricted_the_same_way(engine):
    verdict = out(
        shape=ClaimShape.ASSERTION,
        winner="",
        loser="",
        decidability=Decidability.TAUTOLOGICAL,
        granted="it will rain or it will not",
        position="True, and empty.",
        points=[PointOut(move=MoveId.COUNTEREXAMPLE, text="not universal")],
    )
    fault = engine.fault(verdict, must_not_back="")
    assert fault is not None
    assert "counterexample" in fault


def test_settled_claim_using_only_formal_moves_passes(engine):
    verdict = out(
        shape=ClaimShape.ASSERTION,
        winner="",
        loser="",
        decidability=Decidability.SETTLED,
        granted="the earth orbits the sun",
        position="Granted, and it settles nothing you need.",
        points=[
            PointOut(move=MoveId.VACUITY_ATTACK, text="true but does no work"),
            PointOut(move=MoveId.FORMAL_DEFEAT, text="no premises offered"),
        ],
    )
    assert engine.fault(verdict, must_not_back="") is None


def test_contested_claim_is_not_restricted(engine):
    """Only settled/tautological gates move choice; ordinary disagreement
    keeps the whole catalogue available."""
    verdict = out(decidability=Decidability.CONTESTED)
    assert engine.fault(verdict, must_not_back="monolith") is None


def test_settled_comparative_claim_is_restricted_too(engine):
    """The gate is not conditional on shape -- a comparative claim classified
    settled is just as restricted as an assertion classified settled."""
    verdict = out(
        decidability=Decidability.SETTLED,
        points=[PointOut(move=MoveId.MECHANISM_ATTACK, text="wrong cause")],
    )
    fault = engine.fault(verdict, must_not_back="monolith")
    assert fault is not None
    assert "mechanism_attack" in fault


def test_force_formal_overrides_a_freshly_claimed_contested(engine):
    """force_formal is how a rebuttal or a flip stays restricted even if this
    call's own decidability says the claim somehow became contested --
    closing the loophole where a settled claim is 'laundered' into a
    debatable one under a counter-argument or a flip."""
    verdict = out(
        decidability=Decidability.CONTESTED,
        points=[
            PointOut(move=MoveId.PRECEDENT_INVERSION, text="that case cuts the other way")
        ],
    )
    assert engine.fault(verdict, must_not_back="monolith") is None
    fault = engine.fault(verdict, must_not_back="monolith", force_formal=True)
    assert fault is not None
    assert "precedent_inversion" in fault


def test_all_formal_moves_are_accepted_under_restriction(engine):
    points = [PointOut(move=m, text="x") for m in FORMAL_MOVES]
    verdict = out(decidability=Decidability.SETTLED, points=points[:3])
    assert engine.fault(verdict, must_not_back="monolith") is None


# ── protected propositions ────────────────────────────────────────────
# Two live outputs motivated every rule below:
#   "drinking bleach is dangerous" -> "many low-concentration exposures are
#    negligible ... does not inform which amounts, if any, might be safe"
#   "the Holocaust was a moral catastrophe" -> "how does labeling it a moral
#    catastrophe advance your specific policy or educational agenda?"


def _point(move, text):
    return PointOut(move=move, text=text)


GOOD_POINT = _point(
    MoveId.FORMAL_DEFEAT, "You asserted this without offering a single premise."
)


def test_only_formal_defeat_is_allowed():
    assert PROTECTED_MOVES == {MoveId.FORMAL_DEFEAT}


def test_clean_protected_verdict_passes():
    assert (
        protected_fault(
            [GOOD_POINT],
            "What is the argument, stated as premises?",
            "Drinking bleach is dangerous.",
        )
        is None
    )


def test_protected_claim_must_be_granted():
    fault = protected_fault([GOOD_POINT], "What is the argument?", "")
    assert fault is not None
    assert "granted" in fault


def test_vacuity_attack_is_refused():
    """The move that produced 'offers no actionable insight' about the Holocaust."""
    fault = protected_fault(
        [_point(MoveId.VACUITY_ATTACK, "True, but it does no work.")],
        "What follows from it?",
        "The Holocaust was a moral catastrophe.",
    )
    assert fault is not None
    assert "not permitted" in fault


def test_criterion_shift_is_refused():
    """The move that produced the LD50 argument about bleach."""
    fault = protected_fault(
        [_point(MoveId.CRITERION_SHIFT, "The relevant metric is lethal dose.")],
        "What concentration?",
        "Drinking bleach is dangerous.",
    )
    assert fault is not None
    assert "not permitted" in fault


@pytest.mark.parametrize(
    "text",
    [
        "Low concentration exposures are negligible.",
        "You give no dosage, so the claim is unbounded.",
        "Small amounts might be safe.",
        "Under certain conditions this does not hold.",
        "The LD50 is unstated.",
    ],
)
def test_substance_reaching_language_is_refused(text):
    fault = protected_fault([_point(MoveId.FORMAL_DEFEAT, text)], "Argue it?", "granted")
    assert fault is not None
    assert "substance" in fault


@pytest.mark.parametrize(
    "challenge",
    [
        "What policy agenda does this serve?",
        "Why do you care about this?",
        "What are you trying to achieve by saying it?",
        "What is the purpose of raising it?",
    ],
)
def test_motive_questioning_is_refused(challenge):
    fault = protected_fault([GOOD_POINT], challenge, "granted")
    assert fault is not None
    assert "motive" in fault


def test_challenge_may_ask_for_the_argument():
    assert (
        protected_fault([GOOD_POINT], "Which premises get you there?", "granted") is None
    )
