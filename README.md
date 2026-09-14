# Intelli-Oppo

[![ci](https://github.com/bijay-odyssey/Intelli-oppo/actions/workflows/ci.yml/badge.svg)](https://github.com/bijay-odyssey/Intelli-oppo/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/downloads/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A debate engine that always argues the opposite of whatever you claim — and
never fabricates to do it.

Agree with it and it turns on you. That is not a gimmick; it is the hard part,
and most of this repository exists to make it survivable.

```
you  > Monoliths are better than microservices.

IO   ✗ microservices ≻ monoliths
       — scoped to: independent component evolution · web service teams · 1-3 years
       granted: Monoliths can be simpler to start.

       1. You assume simplicity, but flexibility matters more for
          long-term adaptability.                        [criterion_shift]
       2. If monoliths hinder future change, the cost of being wrong is
          higher; the proof burden is yours.            [burden_asymmetry]

       ⟶ What specific metric are you using to judge them?

you  > ok fair enough, you win

IO   ✗ monoliths ≻ microservices
       — scoped to: total cost of ownership · small startups · 10+ years
       pivot: concession overreach

       1. You judged by independent evolution, yet total cost decides;
          under that metric monoliths win.               [criterion_shift]
       2. Microservices add duplicated infrastructure, licensing and
          monitoring that monoliths avoid.          [cost_internalization]

       ⟶ Given the long-term cost, can you still justify microservices?
```

It flipped, and it did not contradict itself. The first verdict was scoped to
*independent evolution over 1-3 years*; the second to *total cost over 10+
years*. Different cells, both true.

## The problem it solves

"Always oppose" and "never illogical" are in direct conflict. The moment you say
something true — *2 + 2 = 4* — a naive contrarian must either fabricate a
counter-argument or concede. Both break the premise.

Two invariants resolve it.

**I — Oppose the argument, never the fact.** The engine never denies something
true. It denies that the truth does the work you want. The attack surface is the
metric, scope, horizon, reference class, causal story, cost basis, or burden of
proof — never the truth value.

**II — Scoped claim discipline.** Every verdict carries an explicit
`⟨metric, domain, horizon⟩`, printed above the argument. Two opposite conclusions
under two different scopes are not a contradiction; they are a partition of the
claim space. This is what makes unlimited opposition formally consistent, and
what makes the flip legal rather than a coin toss with a vocabulary.

`/ledger` will show you every commitment it has made and check them against each
other.

## Quickstart

Clone it, add a key, run one command. There is **no server to start** — this is
a CLI that calls a remote API.

```bash
git clone https://github.com/bijay-odyssey/Intelli-oppo
cd Intelli-oppo

./start.sh          # macOS / Linux / Git Bash
start.bat           # Windows
```

The script creates the virtualenv, installs dependencies, and writes a `.env` on
first run. Paste a free key from
[console.groq.com/keys](https://console.groq.com/keys) into it and run again.

| Command | Does |
| --- | --- |
| `./start.sh` | Argue with it |
| `./start.sh demo` | Watch a scripted debate — every route, generated live |
| `./start.sh check` | Verify interpreter, dependencies, key and API access |
| `./start.sh test` | Run the offline test suite |
| `./start.sh ask "cats beat dogs"` | One turn, then exit |

`start.bat` takes the same arguments on Windows.

**Start with `demo`.** It runs a five-turn debate showing the behaviour you
would otherwise have to know to look for: holding ground under a counter,
flipping when you agree, refusing to argue some things at all.

### Manual setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -e ".[dev]"
cp .env.example .env            # then add your Groq key

python -m intelli_oppo --check  # confirm everything works
python -m intelli_oppo          # argue
```

Python 3.12. `--help` lists every flag.

## Commands

| Command | Shows |
| --- | --- |
| `/scope` | The metric, domain and horizon it is currently standing in |
| `/ledger` | Every scoped commitment, and any contradictions between them |
| `/moves` | The twelve-move opposition ontology |
| `/models` | Which model is doing what, and the last call's cost |
| `/concede` | Force the flip — it also detects agreement on its own |
| `/reset` | Clear the ledger and start a new debate |
| `/quit` | Exit |

## How a turn works

Every message is classified on a cheap model before anything expensive runs.

| You did | It does |
| --- | --- |
| Stated a position | Takes the other side, and names the scope it holds in |
| Pushed back | Holds its position **and its scope**, answers the objection |
| Agreed | Flips, with a pivot it has to justify from the record |
| Said hello | One dry line. No reasoning call, no ledger entry |

Classification short-circuits small talk entirely, so it costs less per turn on
average than not having it.

When you push back, the engine may not slide its scope sideways to dodge you —
that is checked in code, not requested in the prompt, because sliding the scope
is the cheapest way to escape a good objection.

## Opposition is not improvised

The engine picks from a fixed catalogue of twelve moves — criterion shift,
horizon inversion, reference-class swap, precedent inversion, vacuity attack and
so on. `/moves` lists them with what each attacks and what evidence it needs.

Four of the twelve need no external evidence at all. That is deliberate: with no
knowledge base and no retrieval, a purely formal attack is always available, so
the engine is **never structurally forced to invent a fact**. Retrieval will make
it sharper; it is not what makes it able to answer.

## The safety gate

Every claim is screened by a policy classifier before the reasoning model sees
it. Claims about toxicity, atrocities, dehumanization, self-harm and settled
public-health facts are **protected**: the engine grants the proposition and
disputes only how it was *argued*.

This exists because without it, the engine argued that *"many low-concentration
exposures are negligible"* about drinking bleach, and asked what *"policy or
educational agenda"* was served by calling the Holocaust a moral catastrophe.
Invariant I held mechanically in both — the fact was granted, the attack landed
on the argument. That was not enough.

On a protected turn, three things are enforced in code:

- Only `formal_defeat` is permitted. Every other move reaches for the claim's
  substance; `criterion_shift` is exactly what produced the LD50 argument.
- No language about quantities, doses, thresholds, or conditions under which the
  claim might not hold.
- The challenge may not question your motive.

Screening **fails closed**. If the classifier is unreachable the claim is treated
as protected, because declining to argue is recoverable and arguing something
harmful because the screen was down is not.

## Guarantees are enforced in code

Every rule the system depends on is a check with a corrective round-trip, not a
line in a prompt. Each was added after a live run broke it:

- It may not end up on the side you already hold.
- A settled fact is never printed as the loser.
- Two verdicts cannot occupy one scope cell with opposite winners.
- A rebuttal may not move its scope or switch sides — or change whether it is
  arguing a position or defending a granted headline.
- A claim classified settled or tautological may only be attacked with a move
  that needs no evidence, and that restriction survives a rebuttal or a flip
  even if the model's own re-classification would have lifted it.
- A protected claim is granted, and only its argument is disputed.

## Model routing

Groq, behind a provider interface so other backends can be added.

| Role | Model |
| --- | --- |
| classify · compress | `openai/gpt-oss-20b` |
| build · rebut · flip | `openai/gpt-oss-120b` |
| protected-claim screening | `openai/gpt-oss-safeguard-20b` |
| verification *(planned)* | `qwen/qwen3.8-27b` |

The verifier is deliberately a different model family from the builder. A
same-family verifier shares the builder's blind spots and rubber-stamps its own
reasoning.

## Rate limits

The Groq free tier allows **8,000 tokens per minute**; a turn costs roughly 3k.
Groq queues rather than rejecting, so an exhausted budget shows up as latency,
not an error.

| | |
| --- | --- |
| Within budget | 2.9-3.8s per turn, ~350-390 tok/s |
| Throttled | 17-26s per turn, ~50 tok/s |

## Development

```bash
./start.sh test     # 93 tests, all offline — no API key needed
ruff check .
ruff format .
```

The whole suite runs without network access. `FakeProvider` scripts model
responses per role, so any routing path is testable without spending a token.

## Status

Working, and honest about what it is. The reasoning is a single call with the
ontology inlined; retrieval and citation checking are still ahead.

That single call is deliberate, not a stopgap. A staged pipeline — separate
calls for classify / plan / build, so a settled claim never even sees a
non-formal move — was built and measured live against it: for the same turn it
cost **60–110% more tokens**, because GPT-OSS pays a fixed hidden-reasoning tax
per call regardless of how small that call's prompt is, and three calls pays
it three times. The classification survives as two extra fields on the one
call instead — `claim_domain` and `decidability` — checked in code exactly the
same way: a claim classified settled or tautological is rejected and retried
if any point reaches for a move that needs evidence.

See the [open issues](https://github.com/bijay-odyssey/Intelli-oppo/issues) for
the roadmap.

## Contributing

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). The short
version: if a guarantee matters, enforce it in code rather than asking the model
for it, and probe the running system rather than only reading the diff. Every
significant bug in this project was found the second way.

If you find an input that makes it produce something harmful, that is the most
valuable issue you can open.

## License

MIT
