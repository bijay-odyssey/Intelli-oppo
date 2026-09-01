"""Terminal rendering.

The output contract uses ✗ ≻ ⟶ ·, and a default Windows console on cp1252
mangles all of them. So: reconfigure stdout to UTF-8 where possible, probe
whether the glyphs actually survive encoding, and fall back to ASCII when they
do not. Cheap here, tedious to retrofit later.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from rich.console import Console
from rich.padding import Padding
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from ..core.claim import Turn, Verdict
from ..core.ledger import Ledger

THEME = Theme(
    {
        "thesis": "bold #4C8FCC",
        "anti": "bold #D45C6E",
        "gate": "#5FA981",
        "faint": "dim",
        "move": "italic #8A929E",
    }
)

MAX_WIDTH = 96
"""Cap the reading measure. A verdict sprawled across 200 columns is unreadable."""


@dataclass(frozen=True)
class Glyphs:
    verdict: str
    beats: str
    arrow: str
    sep: str
    dash: str


UNICODE = Glyphs(verdict="✗", beats="≻", arrow="⟶", sep="·", dash="—")
ASCII = Glyphs(verdict="X", beats=">", arrow="->", sep="-", dash="-")

_PROBE = "✗≻⟶·—"


def enable_utf8() -> None:
    """Best-effort switch of stdio to UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass


def supports_unicode() -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        _PROBE.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def pick_glyphs(force_ascii: bool = False) -> Glyphs:
    if force_ascii:
        return ASCII
    return UNICODE if supports_unicode() else ASCII


class Renderer:
    INDENT = 7

    def __init__(self, force_ascii: bool = False) -> None:
        enable_utf8()
        self.g = pick_glyphs(force_ascii)
        self.console = Console(theme=THEME, highlight=False)
        if self.console.width > MAX_WIDTH:
            self.console.width = MAX_WIDTH

    # ── plumbing ──────────────────────────────────────────────────────

    def print(self, text: str = "") -> None:
        self.console.print(text)

    def _indented(self, renderable) -> None:
        """Print wrapped at the body indent, so continuation lines line up."""
        self.console.print(Padding(renderable, (0, 0, 0, self.INDENT)))

    def _glyphed(self, text: str) -> str:
        """Swap data-level glyphs for whatever this terminal can encode."""
        return text.replace("≻", self.g.beats)

    # ── the verdict ───────────────────────────────────────────────────

    def verdict(self, turn: Turn) -> None:
        v: Verdict = turn.verdict
        g = self.g

        self.console.print()
        head = Text(f"IO   {g.verdict}  ", style="faint")
        head.append(self._glyphed(v.headline), style="anti")
        self.console.print(head)

        self._indented(Text(f"{g.dash} scoped to: {v.scope.render()}", style="faint"))

        if v.granted:
            self.console.print()
            granted = Text("granted: ", style="gate")
            granted.append(v.granted)
            self._indented(granted)

        if turn.conceded:
            self.console.print()
            self._indented(
                Text(f"pivot: {turn.pivot.value.replace('_', ' ')}", style="faint")
            )

        self.console.print()
        self._indented(self._points_table(v))

        self.console.print()
        challenge = Text(f"{g.arrow} ", style="thesis")
        challenge.append(v.challenge)
        self._indented(challenge)
        self.console.print()

    def _points_table(self, v: Verdict) -> Table:
        """Two columns so wrapped point text hangs under itself, not under the number."""
        table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 0, 0, 0))
        table.add_column(width=3, no_wrap=True, style="faint")
        table.add_column(overflow="fold", ratio=1)
        for i, point in enumerate(v.points, start=1):
            body = Text(point.text.strip())
            body.append(f"  [{point.move.value}]", style="move")
            table.add_row(f"{i}.", body)
        return table

    # ── inspection commands ───────────────────────────────────────────

    def scope(self, ledger: Ledger) -> None:
        if ledger.is_empty:
            self.console.print("[faint]no scope yet — make a claim first[/faint]")
            return
        current = ledger.turns[-1].verdict.scope
        self.console.print()
        for label, value in (
            ("metric ", current.metric),
            ("domain ", current.domain),
            ("horizon", current.horizon),
        ):
            line = Text(f"{label}  ", style="faint")
            line.append(value)
            self.console.print(Padding(line, (0, 0, 0, 2)))
        self.console.print()

    def ledger(self, ledger: Ledger) -> None:
        if ledger.is_empty:
            self.console.print("[faint]ledger is empty[/faint]")
            return

        self.console.print()
        self.console.print("[faint]scoped commitments[/faint]")
        for i, line in enumerate(ledger.commitments(), start=1):
            self.console.print(Padding(Text(f"{i}. {self._glyphed(line)}"), (0, 0, 0, 2)))

        contradictions = ledger.contradictions()
        self.console.print()
        if contradictions:
            self.console.print("[anti]contradictions[/anti]")
            for c in contradictions:
                self.console.print(Padding(Text(c.render()), (0, 0, 0, 2)))
        else:
            self.console.print(
                "[gate]no contradictions[/gate] "
                "[faint]— every verdict sits in its own scope[/faint]"
            )
        self.console.print()

    def moves(self) -> None:
        from ..core.moves import MOVES, Evidence

        colours = {
            Evidence.NONE: "gate",
            Evidence.SOME: "faint",
            Evidence.REQUIRED: "anti",
        }
        table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2, 0, 0))
        table.add_column(style="move", no_wrap=True)
        table.add_column(no_wrap=True)
        table.add_column(no_wrap=True)
        for move in MOVES.values():
            table.add_row(
                move.id.value,
                move.attacks,
                Text(move.evidence.value, style=colours[move.evidence]),
            )

        self.console.print()
        self.console.print(Padding(table, (0, 0, 0, 2)))
        self.console.print()
        self.console.print(
            "  [faint]evidence: what the move needs before it may be used. "
            "The four marked 'none' are the fabrication floor.[/faint]"
        )
        self.console.print()

    # ── messages ──────────────────────────────────────────────────────

    def error(self, message: str) -> None:
        line = Text("! ", style="anti")
        line.append(message)
        self.console.print(line)

    def info(self, message: str) -> None:
        self.console.print(Text(message, style="faint"))
