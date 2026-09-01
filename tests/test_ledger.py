from intelli_oppo.core import Ledger, MoveId, Point, Scope, Turn, Verdict


def make_turn(winner: str, loser: str, scope: Scope, user_favors: str = "") -> Turn:
    return Turn(
        user_text=f"{loser} is better than {winner}",
        user_favors=user_favors or loser,
        verdict=Verdict(
            winner=winner,
            loser=loser,
            scope=scope,
            points=(Point(move=MoveId.CRITERION_SHIFT, text="metric is wrong"),),
            challenge="which metric?",
        ),
    )


THROUGHPUT = Scope("merge-queue throughput", "org > 50 eng", "3y")
COST = Scope("total cost of ownership", "org > 50 eng", "10y")


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


def test_scope_matching_ignores_case_and_padding():
    ledger = Ledger()
    ledger.record(make_turn("a", "b", Scope("Cost", "Teams", "5y")))
    ledger.record(make_turn("b", "a", Scope("  cost ", "TEAMS", "5y")))

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


def test_meta_turns_never_count_as_contradictions():
    """A meta-opposition turn grants the claim rather than backing a side, so it
    has no winner to disagree with — even in an identical scope cell."""
    from intelli_oppo.core import ClaimShape

    meta = Verdict(
        scope=THROUGHPUT,
        points=(),
        challenge="",
        granted="microservices deploy more often",
        position="Not disputing that. Disputing that it decides anything.",
        shape=ClaimShape.ASSERTION,
    )
    ledger = Ledger()
    ledger.record(make_turn("microservices", "monolith", THROUGHPUT))
    ledger.record(Turn(user_text="x", user_favors="monolith", verdict=meta))

    assert ledger.contradictions() == []


def test_commitments_render_meta_turns_by_position():
    from intelli_oppo.core import ClaimShape

    meta = Verdict(
        scope=COST,
        points=(),
        challenge="",
        position="Granted, and it does no work.",
        shape=ClaimShape.ASSERTION,
    )
    ledger = Ledger()
    ledger.record(Turn(user_text="x", user_favors="y", verdict=meta))

    assert "Granted, and it does no work." in ledger.commitments()[0]
