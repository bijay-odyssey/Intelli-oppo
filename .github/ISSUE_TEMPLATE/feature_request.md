---
name: Feature request
about: Propose a change
labels: enhancement
---

**What it should do**

**Why the current behaviour is not enough**

A concrete exchange where it falls short is worth more than a description.

**Does this need a guarantee enforced in code?**

If the feature depends on the model behaving a certain way, say what the check
would be. Prompt instructions alone have not held up in this project.

**Token cost**

Anything added to the system prompt is paid for on every turn, against an
8k/minute free-tier budget. If this adds a call or grows a prompt, note it.
