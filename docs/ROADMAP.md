# Roadmap

FirstLine is an L1 IT support agent for CorpLabs AG, a fictional company headquartered in Zürich, built as a portfolio project for Swiss employers. UnderCover is the model for the engineering practice, not the product.

**The idea: the agent proposes, the system enforces, and a scoreboard proves it works.**

The project runs in three sprints, one for each week of the AI FDE course. This file holds all three, with success criteria for the current sprint and commit lists for the others. Each commit ships one working MVP. When a sprint ends we run the held-out set, review it, and write the next sprint's criteria.

## The business goal

**Every ticket gets a correct first pass before a technician touches it.** `docs/BUSINESS_GOAL.md` holds the outcomes, the money, the baselines and the success criteria.

The dataset does four jobs, and none of them is training a model:

| Job | What it gives us | Part of the data |
|---|---|---|
| Knowledge | Playbooks and similar past incidents | Knowledge base split only |
| Evaluation | Scores on tickets the agent has never seen | Development set, held-out set and two unseen families |
| Simulator | Checks that return recorded results, so the agent can investigate with no live systems | `diagnostics` |
| Privacy test | A real score for redaction | `pii.json` and `retention.json` |

## The three sprints

| Sprint | Course week | Question it answers | Where it runs | Done when |
|---|---|---|---|---|
| 1. Prove it locally | Week 1: AI Engineer | Is this the right problem, and does the agent beat a simple baseline? | Your Mac, with Claude's API | A chosen model and design, with real numbers |
| 2. Make it a system | Week 2: AI Architect | Can it run a whole queue, be observed, and improve safely? | Your Mac, with Qdrant, Supabase and Langfuse | A durable Queue, with every ticket traced and scored |
| 3. Deliver it | Week 3: AI FDE | Could a client safely run it without you? | Microsoft Azure | A secured, hosted demo with a handover pack |

### What each service is for

Week 3 asks where each kind of data belongs. Each store has one job, so nothing has two sources of truth.

| Place | Tool | What it holds | Source of truth? |
|---|---|---|---|
| Context layer | `data/kb/` in git | Playbooks and policies, with owner and review date | Yes |
| Search index | Qdrant | Embedded knowledge base sections and past incidents | No, it can be rebuilt from git |
| System of record | Supabase | Tickets, batches, decisions, reviews, the audit trail, checkpoints and sign-in | Yes |
| Observability | Langfuse | Traces, datasets, experiments and scores | Yes for traces, no for labels, which stay in git |
| Gateway | Azure API Management | Keys, rate limits, token budgets and logs | No, it holds rules, not data |

## Sprint 1: prove it locally

**Week 1 in one line: start from a business problem you can measure, label the data, and test models on your own task against a simple baseline.**

Everything runs locally, with no new services. Done so far: the FastAPI and React stack, the rename to FirstLine, and commits 1 and 2.

| # | Commit | What you can see afterwards |
|---|---|---|
| 1 | ✅ **Tickets.** Import the 745 incidents, split them, and score retrieval for free | A "before" retrieval score on the Scoreboard |
| 2 | ✅ **CorpLabs.** Company, policies, queues, tools and staff records replace the old client | The Assistant answers as CorpLabs, with no old names left |
| 3 | ✅ **Playbooks.** 12 playbooks on one template, with section-level retrieval | The same score beside the "before", on tickets the playbooks never saw |
| 4 | **Labels.** Named causes with paths, reviewed by you, and the rules set relabelled | The Tickets page shows each ticket's cause and expected path |
| 5 | **Baseline.** Structured decisions, scored against the most common answer and a simple classifier | The first real numbers, including whether Claude beats the yardsticks |
| 6 | **Rules in code.** Requester records, tool risk tiers and the SEC-04 guard | Pick a user: the same lockout gets a different answer |
| 7 | **Investigate.** Three designs on the same tickets: one call, code runs the family's checks before one call, and one agent loop with read-only tools. Each writes a full handover | What investigating adds over one call, and whether a loop beats a fixed workflow, for what extra cost |
| 8 | **Choices.** Test models and reasoning effort, rank the families by RICE, and record plans B and C | A written choice of model and design, backed by numbers |

Commit 4 needs you: the path labels are your judgement, and everything after it depends on them. After commit 5, `docs/EVALS.md`, `docs/PLAN_EVALS.md` and `briefs/LABEL_REVIEW.md` are deleted.

### Success criteria

The number after each one is the commit that meets it.

