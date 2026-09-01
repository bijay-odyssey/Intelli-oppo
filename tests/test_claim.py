from intelli_oppo.core import (
    ClaimShape,
    MoveId,
    Point,
    Scope,
    Verdict,
    word_count,
)


def test_word_count_ignores_punctuation():
    assert word_count("Better under which metric? Under M', B wins.") == 8


def test_word_count_handles_empty():
    assert word_count("") == 0


def test_scope_key_normalizes():
    a = Scope("Total Cost", " Teams > 50 ", "10Y")
    b = Scope("total cost", "teams > 50", "10y")
    assert a.key() == b.key()


def test_scope_renders_all_three_axes():
    rendered = Scope("throughput", "org > 50", "3y").render()
    assert "throughput" in rendered
    assert "org > 50" in rendered
    assert "3y" in rendered


def test_body_words_covers_points_and_challenge():
    verdict = Verdict(
        winner="b",
        loser="a",
        scope=Scope("cost", "teams", "5y"),
        points=(
            Point(move=MoveId.CRITERION_SHIFT, text="one two three"),
            Point(move=MoveId.FORMAL_DEFEAT, text="four five"),
        ),
        challenge="six seven",
    )
    assert verdict.body_words == 7


def test_granted_defaults_empty():
    verdict = Verdict(
        winner="b",
        loser="a",
        scope=Scope("cost", "teams", "5y"),
        points=(),
        challenge="",
    )
    assert verdict.granted == ""
    assert verdict.body_words == 0


def test_comparative_headline_pairs_the_options():
    verdict = Verdict(
        scope=Scope("cost", "teams", "5y"),
        points=(),
        challenge="",
        winner="b",
        loser="a",
    )
    assert not verdict.is_meta
    assert verdict.headline == "b ≻ a"


def test_meta_verdict_uses_position_not_a_negation():
    """Invariant I: a granted fact must never appear as the loser."""
    verdict = Verdict(
        scope=Scope("arithmetic", "base 10", "immediate"),
        points=(),
        challenge="",
        granted="2 + 2 = 4",
        position="Not disputing that. Disputing that your argument earns it.",
        shape=ClaimShape.ASSERTION,
    )
    assert verdict.is_meta
    assert verdict.headline.startswith("Not disputing")
    assert "≠" not in verdict.headline


def test_meta_headline_falls_back_when_position_missing():
    verdict = Verdict(scope=Scope("m", "d", "h"), points=(), challenge="")
    assert verdict.is_meta
    assert "Disputing" in verdict.headline
