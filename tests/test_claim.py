from intelli_oppo.core import (
    ClaimShape,
    Horizon,
    MetricKind,
    MoveId,
    Point,
    Scope,
    Verdict,
    word_count,
)

COST_5Y = Scope(MetricKind.COST, "total cost", "teams", Horizon.THREE_TO_10Y)


def test_word_count_ignores_punctuation():
    assert word_count("Better under which metric? Under M', B wins.") == 8


def test_word_count_handles_empty():
    assert word_count("") == 0


def test_scope_renders_all_three_axes():
    rendered = Scope(
        MetricKind.SPEED, "throughput", "org > 50", Horizon.ONE_TO_3Y
    ).render()
    assert "throughput" in rendered
    assert "org > 50" in rendered
    assert "1-3 years" in rendered


def test_body_words_covers_points_and_challenge():
    verdict = Verdict(
        scope=COST_5Y,
        points=(
            Point(move=MoveId.CRITERION_SHIFT, text="one two three"),
            Point(move=MoveId.FORMAL_DEFEAT, text="four five"),
        ),
        challenge="six seven",
        winner="b",
        loser="a",
    )
    assert verdict.body_words == 7


def test_granted_defaults_empty():
    verdict = Verdict(scope=COST_5Y, points=(), challenge="", winner="b", loser="a")
    assert verdict.granted == ""
    assert verdict.body_words == 0


def test_comparative_headline_pairs_the_options():
    verdict = Verdict(scope=COST_5Y, points=(), challenge="", winner="b", loser="a")
    assert not verdict.is_meta
    assert verdict.headline == "b ≻ a"


def test_meta_verdict_uses_position_not_a_negation():
    """Invariant I: a granted fact must never appear as the loser."""
    verdict = Verdict(
        scope=Scope(
            MetricKind.CORRECTNESS, "integer addition", "base 10", Horizon.IMMEDIATE
        ),
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
    verdict = Verdict(scope=COST_5Y, points=(), challenge="")
    assert verdict.is_meta
    assert "Disputing" in verdict.headline


# ── scope cell identity ───────────────────────────────────────────────
# Free-text scopes made the contradiction check near-vacuous: two wordings of
# one cell never matched, so the engine could reverse itself indefinitely just
# by rephrasing. These pin the typed replacement.


def test_reworded_same_cell_is_recognised():
    """Both scopes are taken verbatim from a real run that escaped detection."""
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
    assert a.same_cell_as(b)


def test_different_metric_axis_is_a_different_cell():
    a = Scope(MetricKind.SPEED, "throughput", "large orgs", Horizon.ONE_TO_3Y)
    b = Scope(MetricKind.COST, "throughput", "large orgs", Horizon.ONE_TO_3Y)
    assert not a.same_cell_as(b)


def test_different_horizon_is_a_different_cell():
    a = Scope(MetricKind.COST, "spend", "large orgs", Horizon.UNDER_1Y)
    b = Scope(MetricKind.COST, "spend", "large orgs", Horizon.OVER_10Y)
    assert not a.same_cell_as(b)


def test_unrelated_domains_are_different_cells():
    a = Scope(MetricKind.COST, "spend", "cloud-native startups", Horizon.UNDER_1Y)
    b = Scope(MetricKind.COST, "spend", "regulated banking estates", Horizon.UNDER_1Y)
    assert not a.same_cell_as(b)


def test_domain_matching_ignores_stopwords_and_case():
    a = Scope(MetricKind.RISK, "exposure", "Teams of the Enterprise", Horizon.IMMEDIATE)
    b = Scope(MetricKind.RISK, "exposure", "enterprise teams", Horizon.IMMEDIATE)
    assert a.same_cell_as(b)
