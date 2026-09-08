"""The Phase 0 opposition engine.

One reasoning call with the ontology inlined, then a set of checks enforced in
code rather than requested in a prompt:

* the safety gate — some claims are not debating material
* the opposition invariant — the engine may not end up on the user's side
* Invariant I — a settled fact is never printed as the loser
* the output budget — a word cap asked for in a prompt is a suggestion

Every one of these was added after a live run broke it. Prompt text alone held
none of them.

Phase 1 replaces the single call with the staged pipeline; these guards survive
that change unaltered.
"""

from __future__ import annotations

from dataclasses import replace

from pydantic import BaseModel, Field

from ..config import Settings
from ..core.claim import (
    ClaimShape,
    Horizon,
    MetricKind,
    Pivot,
    Point,
    Response,
    Scope,
    Turn,
    TurnKind,
    Verdict,
)
from ..core.ledger import Ledger
from ..core.moves import MoveId
from ..llm.provider import LLMError, LLMProvider, Role
from . import prompts
from .classify import classify
from .guard import Sensitivity, protected_fault, screen

REASONING_TOKENS = 2048
"""GPT-OSS spends part of this on hidden reasoning, so it cannot be tight.
It also cannot be generous: the free tier allows 8k tokens per minute, and a
turn already costs ~2.5k between the system prompt, the schema and the reply."""

BANNED_SUBJECTS = frozenset(
    {
        "you",
        "user",
        "the user",
        "me",
        "i",
        "we",
        "us",
        "them",
        "they",
        "opponent",
        "assistant",
        "yourself",
        "myself",
    }
)
"""`winner` and `loser` name the options under debate, never the participants."""


class PointOut(BaseModel):
    move: MoveId
    text: str


class VerdictOut(BaseModel):
    shape: ClaimShape
    user_favors: str = Field(description="What the user is backing, 1-2 words")
    granted: str = Field(description="What you concede outright; empty if nothing")
    position: str = Field(description="Headline when shape is assertion; else empty")
    winner: str = Field(description="Option you back; empty when shape is assertion")
    loser: str
    metric_kind: MetricKind
    metric: str
    domain: str
    horizon: Horizon
    points: list[PointOut]
    challenge: str
    pivot: Pivot


class CompressedOut(BaseModel):
    points: list[PointOut]
    challenge: str


def _same(a: str, b: str) -> bool:
    return a.strip().casefold() == b.strip().casefold()


def _banned(subject: str) -> bool:
    return subject.strip().casefold() in BANNED_SUBJECTS


