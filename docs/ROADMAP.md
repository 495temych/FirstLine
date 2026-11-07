# Roadmap

FirstLine is an L1 IT support agent for CorpLabs AG, a fictional company headquartered in Zürich, built as a portfolio project for Swiss employers. UnderCover is the model for the engineering practice, not the product.

**The idea: the agent proposes, the system enforces, and a scoreboard proves it works.**

This file holds the current sprint in detail and only a rough list after it. Each commit ships one working MVP. When the sprint ends we review it, plan again and rewrite this file.

## Where we are

Sprint 1 replaced Streamlit with a FastAPI backend and a React dashboard. Its other commits moved here, because the new dataset changes them: the baseline now runs on the new tickets, and the lockout guard now reads records that match them.

`docs/SPEC.md` now describes two modes on one company, CorpLabs. Today the app still runs the old Limmatica knowledge base, and only the Assistant's flow exists.

## The business goal

**Every ticket gets a correct first pass before a technician touches it.**

Only about a third of tickets show failures L1 could fix alone. That's a rough measure from who owns each failing check. So FirstLine can't be judged only on tickets it resolves: most of its value is sending the rest to the right team, already investigated.

| Outcome | Tickets | Measure |
|---|---|---|
| Routine tickets close with one approval | About a third | Share a technician would approve unchanged, by family |
| Other tickets reach the right team first time, already investigated | About two thirds | Right team first time, and required checks run |
| Nothing unsafe happens | All | Zero rule breaks |

The headline number is **technician time per ticket against model cost, in CHF**. Our records have no handling times, so the minutes are an assumption, and the Scoreboard says so.

The dataset does four jobs, and none of them is training a model:

| Job | What it gives us | Part of the data |
|---|---|---|
| Knowledge | Playbooks and similar past incidents | Knowledge base split only |
| Evaluation | Scores on tickets the agent has never seen | Development set, held-out set and two unseen families |
| Simulator | Checks that return recorded results, so the agent can investigate with no live systems | `diagnostics` |
| Privacy test | A real score for redaction | `pii.json` and `retention.json` |

## Sprint 2: the first pass, end to end

By the end, a technician can load a batch of tickets, let the agent investigate them, and work through three lists: approve the fix, approve the routing, or needs a person. This is a thin Queue, and Sprint 3 hardens it.

The foundations come first because both modes share them. Measured on the old knowledge base and the development sets, 94% of tickets in the 8 families it covers find the right playbook, but 91% of tickets in the 6 families it doesn't cover still match something: 85% in the 4 that get a playbook later, and 96% in the 2 unseen families. **This sprint has to bring that second number down, because an agent that doesn't know what it doesn't know is unsafe in a queue.**

| # | Commit | What you can see afterwards |
|---|---|---|
| 1 | **Tickets.** Import the 745 incidents, split them, and score retrieval for free | A "before" retrieval score on the Scoreboard |
| 2 | **CorpLabs.** Company, policies, queues, tools and staff records replace Limmatica | The Assistant answers as CorpLabs, with no old names left |
| 3 | **Playbooks.** 12 playbooks on one template, with section-level retrieval | The same score beside the "before", on tickets the playbooks never saw |
| 4 | **Labels.** Named causes with paths, reviewed by you, and the rules set relabelled | The Tickets page shows each ticket's cause and expected path |
| 5 | **Baseline.** One-call decisions scored against a simple classifier, and Triage becomes Assistant | The first real numbers, including whether Claude beats the yardstick |
| 6 | **Rules in code.** Requester records, tool risk tiers and the SEC-04 guard | Pick a user: the same lockout gets a different answer |
| 7 | **Investigate.** An agent loop with read-only tools and simulated checks, scored on the development set | What investigating adds over one call, for what extra cost |
| 8 | **Review.** Load a batch, work it in order, and approve, correct or reject in three lists | The full workflow, and technician time per ticket |
| 9 | **Privacy and tracing.** Redaction before the model, then Langfuse | Open any ticket and follow its trace, with no personal data in it |

Commit 4 needs you: the path labels are your judgement, and everything after it depends on them. Commit 9 needs your Langfuse keys, from its EU region. After commit 5, `docs/EVALS.md`, `docs/PLAN_EVALS.md` and `briefs/LABEL_REVIEW.md` are deleted.

**Left for Sprint 3 on purpose:** several agents at once, recovery after a crash, batch spending limits and the hold on tickets with hidden instructions. Until they exist, the Queue is a working demo and we won't describe it as production ready.

### Success criteria

The number after each one is the commit that meets it.

**Data (`data/`)**

