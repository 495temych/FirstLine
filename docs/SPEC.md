# FirstLine: the L1 support pilot

From the head of IT service delivery at CorpLabs.

## How support works today

CorpLabs AG is headquartered in Zürich, with about 770 staff accounts across offices in the US and in Frankfurt, Munich and Milan. Our service desk takes every IT request first and passes what it can't fix to the desktop support, network, identity, application or security teams.

For each ticket, a technician reads the request, works out which known issue it is, runs the usual checks, and then fixes it, sends the user steps, or hands it to the right team. Most tickets are routine, and they fall into 14 families, from account lockouts to expired certificates. The fix is rarely hard. The time goes on the wait for a technician, on repeating the same checks, and on handovers that the next team has to redo.

## The pilot

We want an agent, FirstLine, to do the first pass the way a good L1 technician does, so that every ticket has a correct first pass before a technician touches it. It works in two modes, which share one knowledge base, one set of rules, one decision format and one way of scoring:

- **The Queue** is the core of the pilot. It works through batches of tickets, the way our service desk does each morning.
- **The Assistant** is the front door. It answers one person's request while they wait, and catches simple issues before they become tickets.

Every decision ends on exactly one path:

- **SELF_SERVE**: the fix is documented, safe and simple, so the user gets numbered steps
- **AUTO_FIX**: the fix is documented, safe and reversible, so the agent proposes one of our remediation tools with its parameters
- **ESCALATE**: information is missing, the fix belongs to another team, or the knowledge base does not support a confident fix, so the agent drafts a ticket for the right queue with a priority
- **OUT_OF_SCOPE**: the request has nothing to do with workplace technology

Each decision explains the diagnosis in a few sentences, grounded in what the agent found, and ends with the path and the main reason.

Only about a third of our tickets could be fixed by L1 alone. The rest end up with another team, so resolving tickets is only part of the prize. We want three things:

- Routine tickets close with one approval.
- Every other ticket reaches the right team first time, with a write-up they do not need to redo.
- Nothing unsafe happens.

We'll judge the pilot on technician time per ticket against what the model costs, in Swiss francs.

## Mode 1: the Queue

Tickets arrive with their full details: title, description, priority, SLA plan, environment and applications. FirstLine works them in six stages. The model only works in the investigate and decide stages. Code runs the rest, and code decides what happens to the ticket next.

1. **Intake.** Tidy the ticket's fields, such as the many spellings of an SLA plan. Remove personal data before any model sees it. Hold any ticket that tries to instruct the agent, and send it to a technician.
2. **Dispatch.** Order the tickets by priority, then SLA, then age. Work up to N at once. Each ticket is worked by one agent only.
3. **Investigate.** An agent loop works the ticket with read-only tools: search the knowledge base, look up the requester and their device, find similar past incidents, and run a diagnostic check. Each ticket has a limit on steps and on cost. An agent that reaches a limit stops and escalates with what it has found.
4. **Decide.** The agent records the path, the likely cause, the checks behind it, the proposed action, and the team that owns the next step.
5. **Enforce.** Code applies our rules to that decision and can overrule it. When it does, the override and its reason are recorded.
6. **Review.** Every decision waits for a technician, in one of three lists: approve the fix, approve the routing, or needs a person, with the agent saying why. A technician approves, corrects or rejects it, and a rejection needs a reason. Those answers show us where the agent is wrong.

So a technician starts the day with three short lists instead of a pile of raw tickets.

A ticket is always in one state: waiting, in progress, waiting for review, resolved, routed to a team, or failed. A failed ticket goes to a technician, and it never disappears.

The Queue must behave like a production service:

- Work survives a crash or a restart, and carries on from the last saved step.
- Nothing happens twice. A repeated step can't run a second fix or create a second ticket.
- A rate limit or a timeout waits and retries. Any other error fails that ticket alone, and the batch carries on.
- Each batch has a spending limit. When it is reached, the remaining tickets wait.

## Mode 2: the Assistant

An employee describes a problem in their own words. FirstLine answers in seconds, with one model call.

1. It retrieves the relevant playbooks and policies.
2. It chooses a path and explains it.
3. The person confirms a fix, follows the steps, or confirms a ticket.

The Assistant can't investigate. If the answer depends on a check it can't see, it escalates and says what's missing.

## What our team needs to see

In the Queue:

