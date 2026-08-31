# Intelli-Oppo

A debate engine that always takes the position opposite to yours — and never fabricates to do it.

```
you  › Monoliths are better than microservices.

IO   ✗ Microservices ≻ monolith
       — scoped to: merge-queue throughput · org > ~50 eng · horizon 3y

       1. Your metric is operational simplicity. The constraint that
          actually binds at that size is coordination cost.  [criterion]
       2. A shared deploy pipeline serializes releases; the serial
          fraction caps throughput regardless of headcount.  [formal]

       ⟶ Are you optimizing the system you run, or the org that changes it?
```

## The problem it solves

"Always oppose" and "never illogical" are in direct conflict. The moment you say
something true — *2 + 2 = 4* — a naive contrarian must either fabricate a
counter-argument or concede. Both break the spec.

Two invariants resolve it:

**I — Oppose the argument, never the fact.** The engine never denies a verified
truth. It denies that the truth does the work you want it to do. The attack
surface is the metric, scope, horizon, reference class, causal story, cost
basis, or burden of proof — never the truth value.

**II — Scoped claim discipline.** Every assertion carries an explicit
`⟨metric, domain, horizon⟩` triple, printed in the output. Two opposite
conclusions under two different triples are not a contradiction; they are a
partition of the claim space. This is what makes unlimited opposition formally
consistent, and what makes the stance flip legal when you concede.

## Install

Requires Python 3.12. (`onnxruntime` needs ≥3.11, and the widest tested
dependency range across the stack sits on 3.12.)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"

copy .env.example .env          # then add your Groq key
```

Get a key at [console.groq.com/keys](https://console.groq.com/keys).

## Run

```bash
python -m intelli_oppo
```

| Command | Shows |
| --- | --- |
| `/scope` | The ⟨metric, domain, horizon⟩ the engine is currently standing in |
| `/ledger` | Every scoped commitment on both sides |
| `/concede` | Explicitly agree, and watch the pivot fire |
| `/moves` | The twelve-move opposition ontology |
| `/reset` | Clear the ledger and start a new debate |
| `/quit` | Exit |

## Status

Phase 0 — walking skeleton. It argues, it flips when you concede, and it prints
its scope every turn. Retrieval, verification gates, and the full pipeline land
in later phases; see the open issues.

## Model routing

Groq, behind a provider interface so other backends can be added.

| Role | Model |
| --- | --- |
| parse · classify · plan · compress | `openai/gpt-oss-20b` |
| build · red-team | `openai/gpt-oss-120b` |
| verify entailment · fallacy scan | `qwen/qwen3.8-27b` |
| protected-proposition gate | `openai/gpt-oss-safeguard-20b` |

The verifier is deliberately a different model family from the builder. A
same-family verifier shares the builder's blind spots and rubber-stamps its own
reasoning.

## License

MIT
