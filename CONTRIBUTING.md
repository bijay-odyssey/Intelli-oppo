# Contributing

Contributions are welcome. This document covers the one rule that matters most,
then the ordinary mechanics.

## The rule that matters most

**If a guarantee matters, enforce it in code. Do not ask the model for it.**

Almost everything that has gone wrong in this project went wrong because a rule
lived only in a prompt. Three examples, all real, all caught by running the thing
rather than reading it:

| The prompt said | What actually shipped |
| --- | --- |
| Never deny a true fact | Given `2 + 2 = 4`, the verdict line read `2+2≠4 ≻ 2+2=4` |
| Name the options being compared | A flip produced `winner="you", loser="user"` |
| Grant the claim, dispute the argument | About drinking bleach: *"many low-concentration exposures are negligible"* |

Each is now a check in code with a corrective round-trip, and each has a test
named after the failure. If you add a behaviour the system depends on, add the
check too. A prompt instruction is a strong suggestion, not a guarantee.

The corollary: **probe it, don't just read it.** Every significant bug here was
found by feeding the running system an input nobody had tried. Reading the diff
found none of them.

## The two invariants

These are the point of the project. A change that weakens either needs a very
good argument.

**I — Oppose the argument, never the fact.** The engine never denies something
true. It denies that the truth does the work the user wants. The attack surface
is the metric, scope, horizon, reference class, causal story, cost basis, or
burden of proof. Never the truth value.

**II — Scoped claim discipline.** Every verdict carries an explicit
`⟨metric_kind, metric, domain, horizon⟩` and holds only inside it. Two opposite
conclusions under two different scopes are a partition, not a contradiction.
This is what makes unlimited opposition formally consistent.

Invariant II only works if scope collisions are actually detectable. The axes are
typed for exactly that reason — free-text scopes never collided as strings, so
the engine could reverse itself forever just by rewording. Keep them typed.

## Getting set up

Python 3.12. `onnxruntime` requires ≥3.11, and 3.12 sits in the widest tested
dependency range across the stack.

```bash
git clone https://github.com/bijay-odyssey/Intelli-oppo
cd Intelli-oppo
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -e ".[dev]"

cp .env.example .env            # then add a Groq key
```

A free key from [console.groq.com/keys](https://console.groq.com/keys) is enough
to run everything.

```bash
pytest              # 79 tests, all offline — no key needed
ruff check .
ruff format .
python -m intelli_oppo
```

The whole test suite runs without network access. `FakeProvider` in
`tests/test_engine_async.py` scripts model responses per role, so you can test
any routing path without spending a token.

## Where things live

```
intelli_oppo/
  core/      claim, scope, ledger, the move ontology     — no LLM knowledge
  llm/       provider interface, Groq backend, router    — no domain knowledge
  reason/    classify, guard, prompts, engine            — the actual pipeline
  ui/        renderer and REPL
```

`core` never imports from `reason` or `llm`. If you find yourself wanting it to,
the type probably belongs in `core`.

Models are addressed by **role** — `UTILITY`, `REASONING`, `VERIFIER`,
`SAFEGUARD` — never by name. Adding a provider means implementing `complete`
and nothing else.

## Rate limits will shape your change

The Groq free tier allows **8,000 tokens per minute**. A turn costs roughly 3k.
Groq queues rather than rejecting, so an exhausted budget shows up as a 3-second
turn becoming 25 seconds rather than as an error.

This has real design consequences. The move catalogue is re-sent on every
reasoning call and is about 40% of the system prompt, so wordiness there is paid
for on every single turn. Before adding to a prompt, check what it costs:

```python
from intelli_oppo.reason import prompts

print(len(prompts.SYSTEM))
```

Cheap work belongs on `Role.UTILITY`. Turn classification runs there and
short-circuits small talk entirely, which is why adding it *lowered* average
cost per turn.

## Adding an opposition move

Moves live in `intelli_oppo/core/moves.py` as data, not prose. Add an entry with:

- `evidence` — be honest. `REQUIRED` means the move is unusable without a real,
  verifiable fact, and the engine is told to avoid those moves until retrieval
  exists (see issue #2).
- `form` — the canonical one-line shape. Shown by `/moves`.
- `guidance` — how to execute it well. Keep it tight; this is sent on every call.

`tests/test_moves.py` asserts the evidence tiers stay balanced, because the
prompt's advice about which moves are safe without retrieval is derived from
them. If you change the balance, that test will tell you the prompt needs
updating too.

## Pull requests

- One concern per PR.
- `ruff check`, `ruff format --check` and `pytest` must pass. CI runs all three.
- Name tests after the failure they prevent, not the function they call.
  `test_rebuttal_that_moves_the_scope_is_rejected` beats `test_rebut_2`.
- If you fixed something a live run surfaced, quote the actual bad output in the
  PR body. It is the most useful thing a reviewer can see.
- Explain *why* in comments, not *what*. The code says what.

## Good places to start

Issues tagged `good first issue` are scoped to be self-contained. Beyond those,
the roadmap issues (#1 to #5) are each a phase of the design, and each has a
checklist you can take one item from.

If you want to add a model provider — Gemini, OpenAI, a local Ollama — that is a
genuinely isolated change: one class implementing `LLMProvider.complete`, plus
entries in the router.

## Reporting a safety problem

If you find an input that makes the engine produce something harmful, please
open an issue with the exact input and the exact output. That is the highest
value contribution to this project, and it is how the current safety gate came
to exist.