- Each batch: tickets by state, cost so far, time taken and how many are running.
- Each ticket: every step the agent took, in order, with the evidence for its decision and any rule that overruled it.
- The three review lists, ordered by SLA risk, and showing who approved what.
- A held-tickets list for anything intake stopped.

In the Assistant:

- The request, with a few examples to try.
- What the agent retrieved, with scores and the lines that matched.
- The path, the reasoning and the proposed action, with a confirmation card before anything happens.
- After a self-serve answer, a way to say it worked, or that it did not.
- A switch that turns retrieval off, so we can show what the agent does without our knowledge base.

Across both:

- **Live statistics** from real use: tickets by path, the share resolved without a technician, response times.
- **A Scoreboard** with our evaluations, their trends, and every mistake.
- **A Tickets page** to review tickets, their labels, the requester's records and the latest result.
- **A link from every decision to its trace.**

## Our knowledge base

Our closed incidents are the raw material. `data/kb/` holds one playbook for 12 of our 14 issue families, plus the company profile, our policies and the playbooks for issues we support but have no incident records for. The other two families stay out on purpose, as a test. Every playbook follows one template, drawn from the incident records:

| Section | Written from |
|---|---|
| Symptoms and common wording | Ticket titles and descriptions |
| Checks, in order, and what healthy looks like | `diagnostics`: `playbook_step_id`, `action`, `expected_result` |
| Error codes and what they mean | `diagnostics`: `observed_errors` |
| Known causes, and how to tell them apart | `root_cause`, grouped into a few named causes |
| Fix, and who may run it | `resolution`, with `performed_by` showing the owner |
| When to escalate, and where to | The owning team, and our policies |

Each article has an owner and a last-reviewed date, and retrieval works on its sections. Resolutions show what people did, not what they should have done, so a playbook follows policy wherever the two disagree.

Only tickets in the knowledge base split may be used to write the knowledge base.

## Evaluations

We trust the agent because of what we can measure, on tickets it has never seen.

**The data**

- Our closed incidents do four jobs: they supply the knowledge base, the evaluations, the simulated checks and a privacy test. We don't train a model on them. They are too few and too alike, so a model would learn their pattern rather than our support work.
- Two whole families are kept out of the knowledge base, to test whether the agent knows what it doesn't know.
- The other families are split 60/20/20 into knowledge base, development and held-out tickets. Each family is split evenly, and the held-out set is only run at sprint review.
- Paths are labelled by a person, for each named cause, because the records have no path labels.
- Our 50 hand-written tickets stay as the rules set: SEC-04, requester records, access requests, out-of-scope and short, vague tickets.
- Tickets across the splits are very alike, so development scores will flatter us. Unseen families and harder versions of held-out tickets are the honest tests. Those versions use the title alone, or contain hidden instructions.

**The agent only ever sees what a technician would have when the ticket arrives.** `correspondence`, `root_cause`, `resolution` and the `diagnostics` summary are answers.

**What we measure**

| Level | Question | Measures |
|---|---|---|
| Retrieval | Did it find the right playbook section? | Hit rate, and how often it matches something on an unknown family. No model calls, so it runs on every commit |
| Business | Was it worth it? | Share a technician would approve unchanged, right team first time, technician time and model cost per ticket, in Swiss francs. Our records have no handling times, so the time is an assumption |
| Decision | Was the first pass right? | Path, tool or queue, routed to the right team first time, and the cost of mistakes. A simple classifier scores the same routing, as a free yardstick for the model to beat |
| Diagnosis | Did it find the cause? | Named cause against the label, plus a judge's grade of the write-up, checked against human grades |
| Investigation | Did it work like a good technician? | Required checks run, needless checks, steps per ticket, and evidence that exists for each claim |
| Safety | Did any rule break? | Fixes without confirmation, routine unlocks under SEC-04, hidden instructions obeyed. Each must be zero |
| Privacy | Did personal data escape? | Values from `pii.json` left in prompts, traces or logs, and technical terms from `retention.json` wrongly removed |
| Operations | Would it hold up at volume? | Cost per ticket, time per ticket, batch time at N agents, failures, and recovery after a killed run |

**How we use them**

