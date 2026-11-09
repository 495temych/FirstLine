# FirstLine

**An AI first pass for every IT ticket: proven with evals, enforced in code, traced end to end, and running on Azure.**

I worked in L1 IT support. FirstLine is how I'd now put AI into a service desk, and the method carries over to any business process. The client is CorpLabs AG, a fictional company in Zürich, and the 745 tickets are synthetic.

## Four promises

| Promise | The client's question | What you can see |
|---|---|---|
| **Proven** | Is it better than what we have, and what does it cost? | Is it worth it?: the agent against two free yardsticks, in CHF, with margins of error, and the models compared |
| **Safe** | Can it do something dangerous? | The agent proposes, code enforces, and a person approves every fix |
| **Observable** | Can we see why it decided? | Every decision traced, from what it read to what a person did *(Sprint 2)* |
| **Shippable** | Can it run in our cloud, within budget? | Azure Container Apps, Key Vault, API Management, and Claude through Microsoft Foundry *(Sprint 3)* |

## Two modes

- **The Assistant:** an employee describes a problem and gets an answer while they wait. Routine fixes need their confirmation, and anything touching access or security becomes a ticket.
- **The Queue:** a technician's morning batch, pre-triaged by an agent that investigates with read-only tools. The technician approves, corrects or rejects each decision *(Sprint 2)*.

## The method

1. **Frame the money.** Minutes saved, review time, mistake costs and break-even, in francs. See [the business goal](docs/BUSINESS_GOAL.md).
2. **Define the exam.** Labelled tickets, a held-out set opened once, and two free yardsticks to beat.
3. **Build the baseline.** One model call with a structured decision, before anything clever. See [Results](#results).
4. **Enforce rules in code.** The model proposes. Code and people decide what runs.
5. **Experiment.** Change one thing, measure it against cost and noise, and write the decision down. See [the decisions](docs/DECISIONS.md).
6. **Ship and watch.** Trace every decision, cap the spend, and hand it over.

[The roadmap](docs/ROADMAP.md) shows where each step stands.

---

## Architecture

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	retrieve(retrieve)
	triage(triage)
	no_tools(no_tools)
	confirm_fix(confirm_fix)
	confirm_ticket(confirm_ticket)
	self_serve_wait(self_serve_wait)
	execute_tool(execute_tool)
	draft_ticket(draft_ticket)
	create_ticket(create_ticket)
	log(log)
	__end__([<p>__end__</p>]):::last
	__start__ -.-> no_tools;
	__start__ -.-> retrieve;
	confirm_fix -.-> draft_ticket;
	confirm_fix -.-> execute_tool;
	confirm_ticket -.-> create_ticket;
	confirm_ticket -.-> log;
	create_ticket --> log;
	draft_ticket --> confirm_ticket;
	execute_tool --> log;
	retrieve --> triage;
	self_serve_wait -.-> draft_ticket;
	self_serve_wait -.-> log;
	triage -.-> confirm_fix;
	triage -.-> confirm_ticket;
	triage -.-> log;
	triage -.-> self_serve_wait;
	log --> __end__;
	no_tools --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

*Generated from the compiled graph (`build_graph(...).get_graph().draw_mermaid()`), so it cannot drift from the code. Dotted edges are conditional routers (`graph.py`: `route_start`, `route_after_triage`, `route_after_confirm_fix`, `route_after_confirm_ticket`, `route_after_self_serve`); `confirm_fix`, `confirm_ticket` and `self_serve_wait` are the human gates.*

| Path | When | Operator action required? |
|---|---|---|
| **SELF_SERVE** | Fix is documented, safe, and user-executable | No — steps returned directly; "didn't resolve it" button escalates |
| **AUTO_FIX** | Fix is documented, reversible, better run by the agent | Yes — Confirm runs the tool; Cancel pre-fills an escalation ticket instead of just dropping the issue |
| **ESCALATE** | Info missing, infra-/hardware-/IAM-side issue, or low confidence | Yes — Confirm or Cancel before ticket is created |
| **OUT_OF_SCOPE** | Not a workplace-technology request at all | No — declined immediately |

---

## How to run

```bash
uv sync
npm install
cp .env.example .env    # then add your ANTHROPIC_API_KEY
npm run dev             # http://localhost:5173
```

Checks, with no API key needed: `uv run poe check`.

## Documentation

- [What it must do](docs/SPEC.md)
- [The current sprint and where it's heading](docs/ROADMAP.md)
- [The tech choices](docs/TECH_STACK.md)
- [How the dashboard looks](docs/BRAND.md)
- [How to write the code](docs/CODE_STANDARDS.md)
- [How to run, plan and check the work](docs/PROCESS.md)
- [What's built, and which rules code enforces](docs/STATUS.md)
- [Design decisions and known limitations](docs/DECISIONS.md)

## Results

The baseline: one model call per ticket with `claude-haiku-4-5`, version `93b8e4f5`, run on 7 November 2026 and re-scored for free on 8 November after the owner reviewed two causes. The ± is the 95% margin of error. Mistake costs are assumptions, and they count every mistake as if nobody caught it at review.

| Set | Tickets | Path | Action | Right team | Kappa | Mistakes (CHF) |
|---|---|---|---|---|---|---|
| Rules set | 25 | 80% ±15% | 72% ±17% | 75% ±26% | 0.71 | 600 |
| Development | 129 | 73% ±8% | 71% ±8% | 70% ±9% | 0.44 | 9,960 |
| Unseen families | 52 | 60% ±13% | 31% ±12% | 31% ±12% | 0.00 | 3,420 |

Beside the two yardsticks:

| Set | Measure | FirstLine | Simple classifier | Most common answer |
|---|---|---|---|---|
| Rules set | Path | **80%** | 56% | 40% |
| Development | Path | 73% | **93%** | 70% |
| Development | Action | 71% | **91%** | 16% |
| Development | Mistakes (CHF) | 9,960 | **1,140** | 8,880 |
| Unseen families | Path | 60% | **100%** | **100%** |
| Unseen families | Right team | **31%** | 0% | 0% |

What it says:

- **The agent doesn't beat both yardsticks yet.** It wins on short, real requests (the rules set) and is the only one that finds the right team for families with no playbook. On the templated development tickets, a free classifier does better on everything.
- **Most tickets should be escalated**, 63% of the development set, so always escalating to `DESK-SUPPORT` gets the path right nearly as often as the agent. The agent earns its keep on the action and team, not the path.
- **Three security mistakes cost CHF 6,000 of the 9,960**, which makes the agent's mistakes dearer than always escalating. The agent proposed a routine fix on a possible compromise. SEC-04 moves into code in commit 6.
- **Disk encryption is the clearest weakness.** On 6 of 7 tickets where the TPM was never set up, the agent proposed escrowing the recovery key, which the playbook says only works on healthy encryption.
- **On unseen families it says "out of scope" too often** (21 of 52), when those are IT problems for another team.
- **It's cheap:** about CHF 0.005 and 5 seconds a ticket. All 206 practice tickets cost CHF 0.98, and re-scoring after a label change costs nothing.

Nothing was tuned on the held-out sets, which run once at sprint review.
