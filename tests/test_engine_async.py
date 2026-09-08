"""Coverage for the engine's async paths.

Phase 0 shipped with tests for `fault()` and nothing else — the repair retry,
the shrink fallback, the safety routing and ledger recording were all untested
while being the parts most likely to break under refactoring.
"""

import json

import pytest

from intelli_oppo.config import Settings
from intelli_oppo.core import ClaimShape, Horizon, MetricKind, MoveId, TurnKind
from intelli_oppo.llm.provider import LLMError, LLMProvider, Role
from intelli_oppo.reason.engine import OppositionEngine

SETTINGS = Settings(groq_token="fake")


def verdict_payload(**overrides) -> dict:
    base = {
        "shape": "comparative",
        "user_favors": "monolith",
        "granted": "",
        "position": "",
        "winner": "microservices",
        "loser": "monolith",
        "metric_kind": "speed",
        "metric": "merge-queue throughput",
        "domain": "org > 50 eng",
        "horizon": "1_to_3y",
        "points": [{"move": "criterion_shift", "text": "your metric is not decisive"}],
        "challenge": "which metric?",
        "pivot": "none",
    }
    return {**base, **overrides}


def guard_payload(sensitivity: str = "open", reason: str = "ordinary") -> dict:
    return {"sensitivity": sensitivity, "reason": reason}


def label(kind: str = "claim", reason: str = "states a position") -> dict:
    return {"kind": kind, "reason": reason}


class FakeProvider(LLMProvider):
    """Scripts responses per role. A single scripted item repeats.

    A dict is returned as JSON; a raw string is returned verbatim, which is what
    the aside path needs since it calls `complete` rather than `structured`.
    """

    def __init__(self, script: dict[Role, list]) -> None:
        self.script = {role: list(items) for role, items in script.items()}
        self.calls: list[tuple[Role, str]] = []

    async def complete(self, *, role, system, user, **kwargs) -> str:
        self.calls.append((role, user))
        queue = self.script.get(role)
        if not queue:
            raise AssertionError(f"no scripted response for {role}")
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        return item if isinstance(item, str) else json.dumps(item)

    async def aclose(self) -> None:
        pass

    def count(self, role: Role) -> int:
        return sum(1 for r, _ in self.calls if r is role)


def build(script: dict[Role, list]) -> tuple[OppositionEngine, FakeProvider]:
    provider = FakeProvider(script)
    return OppositionEngine(provider, SETTINGS), provider


BASE = {Role.SAFEGUARD: [guard_payload()], Role.UTILITY: [label()]}


# ── the ordinary path ─────────────────────────────────────────────────


async def test_respond_records_a_scoped_turn():
    engine, _ = build({**BASE, Role.REASONING: [verdict_payload()]})
    reply = await engine.respond("Monoliths are better than microservices.")

    assert reply.kind is TurnKind.CLAIM
    assert reply.turn.verdict.winner == "microservices"
    assert reply.turn.verdict.scope.metric_kind is MetricKind.SPEED
    assert reply.turn.verdict.scope.horizon is Horizon.ONE_TO_3Y
    assert not reply.turn.verdict.protected
    assert len(engine.ledger.turns) == 1


async def test_classification_runs_before_anything_expensive():
    engine, provider = build({**BASE, Role.REASONING: [verdict_payload()]})
    await engine.respond("Cats are better than dogs.")

    assert provider.calls[0][0] is Role.UTILITY, "classify first"
    assert provider.calls[1][0] is Role.SAFEGUARD, "then screen"


# ── routing ───────────────────────────────────────────────────────────


async def test_aside_never_reaches_the_reasoning_model():
    """`hello` used to burn a full reasoning call to vacuity-attack a greeting."""
    engine, provider = build(
        {
            Role.UTILITY: [label("aside", "greeting"), "That is not a claim."],
        }
    )
    reply = await engine.respond("hello")

    assert reply.is_aside
    assert reply.text == "That is not a claim."
    assert provider.count(Role.REASONING) == 0
    assert provider.count(Role.SAFEGUARD) == 0, "no claim to screen"
    assert engine.ledger.is_empty, "small talk commits nobody to anything"