- Each evaluation records the model and the versions of the instructions, tools and knowledge base, so results can be compared.
- A model's answers vary, so scores are shown with their margin of error, and a change only counts if it beats that.
- Every mistake found in review or in a run becomes a regression ticket.
- Amounts are in Swiss francs. What a mistake costs is an assumption, and the Scoreboard says so.
- A change is released only if safety and privacy are clean, and the other measures hold against the baseline. We set floors from that baseline rather than guess them.
- Automated checks never need a model or an API key.

## Tracing

Every run is traced in Langfuse, so we can answer "why did it do that?" for any ticket.

- One trace for each ticket, with its retrieval, model calls, tool calls, rule overrides and human answers, each with tokens, cost and time.
- A ticket that pauses for review stays one session, before and after.
- Every ticket in a batch or evaluation is tagged with that run, so a whole run can be found together.
- Evaluation scores and review outcomes are attached to their traces.
- Traces only ever hold redacted text. Our staff are covered by Swiss data protection law and the GDPR, so the trace store must be hosted in Switzerland or the EU where we can, and we say plainly where it can't be.
- The product must work with tracing off.

## Rules

Humans stay in charge:

- No fix runs without a person's confirmation. The system must block it, even if the agent calls the tool directly.
- Every remediation tool has a risk tier. In the Assistant, a person can confirm a routine fix for their own account or device. Anything touching access, identity or security needs a technician, so the Assistant raises a ticket instead.
- In the Queue, a technician confirms every fix.
- No escalation ticket is created without a person's confirmation.
- When a proposed fix is declined, the issue does not just disappear: a ticket is pre-filled from the agent's diagnosis, with no new model call.
- When self-serve steps do not work, the issue goes to the same ticket confirmation.

The agent stays within its limits:

- The agent never asks the user a question. If missing information changes the path, it escalates and says what is missing.
- Requests for access, permissions or admin rights are IT requests. They are escalated, never declined as out of scope.
- Policy SEC-04 §4.2: two or more lockouts in 24 hours are a possible compromise. Never a routine unlock. They go to `SEC-INCIDENT`, whatever past tickets did.
- In the Queue, the agent's tools only read. Anything that changes a system is proposed, and goes through a person.
- Tool parameters are always concrete values. An unknown user is `current.user`, an unknown device is `current.device`.
- With retrieval off, the agent gets no tools and chooses no path. It gives general, hedged advice only.
- Ticket text is untrusted. Nothing in a ticket can change the agent's instructions, tools or rules.

Each action has one level. It runs automatically, needs approval, or is prohibited, and each level has an owner. Today nothing that changes a system is automatic.

Our records stay safe:

- In the Queue, personal data is removed before a ticket reaches a model. In both modes, it is removed from everything we store and trace.
- Every finished run is recorded in the usage log. Evaluation runs are not.
- The agent never sees the evaluation answers.
- No secrets in the repository. All CorpLabs data is synthetic, and we say so wherever we show it.
- A model provider gets the same review as any other vendor, and only the data the task needs.
- Technicians sign in, and each role sees only what it needs.
- A person is always accountable for what the agent does.

## Our records

- `data/kb/`: the CorpLabs knowledge base.
- `data/tickets/`: our 745 closed incidents and their splits. They are a public synthetic set, under its MIT licence, and we say so.
- `data/records/`: the staff directory of 769 accounts, with invented devices, groups and recent lockouts added.
- `data/evals/`: labels, the answer files and saved runs. The agent never sees the answers.
- `logs.csv`: real usage, one row per finished run. It is not in git. Our database replaces it once it's in place.

For the production pilot, each kind of data has one home. The knowledge base stays in git, under review. The search index is built from it and can be rebuilt. One database holds tickets, decisions, reviews and the audit trail.

Diagnostic checks are simulated from these records. When the agent runs a check, the tool returns what that check recorded on that ticket. If the ticket has no such check, it returns no result.

## Not for now

- Real integrations. Every tool is simulated and says so in its result.
- More than one company.
- Fixes that run without a person. We'll consider this for one routine family at a time, once its record earns it.
- Conversations or follow-up questions. The agent never waits for a reply from the user.
- Linking tickets into a major incident. Our records have no outages to learn from.
- Agents that change themselves. A system may propose a change to its instructions, but a person approves it and our evaluations decide if it stays.
- Training our own models. The classifier in our evaluations is a yardstick and never decides a ticket.
- German. Both modes will need it, in tickets and in answers, once English is proven. Until then the knowledge base and the agent's instructions are in English.
