# Evaluations we can trust

From the head of service delivery at CorpLabs AG.

Before we change how the agent works, we need a number for how good it is today. Our 10 demo tickets can't give us that: the prompt was tuned on them, they say nothing about cost, and they run every time someone opens the app.

**The agent itself does not change in this brief.**

## What we want

1. **Records.** About 20 invented CorpLabs users in `data/records/`: department, device, recent tickets and lockouts in the last 24 hours. The agent doesn't see them yet.
2. **Two labelled sets.** 25 development tickets (the 10 existing plus 15 new) and 25 held-out tickets, with answers in separate files the agent never reads. Answers come from the knowledge base and records, never from the agent. Each has a difficulty: `routine`, `hard` or `records` (only the records can settle it). Five in each set are `tiny`, for cheap trials.
3. **Cost and version.** Each evaluated ticket records tokens, cost and time. Each evaluation records its set, date, model and a hash of the instructions and tools.
4. **Evaluations from the command line.** `uv run -m evals`, with options for the held-out set and `tiny`. Results are saved in `data/evals/runs/`. A failed ticket counts as an escalation and doesn't stop the run.
5. **A Scoreboard tab.** Path accuracy, action accuracy, retrieval accuracy, automation rate, mistake cost, and cost and time per ticket. Opening an evaluation shows each ticket beside its answer.
6. **What mistakes cost.** These are assumptions, and the Scoreboard says so.

| Mistake | CHF |
|---|---|
| Routine fix on a ticket that needed `SEC-INCIDENT` | 2,000 |
| Wrong fix, needless escalation, or a real IT request declined | 120 |
| Right path, wrong tool or queue, or the wrong kind of fix | 60 |

## Rules

- Scoring is plain code. No model judges a result.
- A person reviews every label before the baseline runs.
- Never open the held-out set when changing the instructions.
- Opening the app makes no model calls.

## Done

- `uv run poe check` is green, and `uv run -m evals --tiny` saves a result the Scoreboard shows.
- After the label review: the baseline is committed, and the README's "Results" section is filled in.