async def test_plain_english_agreement_fires_the_flip():
    """The headline behaviour, previously gated behind typing /concede."""
    engine, provider = build(
        {
            Role.SAFEGUARD: [guard_payload()],
            Role.UTILITY: [label(), label("concession", "user agrees")],
            Role.REASONING: [
                verdict_payload(),
                verdict_payload(
                    winner="monolith",
                    loser="microservices",
                    user_favors="microservices",
                    metric_kind="cost",
                    horizon="over_10y",
                    pivot="concession_overreach",
                ),
            ],
        }
    )
    await engine.respond("Monoliths are better.")
    reply = await engine.respond("ok fair enough, you win")

    assert reply.kind is TurnKind.CONCESSION
    assert reply.turn.conceded
    assert reply.turn.verdict.winner == "monolith"
    assert engine.ledger.contradictions() == []


async def test_counter_holds_the_position_and_the_scope():
    """A push-back used to be misread as a brand-new claim."""
    engine, provider = build(
        {
            Role.SAFEGUARD: [guard_payload()],
            Role.UTILITY: [label(), label("counter", "pushes back")],
            Role.REASONING: [verdict_payload()],
        }
    )
    await engine.respond("Monoliths are better.")
    reply = await engine.respond("No, coordination cost is overstated.")

    assert reply.kind is TurnKind.COUNTER
    assert reply.turn.kind is TurnKind.COUNTER
    assert reply.turn.verdict.winner == "microservices", "held its side"
    assert engine.ledger.contradictions() == []
    assert provider.count(Role.SAFEGUARD) == 1, "only the opening claim is screened"


async def test_counter_prompt_carries_the_held_position():
    engine, provider = build(
        {
            Role.SAFEGUARD: [guard_payload()],
            Role.UTILITY: [label(), label("counter", "pushes back")],
            Role.REASONING: [verdict_payload()],
        }
    )
    await engine.respond("Monoliths are better.")
    await engine.respond("That is overstated.")

    last_reasoning = [u for r, u in provider.calls if r is Role.REASONING][-1]
    assert "Hold your position" in last_reasoning
    assert "merge-queue throughput" in last_reasoning


async def test_counter_without_history_is_treated_as_a_claim():
    engine, _ = build(
        {
            **BASE,
            Role.UTILITY: [label("counter", "sounds like pushback")],
            Role.REASONING: [verdict_payload()],
        }
    )
    reply = await engine.respond("No, you're wrong.")

    assert reply.kind is TurnKind.CLAIM


async def test_classifier_failure_falls_back_to_claim():
    """Dropping a claim silently is worse than wasting one call on a greeting."""

    class NoClassifier(FakeProvider):
        async def complete(self, *, role, system, user, **kwargs) -> str:
            if role is Role.UTILITY:
                raise LLMError("utility model down")
            return await super().complete(role=role, system=system, user=user, **kwargs)

    provider = NoClassifier(
        {Role.SAFEGUARD: [guard_payload()], Role.REASONING: [verdict_payload()]}
    )
    engine = OppositionEngine(provider, SETTINGS)
    reply = await engine.respond("Monoliths are better.")

    assert reply.kind is TurnKind.CLAIM
    assert reply.turn is not None


# ── the repair round-trip ─────────────────────────────────────────────


async def test_repair_fires_when_the_engine_backs_the_users_side():
    engine, provider = build(
        {
            **BASE,
            Role.REASONING: [
                verdict_payload(winner="monolith", loser="microservices"),
                verdict_payload(),
            ],
        }
    )
    reply = await engine.respond("Monoliths are better.")

    assert reply.turn.verdict.winner == "microservices"
    assert provider.count(Role.REASONING) == 2
    assert "was rejected" in provider.calls[-1][1]


async def test_repair_exhaustion_raises():
    engine, _ = build(
        {**BASE, Role.REASONING: [verdict_payload(winner="monolith", loser="micro")]}
    )
    with pytest.raises(LLMError, match="usable verdict"):
        await engine.respond("Monoliths are better.")


# ── the output budget ─────────────────────────────────────────────────