**Data (`data/`)**

- [x] (1) `data/tickets/tickets.json` holds only what's known at submission. `data/evals/incidents.json` holds `root_cause`, `resolution`, `correspondence` and the `diagnostics` summary.
- [x] (1) `data/tickets/splits.json` is fixed and repeatable: `CES` and `AIT` are unseen families, halved so one half can be tuned against, and the other 12 are split 60/20/20 by family.
- [x] (1) The source, its MIT licence and the fact that it's synthetic are in `data/tickets/SOURCE.md`. The import can be re-run.
- [x] (2) `data/records/users.json` holds the 628 directory accounts, plus the 20 rules-set users, with invented devices, groups and lockouts. All 745 tickets link to a requester's record.
- [ ] (4) Each ticket has one named cause, and each cause has accepted paths, tools, queues and required checks. You have reviewed every cause.
- [ ] (4) Our 50 tickets are moved to CorpLabs queues and renamed the rules set, with no `review` flag left.
- [ ] (7) `data/tickets/checks.json` holds each check's recorded result and nothing that gives away the answer. A test proves no `diagnostics` summary, `root_cause`, `resolution` or `correspondence` text is in it.

**Knowledge base (`data/kb/`)**

- [x] (2) `company-profile.md`, `policies/` and the escalation queues describe CorpLabs, taken from the tickets' systems and teams. No file in the repository names the old client or provider, checked by a test.
- [x] (3) 12 playbooks plus `onedrive`, `teams` and `hardware-peripherals` follow one template, and a test fails on a missing section or field.
- [x] (3) A test proves `CES` and `AIT` have no playbook, and that no held-out or development ticket id appears in `data/kb/`.
- [x] (3) Each error code in a playbook comes from a knowledge base split ticket.

**Retrieval: sentence-transformers (`agent/retrieval.py`)**

- [x] (1) `uv run -m evals --retrieval` scores hit rate and false match rate on any split, with no model calls and in `poe check`.
- [x] (3) Retrieval matches sections, then returns the best playbook's useful sections and any policy that matched. `agent/retrieval.py` keeps a small interface, so Qdrant can replace its insides in Sprint 2.
- [x] (3) Hit rate reaches 95% on the development set, with a floor in `poe check`, and the false match rate on `unseen_dev` falls well below today's 96%. If the threshold alone can't do it, try a score margin. Keyword matching waits for Qdrant. Each attempt is recorded in `docs/DECISIONS.md`, including those that fail.
- [x] (3) The score adds mean reciprocal rank and recall, as well as the hit rate.

**Agent: LangGraph and Claude (`agent/`)**

- [x] (2) `agent/prompt.md` and the tools describe CorpLabs. Each tool has a risk tier and an owner in `agent/tool_schemas.py`, and there's a tool for each fix L1 may run in the 12 families.
- [ ] (5) The decision is a Pydantic class, with the rationale first, so the model reasons before it decides.
- [ ] (6) `run_triage` takes a requester, and the model sees that user's record. With no requester it behaves as it does today.
- [ ] (6) `agent/rules.py` holds pure functions that both modes call. A user with 2+ lockouts on a lockout ticket ends at `SEC-INCIDENT`, and a sensitive tool in the Assistant becomes a ticket.
- [ ] (6) Stub-model tests try to break each rule. The fix can't run, and a user with 2 lockouts and a printer ticket is not overridden.
- [ ] (7) `agent/queue.py` investigates one ticket with four read-only tools: search the knowledge base, look up the requester, find similar incidents and run a check. It ends in the same decision format as the Assistant.
- [ ] (7) The loop stops at its limits on steps and cost and escalates with what it found. A check the ticket doesn't have returns no result.
- [ ] (7) A test proves the loop can't reach a tool that changes a system, and that similar-incident search reads knowledge base split tickets only.
- [ ] (7) A fixed workflow runs a family's playbook checks in code, then makes one model call. With no matching playbook it runs no checks and escalates.
- [ ] (7) An escalation carries a full handover. Code fills in the requester, device, priority, SLA deadline, applications, checks with their evidence, similar incidents and what's unknown. The model writes only the likely cause, what's ruled out and the next step, citing that evidence.

**Evaluations (`evals/`)**

