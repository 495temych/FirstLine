# Budget

We spend as little as gets a trustworthy answer, on models, cloud and services alike, because the owner pays for all of it. This file has the principles, which hold for any project. This project's rules and tools for model runs are in `docs/PROCESS.md`, under "Spending".

## Principles

- **Price the question before paying for the answer.** Each run, service or upgrade starts with what it costs and which decision it informs. If the answer wouldn't change a decision, we don't pay for it.
- **Free first, then cheap, then the real thing.** Build and test against fakes and local copies, prove the path on a free tier or a free model, and pay only for the measurement itself.
- **Sample size sets confidence, not budget.** A number's margin comes from how many cases it covers, so we size a run by the margin we need. Money beyond that buys nothing.
- **A cap at the provider too.** Every API key and cloud account carries its own spending limit and a billing alert, so a bug can't drain it.
- **Count every cost.** Retries, failed calls, egress, logs and storage belong in cost per ticket, not just the model's bill.

## Models

- Short, stable prompts, so caching pays. Context that doesn't change the decision is cut.
- The lowest reasoning effort a model offers, unless more measurably helps.
- What code can do runs as code: rules, scoring, yardsticks and embeddings are local and free.
- Free model variants are for smoke tests only. They're rate-limited, can change provider and may keep prompts.
- A cheaper model can cost more through its mistakes, so models are ranked by net saving, not price.

## Cloud and services

- Free tiers first, with each tier's limits written down beside the service in `docs/TECH_STACK.md`.
- Everything runs locally or in memory without its key, so development and tests cost nothing.
- Scale to zero: nothing always-on for a demo.
- One region close to the data, for latency, egress and data protection alike (`docs/SWISS.md`).
- Delete what a sprint no longer uses.

## Concerns

- **Prices drift.** Estimates are checked against the provider's recorded cost after each run.
- **Free tiers end or pause.** A service that pauses idle projects can break a demo, so it's checked before each review, and the local fallback stays working.
