# Delivery framework

Three phases take an AI use case from an idea to a system a client runs without us. Each phase answers one question, in the order the risk falls: does it work, does it run, and can a client trust it. A phase ends at a gate, which is a decision backed by evidence, not a date.

The framework is project-agnostic. `docs/ROADMAP.md` is FirstLine's instance of it, with one sprint per phase. Another project can copy this file, keep the phases and gates, and write its own commits under each workstream.

## Phase 1: Prove it

**Feasibility, on one machine.** Is the use case worth automating, with which design and model, and at what cost?

| Workstream | What it settles |
|---|---|
| Use case and money | The process, the one decision to automate, what it costs by hand today, what a mistake costs, and success criteria in the client's currency |
| Data and exam | The knowledge the agent may use, labelled cases in fixed splits, a held-out set opened once, and free yardsticks to beat |
| Core functionality | The smallest version that does the job end to end: one model call, a structured decision, the actions it may propose, rules enforced in code, and a person's approval before anything runs |
| Budget | Cost per case and per year, a spending cap, and the cost of each experiment estimated before it runs |
| Design and model evaluation | Designs, such as one call against an agent loop, and models compared on the task itself, ranked by net value with margins of error, by a rule written before the runs |

- **Where it runs:** a laptop, model APIs, local files and local embeddings. No managed services yet.
- **Gate:** a written go or no-go. It beats the yardsticks in net value by more than the margin, the design and model are chosen with their reasons, the cost per case is known, and so are the main ways it fails.
- **What's left behind:** an evaluation harness, saved runs that can be re-scored for free, a decision log and a minimal interface to try it.

## Phase 2: Make it a system

**Integrate and extend.** Can it run the real workflow, observed, durable and usable by the people who own it?

| Workstream | What it settles |
|---|---|
| Observability | One trace per case, experiments on saved datasets, and people's verdicts as scores |
| System of record | Cases, decisions, reviews and an audit trail in a database, with checkpoints that survive a restart |
| Search | The knowledge in a search index, with keyword and meaning search, scored as before |
| Tools and protocols | Read-only lookup tools served through a protocol such as MCP, and richer behaviour, such as a conversation, measured against Phase 1's baseline |
| The workflow | The human's step, such as a review queue, plus views that explain the system and show the business case live |
| Reliability | Retries, no repeated actions, spending limits per batch, and evaluations as a release gate |

- **Where it runs:** a laptop with managed services in the right region. Tests stay free and offline.
- **Gate:** the real workflow runs end to end, every case is traced, the system survives a restart, and measured human time confirms or revises Phase 1's economics.

## Phase 3: Deliver it

**Production, security and handover.** Could the client run it safely in their own cloud, without us?

| Workstream | What it settles |
|---|---|
| Security | A threat model, checks for personal data and secrets, a shield against hidden instructions, a set of attack cases, and an autonomy level for each action |
| Infrastructure | One container image, infrastructure as code, secrets in a vault, a managed identity, and the data kept where the client's rules say |
| Cost control | A gateway with rate limits and token budgets, budget alerts, and a one-command teardown |
| Operations | Monitoring, a runbook, an incident path, and the release gate in CI |
| Handover | Measures against Phase 1's baseline, a named owner for each responsibility, documentation and a short demo |

- **Where it runs:** the client's cloud.
- **Gate:** it's hosted, secured and within budget, the client could operate it, and its numbers are measured against Phase 1's baseline.

## Rules across all three phases

- **One increment at a time.** Each commit ships one working, tested version, shown before the next.
- **Measure every change.** Before and after, against cost and noise, and write down the decision with its trade-off.
- **Spend on purpose.** Estimate before a run, try samples first, and re-score saved runs before re-running.
- **Decide where data may go** before adding a service or a provider.
- **Answer each phase's question with that phase's tools.** Don't build Phase 2's infrastructure to answer a Phase 1 question, and don't polish Phase 3 before Phase 2's gate.
- **Phases can overlap** when the owner decides, such as building the system before the last experiment. The gates still close in order.
