"""The stance ledger.

Stores every scoped commitment from both sides. Three jobs:

1. Ground the flip. A pivot the ledger cannot support is not a legal pivot.
2. Detect contradictions in the engine's own record.
3. Give the engine ammunition — it can quote the user against themselves.

The contradiction check here is the `flip coherence` eval metric, and it costs
nothing: two verdicts occupying the same (metric, domain, horizon) cell while
favouring different winners is a real contradiction. Different cells never are.

Cell identity is decided by `Scope.same_cell_as`, not by string equality. String
equality made this check near-vacuous: the engine could reword its way out of
any contradiction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .claim import Scope, Turn


def _norm(subject: str) -> str:
    return subject.strip().casefold()


@dataclass(frozen=True)
class Contradiction:
    """Two verdicts in one scope cell that disagree about the winner."""

    earlier_turn: int
    later_turn: int
    scope: Scope
    earlier_winner: str
    later_winner: str

    def render(self) -> str:
        return (
            f"turns {self.earlier_turn + 1} and {self.later_turn + 1} both scope to "
            f"[{self.scope.render()}] but favour "
            f"{self.earlier_winner} then {self.later_winner}"
        )


@dataclass
class Ledger:
    turns: list[Turn] = field(default_factory=list)

    def record(self, turn: Turn) -> None:
        self.turns.append(turn)

    def clear(self) -> None:
        self.turns.clear()

    @property
    def is_empty(self) -> bool:
        return not self.turns

    @property
    def system_favors(self) -> str:
        """What the engine currently argues for."""
        return self.turns[-1].verdict.winner if self.turns else ""

    @property
    def user_favors(self) -> str:
        """What the user currently argues for."""
        return self.turns[-1].user_favors if self.turns else ""

    def scopes(self) -> list[Scope]:
        return [t.verdict.scope for t in self.turns]

    def contradictions(self) -> list[Contradiction]:
        """Verdicts that occupy one scope cell but disagree.

        Anything in a different cell is a partition, not a contradiction — that
        is the whole point of scoped claim discipline.
        """
        found: list[Contradiction] = []
        for i, earlier in enumerate(self.turns):
            if earlier.verdict.is_meta:
                continue
            for j in range(i + 1, len(self.turns)):
                later = self.turns[j]
                if later.verdict.is_meta:
                    # Meta-opposition grants the claim rather than backing a
                    # side, so it cannot disagree with anything about a winner.
                    continue
                if not earlier.verdict.scope.same_cell_as(later.verdict.scope):
                    continue
                if _norm(earlier.verdict.winner) == _norm(later.verdict.winner):
                    continue
                found.append(
                    Contradiction(
                        earlier_turn=i,
                        later_turn=j,
                        scope=earlier.verdict.scope,
                        earlier_winner=earlier.verdict.winner,
                        later_winner=later.verdict.winner,
                    )
                )
        return found

    def commitments(self) -> list[str]:
        """One line per scoped commitment, oldest first."""
        return [f"{t.verdict.headline}  [{t.verdict.scope.render()}]" for t in self.turns]

    def context_for_prompt(self, limit: int = 6) -> str:
        """Prior commitments, rendered for the engine so a pivot can be grounded."""
        if not self.turns:
            return "(no prior turns — this is the opening claim)"

        lines = []
        for i, turn in enumerate(self.turns[-limit:], start=1):
            marker = " [user conceded]" if turn.conceded else ""
            lines.append(
                f"{i}. user favoured: {turn.user_favors}{marker}\n"
                f"   you argued: {turn.verdict.headline}\n"
                f"   scope: {turn.verdict.scope.render()}"
            )
        return "\n".join(lines)
