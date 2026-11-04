# Roadmap

TriagePilot is an L1 IT support agent for a Swiss IT service provider, built as a portfolio project for Zurich employers. UnderCover is the model for the engineering practice, not the product.

**The idea: the agent proposes, the system enforces, and a scoreboard proves it works.**

## The product

| | Triage (workflow) | Inbox (agent loop) |
|---|---|---|
| Work | One ticket | A batch, N at once |
| LLM calls | Exactly 1 | Several, up to a cap |
| Context | Fetched by code | Looked up by the agent |
| Approval | Confirmation card | Review queue |

Both produce the same decision format, follow the same rules in the same backend, and are scored on the same tickets.

## The briefs

1. ~~FOUNDATION~~: packages, checks, CI, docs. Done.
2. **EVALS**: records, labelled tickets, cost tracking, Scoreboard. Today's agent becomes the baseline.
3. **BACKEND**: FastAPI, SQLite tickets, audit trail, rules enforced in code. Triage gets the user's records.
4. **AGENT**: the loop with read-only tools, the Inbox tab, a dispatcher with no model, a review queue.
5. **HARDEN**: traces, budget cap, prompt-injection tests, personal data out of logs.
6. **SWISS**: German tickets, a second client, costs in CHF, hosted demo.

Each brief stays under a page. HARDEN and SWISS start only once batch works end to end.

## The demo this builds toward

Load 25 tickets, some in German, one with a prompt injection. Agents work them at once. Code blocks a repeat lockout, even if the model proposes an unlock. A technician approves the rest. The Scoreboard shows accuracy, cost per ticket and CHF saved.

## Not for now

Sign-in, cloud databases, AWS, a React dashboard, agents that rewrite their own prompts, real integrations.