- [ ] (5) The runner scores the development set, unseen families and the rules set. It reports path, action, team, named cause, mistake cost in CHF and cost per ticket, each by family.
- [ ] (5) Each score sits beside two yardsticks: always giving the most common answer, and a simple classifier trained on the knowledge base split. The report includes a confusion matrix, precision and recall per path, and Cohen's kappa.
- [ ] (5) Scores show a margin of error, and each run records the versions of the instructions, tools and knowledge base.
- [ ] (5) The development set is run and committed. A full one-call run should cost under CHF 3, which is an estimate to confirm.
- [ ] (6) Safety scores are zero failures, and SEC-04 scores come from the rules set.
- [ ] (7) The same sets run through the fixed workflow and the loop, scored the same way, plus required checks run and steps per ticket. Evidence cited must come from a tool result. The loop stays only if it beats the fixed workflow by more than the noise, for its extra cost.
- [ ] (8) At least two models, and reasoning effort where it applies, are run on the development set, more than once. A chart shows accuracy against the cost of the whole task, and the choice is in `docs/DECISIONS.md`.
- [ ] (8) Families are ranked by RICE from measured volume and scores, and the ranking says where to start.
- [ ] (8) The held-out set runs once, at sprint review.

**API and dashboard (`backend/`, `dashboard/`)**

- [x] (1) The Scoreboard shows retrieval scores.
- [ ] (4) Tickets shows family, named cause and expected path, with a filter for each.
- [ ] (5) Tickets and evaluations return the new labels and measures. Held-out tickets stay out of every route, checked by a test.
- [ ] (5) Triage is renamed Assistant, and the Scoreboard shows measures by family, the yardsticks, and CHF for mistakes.
- [ ] (6) Starting a triage takes a requester, and a picker sits on the Assistant. The page shows when a rule changed the agent's decision. The gate rules are unchanged.
- [ ] (7) The Scoreboard shows the fixed workflow and the loop beside the one-call run.

**Checks and CI**

- [ ] (all) `uv run poe check` passes on every commit, with the coverage thresholds unchanged and no API key.
- [ ] (all) New dependencies are in `docs/TECH_STACK.md` in the commit that adds them.

### Decisions to confirm at review

- **Unseen families.** `CES` (certificates) and `AIT` (API timeouts) stay out of the knowledge base. Both are wrong for L1 to fix, and `CES` is a hard test, because 93% of those tickets match `vpn` today.
- **Writing the playbooks.** A coding agent drafts them from knowledge base split tickets only, and you review them. The held-out set is never opened while writing.
- **Technician time.** The starting assumption is 15 minutes for a first pass by hand and 2 minutes to review one, at CHF 60 an hour. These numbers are placeholders for you to change.
- **Limits per ticket.** The loop starts at 8 steps and CHF 0.10, a guess to tune from the first run.

## Sprint 2: make it a system

**Week 2 in one line: keep logic in code, measure everything, make long work durable, and let a system improve only when evals approve.**

Redaction comes first, because tickets start leaving the Mac in this sprint. The batch and review screens are built straight on Supabase, so nothing gets built twice.

| # | Commit | What you can see afterwards | Course idea |
|---|---|---|---|
| 1 | **Redaction.** Remove personal data before a ticket reaches any service, scored by `pii.json` and `retention.json` | A free redaction score | Send only the personal data the task needs |
| 2 | **Langfuse.** One trace per ticket, tagged runs, and scores on traces | Open any decision and follow it | Traces, datasets, experiments and scores |
| 3 | **Qdrant.** Sections and past incidents move to Qdrant, with hybrid search for error codes | Before and after retrieval scores, plus false matches | Search by meaning, and retrieval evals |
| 4 | **Supabase.** Postgres replaces SQLite and `logs.csv`, including LangGraph's checkpoints | A paused ticket survives a restart, on Postgres | Checkpoints in Postgres, and a system of record |
| 5 | **Queue and review.** Load a batch, order it in code, and approve, correct or reject in three lists. After a fix, the failed check runs again: the ticket closes if it passes, and escalates with both results if not | The full workflow, and technician time per ticket | The human's step |
| 6 | **Durable at scale.** A dispatcher with no model, N agents, retries, no repeated actions, and spending limits | Kill a batch mid-run, and it carries on without doing anything twice | Dispatcher, `Send`, idempotency, `RetryPolicy` |
| 7 | **Clean evals.** A Langfuse experiment for each change, repeated runs, a judge checked against your grades, and a release gate | A change either passes the gate or doesn't | Three kinds of evals, noise, and an LLM judge |
| 8 | **Self-improvement, if time allows.** An improver proposes changes, you approve them, and evals keep or roll them back | A proposed change with its evidence | The improver, keep or roll back, held-out data |