async def test_over_budget_verdict_is_compressed():
    long_text = " ".join(["word"] * 120)
    engine, provider = build(
        {
            Role.SAFEGUARD: [guard_payload()],
            Role.UTILITY: [
                label(),
                {
                    "points": [{"move": "criterion_shift", "text": "tight now"}],
                    "challenge": "which metric?",
                },
            ],
            Role.REASONING: [
                verdict_payload(points=[{"move": "criterion_shift", "text": long_text}])
            ],
        }
    )
    reply = await engine.respond("Monoliths are better.")

    assert reply.turn.verdict.points[0].text == "tight now"
    assert reply.turn.verdict.body_words <= SETTINGS.max_body_words


async def test_shrink_falls_back_to_dropping_points_when_compression_fails():
    long_text = " ".join(["word"] * 120)
    three = [
        {"move": "criterion_shift", "text": long_text},
        {"move": "formal_defeat", "text": "b"},
        {"move": "burden_asymmetry", "text": "c"},
    ]
    engine, _ = build(
        {
            Role.SAFEGUARD: [guard_payload()],
            Role.UTILITY: [label(), {"nonsense": True}],
            Role.REASONING: [verdict_payload(points=three)],
        }
    )
    reply = await engine.respond("Monoliths are better.")

    assert len(reply.turn.verdict.points) == 2


# ── the safety gate ───────────────────────────────────────────────────


PROTECTED_OK = verdict_payload(
    shape="assertion",
    winner="",
    loser="",
    granted="Drinking bleach is dangerous.",
    position="You asserted this. You did not argue it.",
    metric_kind="other",
    horizon="immediate",
    points=[{"move": "formal_defeat", "text": "No premises were offered."}],
    challenge="Which premises get you there?",
)

PROTECTED_GUARD = {
    Role.SAFEGUARD: [guard_payload("protected", "acute toxicity")],
    Role.UTILITY: [label()],
}


async def test_protected_claims_take_the_constrained_path():
    engine, provider = build({**PROTECTED_GUARD, Role.REASONING: [PROTECTED_OK]})
    reply = await engine.respond("Drinking bleach is dangerous.")

    assert reply.turn.verdict.protected
    assert reply.turn.verdict.shape is ClaimShape.ASSERTION
    assert reply.turn.verdict.granted == "Drinking bleach is dangerous."
    assert all(p.move is MoveId.FORMAL_DEFEAT for p in reply.turn.verdict.points)
    assert "acute toxicity" in provider.calls[-1][1]


async def test_protected_turn_rejects_substance_reaching_points():
    """The bleach failure: arguing toward some amount being safe."""
    engine, provider = build(
        {
            **PROTECTED_GUARD,
            Role.REASONING: [
                verdict_payload(
                    shape="assertion",
                    winner="",
                    loser="",
                    granted="Drinking bleach is dangerous.",
                    position="Asserted, not argued.",
                    points=[
                        {
                            "move": "formal_defeat",
                            "text": "Low concentration exposures are negligible.",
                        }
                    ],
                    challenge="Which premises?",
                ),
                PROTECTED_OK,
            ],
        }
    )
    reply = await engine.respond("Drinking bleach is dangerous.")

    assert provider.count(Role.REASONING) == 2
    assert "negligible" not in reply.turn.verdict.points[0].text


async def test_protected_turn_rejects_motive_questioning():
    """The Holocaust failure: asking what agenda the claim serves."""
    engine, provider = build(
        {
            Role.SAFEGUARD: [guard_payload("protected", "atrocity")],
            Role.UTILITY: [label()],
            Role.REASONING: [
                verdict_payload(
                    shape="assertion",
                    winner="",
                    loser="",
                    granted="The Holocaust was a moral catastrophe.",
                    position="Asserted, not argued.",
                    points=[{"move": "formal_defeat", "text": "No premises offered."}],
                    challenge="What policy agenda does this serve?",
                ),
                PROTECTED_OK,
            ],
        }
    )
    await engine.respond("The Holocaust was a moral catastrophe.")

    assert provider.count(Role.REASONING) == 2


