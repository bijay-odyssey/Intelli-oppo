from intelli_oppo.core import (
    ClaimShape,
    Horizon,
    Ledger,
    MetricKind,
    MoveId,
    Point,
    Scope,
    Turn,
    Verdict,
)

THROUGHPUT = Scope(
    MetricKind.SPEED, "merge-queue throughput", "org > 50 eng", Horizon.ONE_TO_3Y
)
COST = Scope(
    MetricKind.COST, "total cost of ownership", "org > 50 eng", Horizon.THREE_TO_10Y
)


def make_turn(winner: str, loser: str, scope: Scope, user_favors: str = "") -> Turn:
    return Turn(
        user_text=f"{loser} is better than {winner}",
        user_favors=user_favors or loser,
        verdict=Verdict(
            scope=scope,
            points=(Point(move=MoveId.CRITERION_SHIFT, text="metric is wrong"),),
            challenge="which metric?",
            winner=winner,
            loser=loser,
        ),
    )


def test_opposite_winners_in_different_scopes_is_not_a_contradiction():
    """The whole point of scoped claim discipline."""
    ledger = Ledger()
    ledger.record(make_turn("microservices", "monolith", THROUGHPUT))
    ledger.record(make_turn("monolith", "microservices", COST))

    assert ledger.contradictions() == []


def test_opposite_winners_in_one_scope_is_a_contradiction():
    ledger = Ledger()
    ledger.record(make_turn("microservices", "monolith", THROUGHPUT))
    ledger.record(make_turn("monolith", "microservices", THROUGHPUT))

    found = ledger.contradictions()
    assert len(found) == 1
    assert found[0].earlier_turn == 0
    assert found[0].later_turn == 1
    assert "microservices" in found[0].render()


def test_reworded_scope_no_longer_escapes_detection():
    """The regression that made this metric near-vacuous.

    Both scopes describe one cell in different words. Under string comparison
    the engine reversed its winner and the record came back clean.
    """
    a = Scope(
        MetricKind.CORRECTNESS,
        "numerical equality of base-10 integers",
        "primary-school arithmetic expressions",
        Horizon.IMMEDIATE,
    )
    b = Scope(
        MetricKind.CORRECTNESS,
        "standard base-10 integer addition",
        "primary-school arithmetic",
        Horizon.IMMEDIATE,
    )
    ledger = Ledger()
    ledger.record(make_turn("X", "Y", a))
    ledger.record(make_turn("Y", "X", b))

    assert len(ledger.contradictions()) == 1


def test_same_winner_repeated_is_not_a_contradiction():
    ledger = Ledger()
    ledger.record(make_turn("microservices", "monolith", THROUGHPUT))
    ledger.record(make_turn("microservices", "monolith", THROUGHPUT))

    assert ledger.contradictions() == []


def test_tracks_current_stances():
    ledger = Ledger()
    assert ledger.is_empty
    assert ledger.system_favors == ""

    ledger.record(make_turn("microservices", "monolith", THROUGHPUT))
    assert ledger.system_favors == "microservices"
    assert ledger.user_favors == "monolith"


def test_context_for_prompt_marks_concessions():
    ledger = Ledger()
    turn = make_turn("microservices", "monolith", THROUGHPUT)
    ledger.record(
        Turn(
            user_text=turn.user_text,
            user_favors=turn.user_favors,
            verdict=turn.verdict,
            conceded=True,
        )
    )
    assert "[user conceded]" in ledger.context_for_prompt()


def test_empty_ledger_context_is_explicit():
    assert "opening claim" in Ledger().context_for_prompt()


def _meta(scope: Scope, position: str, granted: str = "") -> Verdict:
    return Verdict(
        scope=scope,
        points=(),
        challenge="",
        granted=granted,
        position=position,
        shape=ClaimShape.ASSERTION,
    )


def test_meta_turns_never_count_as_contradictions():
    """A meta-opposition turn grants the claim rather than backing a side, so it
    has no winner to disagree with — even in an identical scope cell."""
    ledger = Ledger()
    ledger.record(make_turn("microservices", "monolith", THROUGHPUT))
    ledger.record(
        Turn(
            user_text="x",
            user_favors="monolith",
            verdict=_meta(THROUGHPUT, "Not disputing that.", "they deploy often"),
        )
    )
    assert ledger.contradictions() == []


def test_commitments_render_meta_turns_by_position():
    ledger = Ledger()
    ledger.record(
        Turn(
            user_text="x",
            user_favors="y",
            verdict=_meta(COST, "Granted, and it does no work."),
        )
    )
    assert "Granted, and it does no work." in ledger.commitments()[0]
