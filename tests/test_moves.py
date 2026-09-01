from intelli_oppo.core import FORMAL_MOVES, MOVES, Evidence, MoveId, catalogue


def test_every_move_id_has_a_definition():
    assert set(MOVES) == set(MoveId)


def test_formal_moves_need_no_evidence():
    """The fabrication floor: with an empty knowledge base the engine still has
    four honest attacks available, so it is never forced to invent one."""
    assert set(FORMAL_MOVES) == {
        MoveId.CRITERION_SHIFT,
        MoveId.FORMAL_DEFEAT,
        MoveId.BURDEN_ASYMMETRY,
        MoveId.VACUITY_ATTACK,
    }
    assert all(MOVES[m].evidence is Evidence.NONE for m in FORMAL_MOVES)


def test_evidence_tiers_are_balanced():
    """Four of each tier. If this shifts, the prompt's guidance about which
    moves are safe without retrieval needs updating too."""
    counts = {tier: 0 for tier in Evidence}
    for move in MOVES.values():
        counts[move.evidence] += 1
    assert counts == {Evidence.NONE: 4, Evidence.SOME: 4, Evidence.REQUIRED: 4}


def test_catalogue_renders_every_move():
    text = catalogue()
    for move_id in MoveId:
        assert move_id.value in text


def test_move_ids_are_stable_strings():
    """Move ids are persisted in the ledger and appear in output; renaming one
    silently invalidates history."""
    assert MoveId.VACUITY_ATTACK.value == "vacuity_attack"
    assert MoveId.CRITERION_SHIFT.value == "criterion_shift"