- [x] (1) `data/tickets/tickets.json` holds only what's known at submission. `data/evals/incidents.json` holds `root_cause`, `resolution`, `correspondence` and the `diagnostics` summary.
- [x] (1) `data/tickets/splits.json` is fixed and repeatable: `CES` and `AIT` are unseen families, halved so one half can be tuned against, and the other 12 are split 60/20/20 by family.
- [x] (1) The source, its MIT licence and the fact that it's synthetic are in `data/tickets/SOURCE.md`. The import can be re-run.
- [ ] (2) `data/records/users.json` holds the 769 directory accounts, plus the 20 rules-set users, with invented devices, groups and lockouts. Tickets that name a requester link to a record (737 of 745 do).
- [ ] (4) Each ticket has one named cause, and each cause has accepted paths, tools, queues and required checks. You have reviewed every cause.
- [ ] (4) Our 50 tickets are moved to CorpLabs queues and renamed the rules set, with no `review` flag left.
- [ ] (7) `data/tickets/checks.json` holds each check's recorded result and nothing that gives away the answer. A test proves no `diagnostics` summary, `root_cause`, `resolution` or `correspondence` text is in it.

**Knowledge base (`data/kb/`)**

- [ ] (2) `company-profile.md`, `policies/` and the escalation queues describe CorpLabs, taken from the tickets' systems and teams. No file in the repository names Limmatica or Sihlwerk, checked by a test.
- [ ] (3) 12 playbooks plus `onedrive`, `teams` and `hardware-peripherals` follow one template, and a test fails on a missing section or field.
- [ ] (3) A test proves `CES` and `AIT` have no playbook, and that no held-out or development ticket id appears in `data/kb/`.
- [ ] (3) Each error code in a playbook comes from a knowledge base split ticket.

**Retrieval: sentence-transformers (`agent/retrieval.py`)**

- [x] (1) `uv run -m evals --retrieval` scores hit rate and false match rate on any split, with no model calls and in `poe check`.
- [ ] (3) Retrieval matches sections, then returns the best playbook's useful sections and any policy that matched.
- [ ] (3) Hit rate stays at 95% or above on the development set, and the false match rate on unseen families falls well below today's 91%. If the threshold alone can't do it, try a score margin first, then keyword matching for error codes. Each attempt is recorded in `docs/DECISIONS.md`, including those that fail.
- [ ] (7) Similar-incident search reads knowledge base split tickets only, checked by a test.

**Agent: LangGraph and Claude (`agent/`)**

- [ ] (2) `agent/prompt.md` and the tools describe CorpLabs. Each tool has a risk tier and an owner in `agent/tool_schemas.py`, and there's a tool for each fix L1 may run in the 12 families.
- [ ] (6) `run_triage` takes a requester, and the model sees that user's record. With no requester it behaves as it does today.
- [ ] (6) `agent/rules.py` holds pure functions that both modes call. A user with 2+ lockouts on a lockout ticket ends at `SEC-INCIDENT`, and a sensitive tool in the Assistant becomes a ticket.
- [ ] (6) Stub-model tests try to break each rule. The fix can't run, and a user with 2 lockouts and a printer ticket is not overridden.
- [ ] (7) `agent/queue.py` investigates one ticket with four read-only tools: search the knowledge base, look up the requester, find similar incidents and run a check. It ends in the same decision format as the Assistant.
- [ ] (7) The loop stops at its limits on steps and cost and escalates with what it found. A check the ticket doesn't have returns no result.
- [ ] (7) A test proves the loop can't reach a tool that changes a system, and that a model error fails that ticket alone.
- [ ] (8) Rule overrides are recorded on the ticket, with their reason.
- [ ] (9) `agent/redact.py` removes personal data before a Queue ticket reaches a model, and technical terms survive.

**Evaluations (`evals/`)**

- [ ] (5) The runner scores the development set, unseen families and the rules set. It reports path, action, team, named cause, mistake cost in CHF and cost per ticket, each by family.
- [ ] (5) A simple classifier trained on the knowledge base split predicts family and team on the same tickets, as a free yardstick for routing. Its score sits beside Claude's.
- [ ] (5) Scores show a margin of error, and each run records the versions of the instructions, tools and knowledge base.
- [ ] (5) The development set is run and committed. A full one-call run should cost under CHF 3, which is an estimate to confirm.
- [ ] (6) Safety scores are zero failures, and SEC-04 scores come from the rules set.
- [ ] (7) The same sets run through the Queue's loop, scored the same way, plus required checks run and steps per ticket. Evidence cited must come from a tool result.
- [ ] (8) The Scoreboard's headline shows approved unchanged, right team first time, technician time and model cost per ticket. Approved unchanged is estimated from decisions that match the labels.
- [ ] (9) A redaction score uses `pii.json` and `retention.json`, with no model calls and in `poe check`.
- [ ] (9) The held-out set runs once, at sprint review, through both modes.

**Tracing: Langfuse (new)**

- [ ] (9) Each ticket is one trace with its retrieval, model calls, tool calls, rule overrides and human answers, and a ticket waiting for review stays one session.
- [ ] (9) Evaluation runs and batches are tagged, and scores and review outcomes are attached to their traces.
- [ ] (9) A test proves nothing from `pii.json` reaches a trace.
- [ ] (9) With no keys in `.env`, the app and `poe check` work as they do today.

**API: FastAPI (`backend/`)**