The improver needs one safeguard. It sees mistakes from part of the development set, and decides on a separate part that it never sees. That keeps the held-out set for sprint review.

The records hold no results from after a fix, so the re-check in commit 5 is simulated, and the demo says so.

Tests stay free and offline: Qdrant has a local mode with no server, and Postgres can run in a container in CI. Commit 3 must confirm that local mode covers hybrid search. Commit 2 needs your Langfuse keys, commit 3 a Qdrant key, and commit 4 a Supabase project.

## Sprint 3: deliver it

**Week 3 in one line: decide what the agent may do, secure it in layers, run it where a client can trust it, and hand it over.**

| # | Commit | What you can see afterwards | Course idea |
|---|---|---|---|
| 1 | **Autonomy and responsibility.** Each action is automatic, approved or prohibited, with an owner for all six pillars | A one-page policy the code enforces | Risk per action, six pillars |
| 2 | **Guardrails.** Coded checks for personal data and keys, a model check for hidden instructions, and golden attack tickets | A hidden-instruction ticket is held, and false alarms are counted | Lethal trifecta, guardrail layers |
| 3 | **Sign-in and roles.** Technicians sign in, and Postgres row rules limit what each role sees | Signed out, you see nothing | Authentication and authorization |
| 4 | **Containers.** The app builds into one image, with no secrets in it | The same image runs locally | Configuration and secrets |
| 5 | **Azure.** Infrastructure as code, Container Apps, Key Vault, managed identity and budget alerts | A hosted demo, with one command to tear it down | Where it runs, cloud hygiene |
| 6 | **Gateway.** API Management in front of the model, with rate limits and token budgets, logging first and enforcing after | A spending limit that blocks a call | Gateways, log-only then enforce |
| 7 | **Handover.** Runbook, audit view, measures against the Sprint 1 baseline, and a two-minute walkthrough | A client could run it without you | Handover and adoption |

The demo all this builds towards: load 25 tickets, one with a hidden instruction. Agents work them at once. Code blocks a repeat lockout, even if the model proposes an unlock. A technician clears the lists in minutes. The Scoreboard shows accuracy, technician time saved and cost per ticket, in CHF.

### From AWS to Azure

| Course, on AWS | FirstLine, on Azure | Why |
|---|---|---|
| AgentCore Runtime | Azure Container Apps | It runs any framework, so LangGraph stays as it is |
| AgentCore Gateway and Policy | API Management | Its `llm-token-limit` policy covers the Anthropic Messages API on v2 tiers. We skip an MCP gateway, because these are our own tools |
| AgentCore Identity, IAM user | Managed identity, Entra ID and Key Vault | The app holds no cloud passwords |
| AgentCore Memory | Supabase, then Qdrant | Week 3 says to start with one kind of memory. Ours is past incidents |
| Bedrock | Claude in Microsoft Foundry | One bill and one identity. The direct Anthropic API is plan B |
| Budget alerts, teardown | Azure budgets, teardown with infrastructure as code | Budgets alert, they don't stop spending, so teardown still matters |

To check before Sprint 3 starts: whether Container Apps runs in Switzerland North, the current Foundry regions for Claude, and the monthly price of an API Management v2 tier.

## How the course maps to FirstLine

| Week | Idea | In FirstLine |
|---|---|---|
| 1 | Score against a simple baseline | Most common answer, and a classifier |
| 1 | Weigh mistakes by business cost | Mistake costs in CHF |
| 1 | Fixed workflow? One call can beat an agent | The Assistant is one call, and commit 7 tests a loop against checks run in code |
| 1 | Structured outputs, rationale first | The decision class |
| 1 | Test models on the customer's task | Sprint 1, commit 8 |
| 1 | Agents need a harness | Instructions, tools, limits and a human handoff |
| 2 | Business logic belongs in code | `agent/rules.py` and the dispatcher |
| 2 | Start with one agent | One agent per ticket, and no sub-agents until evals justify them |
| 2 | Three kinds of evals | Plain code, a judge, and technician reviews |
| 2 | Side effects get their own node | Already how the gates work |
| 2 | Decide on held-out data | The improver's safeguard |
| 3 | Lethal trifecta | Ticket text is untrusted and records are private, so Queue tools only read, and a person approves anything that leaves |
| 3 | Provenance | Owner and review date on every playbook |
| 3 | Agree success criteria at the start | The criteria in `docs/BUSINESS_GOAL.md`, measured at handover |

