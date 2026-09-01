"""Coverage for the engine's async paths.

Phase 0 shipped with tests for `fault()` and nothing else — the repair retry,
the shrink fallback, the safety routing and ledger recording were all untested
while being the parts most likely to break under refactoring.
"""

import json

import pytest

from intelli_oppo.config import Settings
from intelli_oppo.core import ClaimShape, Horizon, MetricKind, MoveId
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


class FakeProvider(LLMProvider):
    """Scripts responses per role. A single scripted item repeats."""

    def __init__(self, script: dict[Role, list[dict]]) -> None:
        self.script = {role: list(items) for role, items in script.items()}
        self.calls: list[tuple[Role, str]] = []

    async def complete(self, *, role, system, user, **kwargs) -> str:
        self.calls.append((role, user))
        queue = self.script.get(role)
        if not queue:
            raise AssertionError(f"no scripted response for {role}")
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        return json.dumps(item)

    async def aclose(self) -> None:
        pass

    def count(self, role: Role) -> int:
        return sum(1 for r, _ in self.calls if r is role)


def build(script: dict[Role, list[dict]]) -> tuple[OppositionEngine, FakeProvider]:
    provider = FakeProvider(script)
    return OppositionEngine(provider, SETTINGS), provider


OPEN_GUARD = {Role.SAFEGUARD: [guard_payload()]}


# ── the ordinary path ─────────────────────────────────────────────────


async def test_respond_records_a_scoped_turn():
    engine, _ = build({**OPEN_GUARD, Role.REASONING: [verdict_payload()]})
    turn = await engine.respond("Monoliths are better than microservices.")

    assert turn.verdict.winner == "microservices"
    assert turn.verdict.scope.metric_kind is MetricKind.SPEED
    assert turn.verdict.scope.horizon is Horizon.ONE_TO_3Y
    assert not turn.verdict.protected
    assert len(engine.ledger.turns) == 1


async def test_every_turn_is_screened_first():
    engine, provider = build({**OPEN_GUARD, Role.REASONING: [verdict_payload()]})
    await engine.respond("Cats are better than dogs.")

    assert provider.calls[0][0] is Role.SAFEGUARD


# ── the repair round-trip ─────────────────────────────────────────────


async def test_repair_fires_when_the_engine_backs_the_users_side():
    engine, provider = build(
        {
            **OPEN_GUARD,
            Role.REASONING: [
                verdict_payload(winner="monolith", loser="microservices"),
                verdict_payload(),
            ],
        }
    )
    turn = await engine.respond("Monoliths are better.")

    assert turn.verdict.winner == "microservices"
    assert provider.count(Role.REASONING) == 2
    assert "was rejected" in provider.calls[-1][1]


async def test_repair_exhaustion_raises():
    engine, _ = build(
        {
            **OPEN_GUARD,
            Role.REASONING: [verdict_payload(winner="monolith", loser="micro")],
        }
    )
    with pytest.raises(LLMError, match="usable verdict"):
        await engine.respond("Monoliths are better.")


# ── the output budget ─────────────────────────────────────────────────


async def test_over_budget_verdict_is_compressed():
    long_text = " ".join(["word"] * 120)
    engine, provider = build(
        {
            **OPEN_GUARD,
            Role.REASONING: [
                verdict_payload(points=[{"move": "criterion_shift", "text": long_text}])
            ],
            Role.UTILITY: [
                {
                    "points": [{"move": "criterion_shift", "text": "tight now"}],
                    "challenge": "which metric?",
                }
            ],
        }
    )
    turn = await engine.respond("Monoliths are better.")

    assert turn.verdict.points[0].text == "tight now"
    assert turn.verdict.body_words <= SETTINGS.max_body_words
    assert provider.count(Role.UTILITY) == 1


async def test_shrink_falls_back_to_dropping_points_when_compression_fails():
    long_text = " ".join(["word"] * 120)
    three = [
        {"move": "criterion_shift", "text": long_text},
        {"move": "formal_defeat", "text": "b"},
        {"move": "burden_asymmetry", "text": "c"},
    ]
    engine, _ = build(
        {
            **OPEN_GUARD,
            Role.REASONING: [verdict_payload(points=three)],
            Role.UTILITY: [{"nonsense": True}],
        }
    )
    turn = await engine.respond("Monoliths are better.")

    assert len(turn.verdict.points) == 2


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


async def test_protected_claims_take_the_constrained_path():
    engine, provider = build(
        {
            Role.SAFEGUARD: [guard_payload("protected", "acute toxicity")],
            Role.REASONING: [PROTECTED_OK],
        }
    )
    turn = await engine.respond("Drinking bleach is dangerous.")

    assert turn.verdict.protected
    assert turn.verdict.shape is ClaimShape.ASSERTION
    assert turn.verdict.granted == "Drinking bleach is dangerous."
    assert all(p.move is MoveId.FORMAL_DEFEAT for p in turn.verdict.points)
    assert "acute toxicity" in provider.calls[-1][1]


async def test_protected_turn_rejects_substance_reaching_points():
    """The bleach failure: arguing toward some amount being safe."""
    engine, provider = build(
        {
            Role.SAFEGUARD: [guard_payload("protected", "acute toxicity")],
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
    turn = await engine.respond("Drinking bleach is dangerous.")

    assert provider.count(Role.REASONING) == 2
    assert "negligible" not in turn.verdict.points[0].text


async def test_protected_turn_rejects_motive_questioning():
    """The Holocaust failure: asking what agenda the claim serves."""
    engine, provider = build(
        {
            Role.SAFEGUARD: [guard_payload("protected", "atrocity")],
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

    provider = BrokenGuard({Role.REASONING: [PROTECTED_OK]})
    engine = OppositionEngine(provider, SETTINGS)
    turn = await engine.respond("Anything at all.")

    assert turn.verdict.protected


# ── concession ────────────────────────────────────────────────────────


async def test_concede_needs_a_prior_turn():
    engine, _ = build(OPEN_GUARD)
    with pytest.raises(LLMError, match="make a claim first"):
        await engine.concede()


async def test_concede_flips_the_winner():
    engine, _ = build(
        {
            **OPEN_GUARD,
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
    turn = await engine.concede()

    assert turn.conceded
    assert turn.verdict.winner == "monolith"
    assert turn.pivot.value == "concession_overreach"
    assert engine.ledger.contradictions() == [], "flip must not reuse the scope cell"


async def test_cannot_concede_to_a_protected_turn():
    engine, _ = build(
        {
            Role.SAFEGUARD: [guard_payload("protected", "acute toxicity")],
            Role.REASONING: [PROTECTED_OK],
        }
    )
    await engine.respond("Drinking bleach is dangerous.")

    with pytest.raises(LLMError, match="nothing to concede"):
        await engine.concede()