- [ ] (5) Tickets and evaluations return the new labels and measures. Held-out tickets stay out of every route, checked by a test.
- [ ] (6) Starting a triage takes a requester. The gate rules are unchanged.
- [ ] (8) Routes load a batch, list tickets by state and list, and take a technician's approve, correct or reject. A rejection without a reason is refused, and a repeated answer does nothing.

**Storage: SQLite and CSV**

- [ ] (8) SQLite tables hold batches and each ticket's state, steps, decision and review. They stay out of git and out of tests.
- [ ] (9) `logs.csv` stores redacted text, in the same format.

**Dashboard: React, Vite and TypeScript (`dashboard/`)**

- [x] (1) The Scoreboard shows retrieval scores.
- [ ] (4) Tickets shows family, named cause and expected path, with a filter for each.
- [ ] (5) Triage is renamed Assistant, and the Scoreboard shows measures by family, with CHF for mistakes and the classifier's score.
- [ ] (6) A requester picker sits on the Assistant, and the page shows when a rule changed the agent's decision.
- [ ] (8) A Queue tab loads a batch and shows the three lists, ordered by SLA risk. A ticket opens to the agent's steps, evidence and any override.
- [ ] (8) A browser test works a batch from load to approved, with a stub model.
- [ ] (9) Each ticket links to its trace.

**Checks and CI**

- [ ] (all) `uv run poe check` passes on every commit, with the coverage thresholds unchanged and no API key.
- [ ] (all) New dependencies, such as scikit-learn and Langfuse, are in `docs/TECH_STACK.md` in the commit that adds them.

### Decisions to confirm at review

- **Unseen families.** `CES` (certificates) and `AIT` (API timeouts) stay out of the knowledge base. Both are wrong for L1 to fix, and `CES` is a hard test, because 93% of those tickets match `vpn` today.
- **Writing the playbooks.** A coding agent drafts them from knowledge base split tickets only, and you review them. The held-out set is never opened while writing.
- **Technician time.** The starting assumption is 15 minutes for a first pass by hand and 2 minutes to review one, at CHF 60 an hour. These numbers are placeholders for you to change.
- **Limits per ticket.** The loop starts at 8 steps and CHF 0.10, a guess to tune from the first run.

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
| `data/tickets/` | New | Tickets as they arrive, with fixed splits |
| `data/evals/` | 50 tickets | Rules set, named causes, incident answers and saved runs |
| `agent/` | One graph | The Assistant's graph, plus `rules.py`, `queue.py` and `redact.py` |
| `agent/tool_schemas.py` | 10 tools | Tools with a risk tier and owner, plus four read-only tools |
| `evals/` | One decision score | One score per level in `docs/SPEC.md`, a classifier yardstick, and the judge later |
| `backend/` | Triage routes | Plus batch and review routes |
| `dashboard/` | Triage, Scoreboard, Tickets | Queue, Assistant, Scoreboard, Tickets |
| Storage | Checkpoints and CSV | Plus SQLite tables for batches, tickets and reviews |

## After this sprint

These are candidates, not commitments, and each sprint picks from them when we plan it.

- **Sprint 3, a Queue that holds up:** several agents at once from a dispatcher with no model, recovery from a killed run, nothing done twice, batch spending limits, and the hold on tickets with hidden instructions.
- **Sprint 4, prove it:** a judge for write-ups, checked against human grades, deeper investigation scores, batch cost and time at N agents, and hidden-instruction tickets in the evaluations.
- **Sprint 5, harden and show:** a hosted demo with a budget cap, a production build served by the backend, a two-minute walkthrough, and an audit view.
- **Sprint 6, German:** tickets and answers in both modes. It needs a multilingual embedding model, German versions of tickets in the evaluations, and answers in the language of the request.

The demo all this builds towards: load 25 tickets, some in German, one with a hidden instruction. Agents work them at once. Code blocks a repeat lockout, even if the model proposes an unlock. A technician clears the lists in minutes. The Scoreboard shows accuracy, technician time saved and cost per ticket, in CHF.

## How to make this a solid project

Employers will spend a few minutes on this, so each point should be something they can see.

1. **Let numbers make the claim.** Replace the README's assumed 50% automation with measured approval and routing rates, next to mistake cost, technician time and cost per ticket.
2. **Close rule gaps by how much harm they do.** Each safety rule needs code, plus a test where a stub model tries to break it.
3. **Treat evaluations as regression tests.** Run the development set after every agent change. Run the held-out set only at sprint review.
4. **Fail towards a technician.** A timeout, API error or unreadable answer should become an escalation, never a crash or a silent fix.
5. **Make every decision traceable.** Each ticket should show what was retrieved, proposed, overridden and confirmed.
6. **Take Swiss data protection seriously.** Say plainly what reaches a model hosted abroad, and keep personal data out of logs and traces.
7. **Keep one of everything.** One decision format, one place for rules. Delete what gets replaced.
8. **Stay honest.** The tickets are synthetic, the costs are assumptions, and the Scoreboard shows every mistake.

## Not for now

Sign-in, cloud databases, AWS, agents that rewrite their own prompts, real integrations and an MCP layer for the knowledge base.