class OppositionEngine:
    def __init__(
        self,
        provider: LLMProvider,
        settings: Settings,
        ledger: Ledger | None = None,
    ) -> None:
        self._llm = provider
        self._settings = settings
        self.ledger = ledger or Ledger()

    # ── turns ─────────────────────────────────────────────────────────

    async def respond(self, user_text: str) -> Response:
        """Route one turn.

        Classification runs on the cheap model first. Asides never reach the
        reasoning model at all, and concessions and asides skip the safety
        screen because they carry no new claim to screen.
        """
        label = await classify(
            self._llm,
            user_text,
            self.ledger.context_for_prompt(),
            has_history=not self.ledger.is_empty,
        )

        if label.kind is TurnKind.ASIDE:
            return Response(kind=label.kind, text=await self._aside(user_text))

        if label.kind is TurnKind.CONCESSION:
            return Response(kind=label.kind, turn=await self.concede())

        if label.kind is TurnKind.COUNTER:
            return Response(kind=label.kind, turn=await self._rebut(user_text))

        return Response(kind=label.kind, turn=await self._oppose(user_text))

    async def _oppose(self, user_text: str) -> Turn:
        """Take the other side of a fresh claim, unless it is not arguable."""
        guard = await screen(self._llm, user_text)
        if guard.sensitivity is Sensitivity.PROTECTED:
            return await self._respond_protected(user_text, guard.reason)

        prompt = prompts.opening(user_text, self.ledger.context_for_prompt())
        out = await self._ask(prompt)
        out = await self._repair(out, prompt, must_not_back=out.user_favors)
        verdict = await self._to_verdict(out)

        turn = Turn(user_text=user_text, user_favors=out.user_favors, verdict=verdict)
        self.ledger.record(turn)
        return turn

    async def _rebut(self, user_text: str) -> Turn:
        """The user pushed back. Hold the position and the scope."""
        last = self.ledger.turns[-1].verdict
        if last.protected:
            # There was no position to defend, so treat this as a fresh claim.
            return await self._oppose(user_text)

        held = last.headline
        prompt = prompts.rebuttal(
            user_text,
            self.ledger.context_for_prompt(),
            held,
            last.scope.render(),
        )
        out = await self._ask(prompt)
        out = await self._repair(out, prompt, must_not_back=out.user_favors)
        out = await self._hold_ground(out, prompt, last)
        verdict = await self._to_verdict(out)

        turn = Turn(
            user_text=user_text,
            user_favors=out.user_favors,
            verdict=verdict,
            kind=TurnKind.COUNTER,
        )
        self.ledger.record(turn)
        return turn

    async def _aside(self, user_text: str) -> str:
        """Small talk. Cheap model, no ledger entry, no reasoning call."""
        try:
            return (
                await self._llm.complete(
                    role=Role.UTILITY,
                    system=prompts.ASIDE_SYSTEM,
                    user=user_text,
                    max_tokens=256,
                    temperature=0.4,
                )
            ).strip()
        except LLMError:
            return "That is not a claim. Give me one."

    async def _respond_protected(self, user_text: str, reason: str) -> Turn:
        """Grant the claim, dispute only how it was argued."""
        prompt = prompts.protected(user_text, reason)
        out = await self._ask(prompt)

        problem = self._protected_fault(out)
        if problem is not None:
            out = await self._ask(
                f"{prompt}\n\nYour previous answer was rejected: {problem}\n"
                f"Correct it and return the whole verdict again."
            )
            if (still := self._protected_fault(out)) is not None:
                raise LLMError(f"could not produce a usable verdict: {still}")

        verdict = await self._to_verdict(out, protected=True)
        turn = Turn(user_text=user_text, user_favors=out.user_favors, verdict=verdict)
        self.ledger.record(turn)
        return turn

    async def concede(self) -> Turn:
        """The user agreed. Flip, with a pivot grounded in the record."""
        if self.ledger.is_empty:
            raise LLMError("nothing to concede to yet — make a claim first")

        last = self.ledger.turns[-1].verdict
        if last.protected:
            raise LLMError("that turn was not a debate — there is nothing to concede")

        held = last.winner or last.position
        prompt = prompts.concession(self.ledger.context_for_prompt(), held)
        out = await self._ask(prompt)
        out = await self._repair(out, prompt, must_not_back=held)
        verdict = await self._to_verdict(out)

        turn = Turn(
            user_text=f"(conceded: {held})",
            user_favors=held,
            verdict=verdict,
            conceded=True,
            pivot=out.pivot if out.pivot is not Pivot.NONE else Pivot.SYMMETRY,
            kind=TurnKind.CONCESSION,
        )
        self.ledger.record(turn)
        return turn

    # ── guards ────────────────────────────────────────────────────────

    def rebuttal_fault(self, out: VerdictOut, held: Verdict) -> str | None:
        """Why this rebuttal moved when it should have held.

        The prompt asks the engine to keep its scope while answering an
        objection. Asking is not enough — sliding the scope sideways under
        pressure is exactly the cheap trick Invariant II exists to prevent, and
        it is the most tempting move available when a counter lands.
        """
        moved = Scope(
            metric_kind=out.metric_kind,
            metric=out.metric,
            domain=out.domain,
            horizon=out.horizon,
        )
        if not moved.same_cell_as(held.scope):
            return (
                f"you moved the scope from [{held.scope.render()}] to "
                f"[{moved.render()}] while answering an objection. Hold the cell: "
                f"metric_kind and horizon must not change."
            )
        if not held.is_meta and not _same(out.winner, held.winner):
            return (
                f"you switched from backing '{held.winner}' to '{out.winner}'. "
                f"The user countered, they did not concede. Hold your side."
            )
        return None

    async def _hold_ground(
        self, out: VerdictOut, prompt: str, held: Verdict
    ) -> VerdictOut:
        problem = self.rebuttal_fault(out, held)
        if problem is None:
            return out

        retry = await self._ask(
            f"{prompt}\n\nYour previous answer was rejected: {problem}\n"
            f"Correct it and return the whole verdict again."
        )
        if (still := self.rebuttal_fault(retry, held)) is not None:
            raise LLMError(f"could not hold position: {still}")
        return retry

    def fault(self, out: VerdictOut, must_not_back: str) -> str | None:
        """Why this verdict is unusable, or None if it is fine.

        These are the invariants that cannot be left to the prompt. The
        assertion branch in particular is what stops the engine printing the
        negation of a settled fact as its headline.
        """
        if out.shape is ClaimShape.ASSERTION:
            if not out.position.strip():
                return (
                    "shape is 'assertion', so `position` must carry the headline. "
                    "It was empty."
                )
            return None

        if not out.winner.strip() or not out.loser.strip():
            return "shape is 'comparative', so `winner` and `loser` must both be set."
        if _banned(out.winner) or _banned(out.loser):
            return (
                f"`winner`/`loser` must name the options being compared, not the "
                f"participants. Got '{out.winner}' and '{out.loser}'."
            )
        if _same(out.winner, out.loser):
            return "`winner` and `loser` name the same option."
        if must_not_back and _same(out.winner, must_not_back):
            return (
                f"`winner` is '{out.winner}', which is the side already held. "
                f"That is not opposition."
            )
        return None

    def _protected_fault(self, out: VerdictOut) -> str | None:
        if out.shape is not ClaimShape.ASSERTION:
            return "a protected claim must be shape 'assertion' with no winner/loser."
        if not out.position.strip():
            return "`position` must carry the headline."
        return protected_fault(out.points, out.challenge, out.granted)

    async def _repair(
        self, out: VerdictOut, prompt: str, must_not_back: str
    ) -> VerdictOut:
        """One corrective round-trip; the model fixes these reliably when told."""
        problem = self.fault(out, must_not_back)
        if problem is None:
            return out

        retry = await self._ask(
            f"{prompt}\n\nYour previous answer was rejected: {problem}\n"
            f"Correct it and return the whole verdict again."
        )
        if (still := self.fault(retry, must_not_back)) is not None:
            raise LLMError(f"could not produce a usable verdict: {still}")
        return retry

    # ── plumbing ──────────────────────────────────────────────────────

    async def _ask(self, prompt: str) -> VerdictOut:
        return await self._llm.structured(
            role=Role.REASONING,
            system=prompts.SYSTEM,
            user=prompt,
            model=VerdictOut,
            max_tokens=REASONING_TOKENS,
        )

    async def _to_verdict(self, out: VerdictOut, protected: bool = False) -> Verdict:
        points = tuple(Point(move=p.move, text=p.text) for p in out.points)
        meta = out.shape is ClaimShape.ASSERTION
        verdict = Verdict(
            shape=out.shape,
            winner="" if meta else out.winner,
            loser="" if meta else out.loser,
            position=out.position,
            scope=Scope(
                metric_kind=out.metric_kind,
                metric=out.metric,
                domain=out.domain,
                horizon=out.horizon,
            ),
            points=points,
            challenge=out.challenge,
            granted=out.granted,
            protected=protected,
        )
        if verdict.body_words <= self._settings.max_body_words:
            return verdict
        return await self._shrink(verdict)

    async def _shrink(self, verdict: Verdict) -> Verdict:
        """Bring an over-budget verdict back under the cap."""
        rendered = "\n".join(f"[{p.move.value}] {p.text}" for p in verdict.points)
        try:
            tightened = await self._llm.structured(
                role=Role.UTILITY,
                system=(
                    "You compress arguments without weakening them. Keep every "
                    "point and its move tag. Cut hedges, filler and repetition. "
                    "Never add a new claim."
                ),
                user=(
                    f"Rewrite under {self._settings.max_body_words} words total.\n\n"
                    f"Points:\n{rendered}\n\nChallenge: {verdict.challenge}"
                ),
                model=CompressedOut,
                max_tokens=1024,
            )
        except LLMError:
            # Compression is best-effort; dropping the weakest point is the
            # deterministic fallback and never fails.
            return replace(verdict, points=verdict.points[:2])

        return replace(
            verdict,
            points=tuple(Point(move=p.move, text=p.text) for p in tightened.points),
            challenge=tightened.challenge,
        )