async def test_screening_failure_fails_closed():
    """If the classifier is unreachable, treat the claim as protected."""

    class BrokenGuard(FakeProvider):
        async def complete(self, *, role, system, user, **kwargs) -> str:
            if role is Role.SAFEGUARD:
                raise LLMError("safeguard unreachable")
            return await super().complete(role=role, system=system, user=user, **kwargs)

    provider = BrokenGuard({Role.UTILITY: [label()], Role.REASONING: [PROTECTED_OK]})
    engine = OppositionEngine(provider, SETTINGS)
    reply = await engine.respond("Anything at all.")

    assert reply.turn.verdict.protected


async def test_counter_after_a_protected_turn_is_treated_as_a_fresh_claim():
    """There was no position to defend, so there is nothing to hold."""
    engine, _ = build(
        {
            Role.SAFEGUARD: [guard_payload("protected", "toxicity"), guard_payload()],
            Role.UTILITY: [label(), label("counter", "pushes back")],
            Role.REASONING: [PROTECTED_OK, verdict_payload()],
        }
    )
    await engine.respond("Drinking bleach is dangerous.")
    reply = await engine.respond("Monoliths are better.")

    assert reply.turn.verdict.winner == "microservices"
    assert not reply.turn.verdict.protected


# ── concession ────────────────────────────────────────────────────────


async def test_concede_needs_a_prior_turn():
    engine, _ = build(BASE)
    with pytest.raises(LLMError, match="make a claim first"):
        await engine.concede()


async def test_cannot_concede_to_a_protected_turn():
    engine, _ = build({**PROTECTED_GUARD, Role.REASONING: [PROTECTED_OK]})
    await engine.respond("Drinking bleach is dangerous.")

    with pytest.raises(LLMError, match="nothing to concede"):
        await engine.concede()


# ── holding ground under a counter ────────────────────────────────────
# The rebuttal prompt asks the engine to keep its scope. Asking is not enough:
# sliding the scope sideways under pressure is the cheapest way to dodge an
# objection, and precisely what Invariant II exists to prevent.


async def _counter_after_claim(second_verdict: dict, third: dict | None = None):
    reasoning = [verdict_payload(), second_verdict]
    if third is not None:
        reasoning.append(third)
    return build(
        {
            Role.SAFEGUARD: [guard_payload()],
            Role.UTILITY: [label(), label("counter", "pushes back")],
            Role.REASONING: reasoning,
        }
    )


async def test_rebuttal_that_moves_the_scope_is_rejected():
    engine, provider = await _counter_after_claim(
        verdict_payload(metric_kind="cost", horizon="over_10y"),
        verdict_payload(),
    )
    await engine.respond("Monoliths are better.")
    reply = await engine.respond("Coordination cost is overstated.")

    assert provider.count(Role.REASONING) == 3, "one claim, one bad rebuttal, one retry"
    assert reply.turn.verdict.scope.metric_kind is MetricKind.SPEED
    assert "moved the scope" in [u for _, u in provider.calls if "rejected" in u][-1]


async def test_rebuttal_that_switches_sides_is_rejected():
    engine, provider = await _counter_after_claim(
        verdict_payload(winner="monolith", loser="microservices", user_favors="x"),
        verdict_payload(),
    )
    await engine.respond("Monoliths are better.")
    reply = await engine.respond("Coordination cost is overstated.")

    assert reply.turn.verdict.winner == "microservices"
    assert provider.count(Role.REASONING) == 3


async def test_rebuttal_may_narrow_the_wording_without_moving_the_cell():
    """Sharpening the description is fine; changing the axis is not."""
    engine, provider = await _counter_after_claim(
        verdict_payload(metric="merge-queue throughput per sprint")
    )
    await engine.respond("Monoliths are better.")
    reply = await engine.respond("Coordination cost is overstated.")

    assert provider.count(Role.REASONING) == 2, "accepted without a retry"
    assert reply.turn.verdict.scope.metric == "merge-queue throughput per sprint"


async def test_rebuttal_that_will_not_hold_raises():
    engine, _ = await _counter_after_claim(
        verdict_payload(metric_kind="cost", horizon="over_10y")
    )
    await engine.respond("Monoliths are better.")
    with pytest.raises(LLMError, match="could not hold position"):
        await engine.respond("Coordination cost is overstated.")
