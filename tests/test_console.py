from intelli_oppo.ui import ASCII, UNICODE, pick_glyphs


def test_force_ascii_wins():
    assert pick_glyphs(force_ascii=True) is ASCII


def test_ascii_glyphs_are_pure_ascii():
    """The fallback exists for consoles that cannot encode the unicode set;
    it defeats the purpose if the fallback itself is non-ascii."""
    for value in (ASCII.verdict, ASCII.beats, ASCII.arrow, ASCII.sep, ASCII.dash):
        value.encode("ascii")


def test_glyph_sets_cover_the_same_slots():
    assert UNICODE.__dataclass_fields__.keys() == ASCII.__dataclass_fields__.keys()