We're leaving some things out on purpose, and each is a choice we can defend:

- **Local and open-weight models.** Claude is enough here. A local model is plan C if a client won't send data to a provider.
- **Fine-tuning.** It learns patterns rather than facts, and our tickets are too few and too alike.
- **MCP.** The course says to skip it for your own tools on your own agent.
- **Sub-agents, teams and A2A.** We have one agent per ticket. A judge and an improver are separate jobs, not agent teams.
- **Self-hosted Langfuse.** It needs Postgres, ClickHouse, Redis and blob storage, which is too much to run for a demo.

## How the knowledge base is structured

```text
data/kb/
├── company-profile.md        systems, teams, offices and naming
├── escalation-queues.md      each queue, what it owns and its SLA
├── policies/                 one file per policy, such as sec-04-account-lockout.md
└── playbooks/                one file per issue
```

Each playbook starts with fields that code reads, then has the same six sections:

```markdown
---
id: vpn-access
title: VPN access
owner_team: network
last_reviewed: 2026-11-06
applications: [GlobalProtect]
tools: [reset_vpn_profile]
---

## Symptoms
## Checks
## Error codes
## Known causes
## Fix
## When to escalate
```

| Family | Playbook | Team that owns escalations |
|---|---|---|
| `ALP` | `account-lockout` | Identity |
| `SML` | `sso-mfa` | Identity |
| `VDA` | `vpn-access` | Network |
| `WCI` | `wifi` | Network |
| `DRF` | `dns` | Network |
| `SDA` | `shared-drive` | Service desk |
| `PDQ` | `printing` | Service desk |
| `OES` | `outlook` | Service desk |
| `SIB` | `software-install` | Service desk, security for blocks |
| `DCP` | `device-compliance` | Service desk |
| `LPD` | `laptop-performance` | Desktop support |
| `EDE` | `disk-encryption` | Desktop support |
| `CES` | None, unseen | Applications and network |
| `AIT` | None, unseen | Applications |

## How the rest of the product changes

| Part | Now | Target |
|---|---|---|
| `data/tickets/` | Imported tickets and splits | The same, loaded into Supabase for the Queue |
| `data/evals/` | 50 tickets, incident answers and retrieval scores | Rules set, named causes and saved runs, mirrored as Langfuse datasets |
| `agent/` | One graph | The Assistant's graph, plus `rules.py`, `queue.py`, `redact.py` and a dispatcher |
| `agent/retrieval.py` | Local NumPy search | The same interface, on Qdrant |
| `agent/tool_schemas.py` | 10 tools | Tools with a risk tier and owner, plus four read-only tools |
| `evals/` | One decision score | One score per level in `docs/SPEC.md`, yardsticks, a judge and a release gate |
| `backend/` | Triage routes | Plus batch and review routes, sign-in and role checks |
| `dashboard/` | Triage, Scoreboard, Tickets | Queue, Assistant, Scoreboard, Tickets, each ticket linked to its trace |
| Storage | SQLite and CSV | Supabase |
| Hosting | Your Mac | Azure Container Apps, behind API Management |

## After Sprint 3

German comes next: tickets and answers in both modes. It needs a multilingual embedding model, German versions of tickets in the evaluations, and answers in the language of the request.

## How to make this a solid project

Employers will spend a few minutes on this, so each point should be something they can see.

1. **Let numbers make the claim.** Replace the README's assumed 50% automation with measured approval and routing rates, next to mistake cost, technician time and cost per ticket.
2. **Close rule gaps by how much harm they do.** Each safety rule needs code, plus a test where a stub model tries to break it.
3. **Treat evaluations as regression tests.** Run the development set after every agent change. Run the held-out set only at sprint review.
4. **Fail towards a technician.** A timeout, API error or unreadable answer should become an escalation, never a crash or a silent fix.
5. **Make every decision traceable.** Each ticket should show what was retrieved, proposed, overridden and confirmed.
6. **Take Swiss data protection seriously.** Say plainly what reaches a model hosted abroad, and keep personal data out of logs and traces.
7. **Keep one of everything.** One decision format, one place for rules, one source of truth for each kind of data. Delete what gets replaced.
8. **Stay honest.** The tickets are synthetic, the costs are assumptions, the test sets are small, and the Scoreboard shows every mistake.

## Not for now

Real integrations, more than one company, agents that change themselves without approval, and fixes that run without a person.
