# Roadmap

TriagePilot is an L1 IT support agent for a Swiss IT service provider. It is built as a portfolio project for Swiss employers, using UnderCover's engineering practices without copying its product.

## The product we are heading to

Two tabs show two ways of working, on the same tickets and the same rules.

- **Triage** is the demo. One ticket, one LLM call. Code retrieves the knowledge base and looks up the user first, and the model decides in a single pass.
- **Inbox** is the realistic case. A batch of tickets, N at once, each worked by an agentic loop. The agent investigates with read-only tools, then submits its decision.

Two more tabs support them: **Scoreboard** for evaluation results and **Ops** for cost, errors and traces.

## The design that keeps this simple

- **One decision format.** Both modes produce the same result: path, tool, queue, priority and reasoning. Evals, the backend and the review queue don't care which mode made it.
- **The agent proposes, the code decides.** The agent can only read and propose. Every rule is checked in the backend after the model answers, in both modes. No fix runs without a technician's approval.
- **The scoreboard settles the argument.** Single-shot and the loop run on the same labelled tickets, so accuracy, cost and time can be compared directly.

| | Triage tab | Inbox tab |
|---|---|---|
| Tickets | One at a time | A batch, N at once |
| LLM calls | Exactly 1 | Several, up to a cap |
| Context | Fetched by code | Looked up by the agent |
| Approval | Confirmation card | Review queue |
| Rules | Backend | Same backend |

## The briefs

Each brief is planned, built and checked on its own, and each reacts to what the last one taught us.

1. **FOUNDATION**: packages, uv, `poe check`, pre-commit hook, GitHub Actions, `MODEL_NAME`, core docs. No visible change.
2. **EVALS**: a small seed of users, devices and lockout history, about 25 + 25 labelled tickets with the answers kept from the agent, tokens and cost per call, the prompt version on every run, and the Scoreboard tab. Single-shot becomes the baseline.
3. **BACKEND**: FastAPI with about 8 routes, SQLite tickets and an audit trail. Rules are enforced here, so SEC-04 lockouts always go to `SEC-INCIDENT`. Streamlit and the agent both go through the API.
4. **LOOP**: read-only tools (knowledge base search, user, device, past tickets), one `submit_decision` tool, and a cap on model calls. A refusal from the backend goes back to the model. The loop is scored against single-shot.
5. **BATCH**: the Inbox tab and a dispatcher with no model. It runs N tickets at once, with live status and a review queue. One bad ticket never stops a batch, and no fix runs twice.
6. **RELIABILITY**: traces, a budget cap per batch, a stop after repeated API failures, the Ops tab, and Docker Compose.
7. **SECURE**: prompt-injection tests and personal data removed from logs and traces.
8. **SWISS**: German tickets, a second client with its own knowledge base and rules, costs in CHF, and a hosted demo.

Briefs 1 to 5 are the core. Briefs 6 to 8 stay thin, and none of them starts before batch works end to end.

## Trials stay cheap

Evaluations get a `tiny` set of 5 tickets for trial runs, as UnderCover has. Full runs happen only when a change is ready to be compared.

## Not for now

- Sign-in, cloud databases and AWS
- A React dashboard
- An agent that rewrites its own prompts
- Real integrations: every tool stays simulated

## Open at the end

Which mode wins, if either. The scoreboard decides, and the result goes in the README whichever way it falls.
