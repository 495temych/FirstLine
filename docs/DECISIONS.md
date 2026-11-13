# Decisions

Each design decision so far, with its reason and its trade-off.

## LangGraph

- **Decision:** orchestrate triage as a LangGraph `StateGraph`.
- **Reason:** the flow has three human gates, and which one comes next depends on earlier answers. Gates become nodes, state is typed, and routers are pure functions that can be tested alone.
- **Trade-off:** more framework than one model call needs, and a node re-runs from its first line on resume, so side effects must live in their own nodes.

## Single-shot triage

- **Decision:** one model call per ticket, with no follow-up questions.
- **Reason:** it adds no latency or session state, keeps the classification easy to inspect, and forces the agent to state what is missing, which gives better escalation summaries.
- **Trade-off:** the agent can't investigate. Some real L1 issues need back-and-forth, and an underspecified ticket like "My VPN keeps disconnecting" can land on different paths from run to run.

## Local embeddings

- **Decision:** embed with `all-MiniLM-L6-v2` on the local machine.
- **Reason:** no API cost per query, and ticket text isn't sent to an embedding service.
- **Trade-off:** a ~90 MB model download and a heavy `torch` dependency, and the model is built for English.

## Section-level retrieval

- **Decision:** embed each playbook section, score a playbook by its best section, and return that playbook without its Symptoms section, plus the best policy or reference units up to 2. `company-profile.md` and the escalation queues still split by `##` section, and policies stay whole.
- **Reason:** a ticket describes symptoms, while the agent needs checks, fixes and escalation rules. Matching sections finds the playbook, and returning it whole gives the agent the rest. Scoring playbooks apart from policies also stops a policy from pushing out the playbook, which took the hit rate to 84% after commit 2.
- **Trade-off:** one ticket returns more text, so each model call costs more. Any new reference document still has to be added to `REFERENCE_DOCS`.

## Matching a playbook: score or clear margin

- **Decision:** a playbook matches if its best section scores at least 0.52, or scores at least 0.40 and beats the next playbook by 0.15.
- **Reason:** long tickets score high, and short requests score low but often favour one playbook clearly. One number can't serve both. Each attempt is below, on `dev`, the short requests in the rules set, and `unseen_dev`:

| Attempt | `dev` hit rate | Rules set hit rate | `unseen_dev` false matches | Outcome |
|---|---|---|---|---|
| Threshold 0.35, as before | 100% | 91% | 100% | Failed: it rejects nothing |
| Threshold 0.50 | 100% | 74% | 13.5% | Failed: it loses a quarter of short requests |
| Threshold 0.55 | 99.2% | 52% | 0% | Failed: it loses half of short requests |
| Margin 0.10 alone | 95.3% | 83% | 5.8% | Failed: `dev` barely clears the floor |
| Margin 0.15 alone | 80.6% | 78% | 0% | Failed: under the floor |
| Score 0.52, or 0.40 with margin 0.15 | 100% | 87% | 3.8% | Chosen |

- **Trade-off:** the two numbers were tuned on `unseen_dev`, so 3.8% is a tuned score. `unseen_held_out` stays unopened as the exam. The imported tickets are templated, which flatters every number here. A bare title from an unknown family still false-matches 36.5% of the time, and the rules set misses three requests.

## Top 2 units

- **Decision:** return up to 2 units: the best playbook if one matches, then the best policy or reference units scoring at least 0.35.
- **Reason:** the threshold keeps irrelevant grounding from the model. Two units let one query pull a playbook and a policy together.
- **Trade-off:** set by inspection, on 21 documents and 99 units.

## No tools with retrieval off

- **Decision:** when retrieval is off, the model gets no tools at all, and no path is chosen.
- **Reason:** an agent with no grounding shouldn't be able to propose an action. It also shows plainly what the knowledge base adds.
- **Trade-off:** the on/off comparison stays visual rather than measured, and those runs aren't logged.

## Checkpoints in Postgres

- **Decision:** store graph state in Supabase through LangGraph's Postgres checkpointer, replacing `checkpoints.sqlite`. `backend.migrate` creates its tables and turns row-level security on. The backend never creates them.
- **Reason:** a pending confirmation is stored thread state. Each ticket has its own thread, and its id is in the dashboard's URL, so a paused ticket survives a reload or a backend restart, on any machine that reaches the database.
- **Trade-off:** the Assistant needs the database to keep a paused run. Without `SUPABASE_DB_URL` runs are kept in memory and a restart loses them.

## Logging from the final state

- **Decision:** the `log` node writes one row, once, when a run reaches a final state.
- **Reason:** `confirmed` is known by then, and there is a single place that writes the log.
- **Trade-off:** a run left at a confirmation card and abandoned for a new query is never logged.

## Mistake costs

- **Decision:** score mistakes in CHF, not just accuracy.
- **Reason:** a routine unlock on a possible compromise is far worse than a needless escalation, and a plain accuracy score treats them the same.
- **Trade-off:** the costs are assumptions. CHF 120 comes from 2 hours at CHF 60, and CHF 2,000 is an estimate that dominates the total.

## FastAPI and React instead of Streamlit

- **Decision:** a thin FastAPI backend around the graph, and a React, Vite and TypeScript dashboard, laid out as in UnderCover.
- **Reason:** Streamlit reruns the whole script on each click, which suited three human gates badly. An API with a separate front end keeps gates and logic in one place, and the Inbox and a hosted demo need it anyway.
- **Trade-off:** a second toolchain and Node in CI, and API response types are written by hand in `dashboard/src/api.ts`.

## An answer names its gate

- **Decision:** answering a gate means naming it, and the API refuses an answer for any other gate.
- **Reason:** declining a fix leads straight to a ticket gate, so a bare yes or no from a repeated click could answer a gate nobody has read.
- **Trade-off:** one more field on each request.

## Browser tests with a stub model

- **Decision:** Playwright runs against the real API and graph, with `e2e/server.py` standing in for the model, on its own ports and temporary files.
- **Reason:** gates are the point of the product, so they're tested through the real stack, at no cost and with no risk of touching a real model or `logs.csv`.
- **Trade-off:** a slower check, and a Chromium download on setup.

## Confirmation on escalations

- **Decision:** an escalation ticket waits for a technician's confirmation, as a fix does.
- **Reason:** opening a ticket routes to an on-call queue, starts an SLA clock and notifies a technician.
- **Trade-off:** one more click on every escalation.

## Evaluations and usage statistics stay apart

- **Decision:** the Scoreboard reads saved evaluations, and the live statistics read the Assistant's runs in Supabase. Neither stands in for the other. The API records a run, not the graph, so evaluations need no switch to stay out of the record.
- **Reason:** a fixed labelled set measures quality, and real usage shows volume and speed.
- **Trade-off:** response time covers the agent's decision only, not the fix, so it is a proxy for time to resolution. Below five runs the app says the sample is too small.

## Automation counts outcomes, not proposals

- **Decision:** a run counts as automated only when the person approved the fix or said the self-serve steps worked. A declined fix, steps that didn't help and an escalation don't count, and nor does a run still waiting. The rate is over runs in scope.
- **Reason:** the measure is technician time saved, as in the Queue's value panel. A proposal the person turned down saved nobody anything.
- **Trade-off:** while runs wait at a gate, the rate reads low until they're answered.

## The Queue is the core product

- **Decision:** build around a first pass on every ticket, with the Queue as the core and the Assistant as a front door. The headline measure is technician time per ticket against model cost.
- **Reason:** only about a third of tickets show failures L1 could fix alone, so most of the value is in right-first-time routing and investigation, not in resolving tickets.
- **Trade-off:** that third is a rough measure from who owns each failing check, and the time saved rests on assumed minutes, because the records have no handling times.

## No trained model

- **Decision:** the dataset supplies the knowledge base, evaluations, simulated checks and a privacy test. We train nothing except a simple classifier, which is a yardstick and never decides a ticket.
- **Reason:** 745 templated synthetic tickets would teach a model the generator's pattern. A free classifier shows whether Claude earns its cost on routing.
- **Trade-off:** the classifier may score very well on tickets this alike, which says as much about the data as about Claude. Its value then rests on investigation and write-ups.

## SEC-04 counts lockouts the ticket describes

- **Decision:** two or more lockouts count under SEC-04 §4.2 whether they're in the records or stated in the ticket. So a stale phone that keeps locking an account goes to `SEC-INCIDENT`, not to a routine unlock.
- **Reason:** a needless escalation costs CHF 120, and a wrong unlock costs CHF 2,000. The policy says what to do, whatever past tickets did.
- **Trade-off:** most lockout tickets go to security, though a real desk would call many of them a harmless phone. No imported ticket now expects `unlock_ad_account`, so only the rules set tests it. Code can guard the records, but a count in the ticket text has to be read by the model.

## Rules in code, in their own node after the model

- **Decision:** the rules live in `agent/rules.py` as pure functions of the decision, the requester's record, what search found and the mode. A new `enforce` node runs them between `triage` and the gates, and keeps any override in state with the rule, its reason, what the agent proposed and the code that enforced it. Supabase keeps it in `decisions.rule`.
- **Reason:** the model proposes and code decides. A node of its own keeps the routers pure, runs the rules before any gate, and puts each override in the trace as a step of its own.
- **Trade-off:** the first rule that changes a decision wins, so SEC-04 runs before the risk tier. A third rule will need its order thought through.

## What counts as a lockout ticket

- **Decision:** SEC-04 in code treats a ticket as a lockout when the model proposed `unlock_ad_account`, or search matched the `account-lockout` playbook or the SEC-04 policy. It ignores the model's own cause.
- **Reason:** a rule that trusts the model's words can be talked out of. Search is deterministic and the proposed tool is a fact, so the model can't skip SEC-04 by calling the lockout something else.
- **Trade-off:** a printer ticket from a user with 2 lockouts that happens to match the lockout policy would go to security too. A needless escalation costs CHF 120 against CHF 2,000 for a wrong unlock, so the rule leans that way on purpose.

## The requester's record, without their name or email

- **Decision:** the model reads the requester's username, department, office, floor, device and groups. Their name, email and lockout count stay out. The Assistant's API requires a requester, while `run_triage` still runs without one.
- **Reason:** that's what a technician uses to triage, and the username and device id let the model fill in a fix with real values instead of `current.user`. Only what the task needs leaves, as `docs/SWISS.md` says. The lockout count was shown at first, and on `dev` it went from no SEC-04 failures to 7, CHF 17,720 in mistakes: the invented records show 0 lockouts for requesters whose tickets describe repeated ones, and the model believed the records. A firmer instruction brought it to 2. Hiding the count leaves SEC-04 on the records to code and the text to the model, as before.
- **Trade-off:** the model can't use a count of 1 to call a lockout routine, as on T-021, so it may escalate one it could have fixed. A needless escalation costs CHF 120, against CHF 2,000 for a wrong unlock.

## Evaluations run in Queue mode

- **Decision:** evaluations pass each ticket's requester and run in Queue mode, where a technician confirms every fix, so the risk-tier rule doesn't apply. SEC-04 does.
- **Reason:** the Queue is the core product, and the labels score the fix itself. In Assistant mode a sensitive fix, such as `restart_print_spooler` on T-003, would become a ticket and count as wrong.
- **Trade-off:** the Assistant's own behaviour, sensitive fixes becoming tickets, is checked by tests, not scored.

## Named causes by rule

- **Decision:** a ticket takes the cause its `root_cause` names first, using rules written on the knowledge base split. Vaguer wording counts only if nothing precise matches. Held-out tickets were labelled by the same rules, and nobody read them.
- **Reason:** the labels can be reproduced and reviewed cause by cause, with no model cost and no reading of held-out text.
- **Trade-off:** many records name several causes, and rules are approximate, so some tickets sit under the wrong cause. Costs and paths are set per cause, so a person reviews 47 causes rather than 745 tickets.

## One call against a loop, and nothing in between

- **Decision:** commit 7 compares two designs: today's one call, and an agent loop with read-only tools. It tries the loop on samples first and keeps it only if it beats one call by more than the noise, for its extra cost.
- **Reason:** the comparison is what shows the method, and two designs show it as well as three. The loop is also what the Queue needs.
- **Trade-off:** we dropped a fixed workflow, where code runs a family's checks before one call. In the knowledge base split every family has the same three checks, so that workflow might match the loop for less, and we won't know.

## Commit 7 in three parts, and the Assistant as a conversation

- **Decision:** on 11 November 2026 the owner split commit 7. 7a builds the loop and its tools with a stub model, 7b measures it against one call, and 7c turns the Assistant into a chat whose reply shows the agent's steps as a checklist. The Assistant runs whichever design 7b keeps, so `docs/SPEC.md`'s "one model call" for the Assistant changes in 7c, if the loop wins.
- **Reason:** the loop is the sprint's biggest commit, and building it free before paying to measure it keeps each step small. Showing every step answers "why did it decide this?" on the page people use, not only in Langfuse.
- **Trade-off:** a loop makes the Assistant slower, a few seconds instead of about one, which the checklist makes visible rather than hides. It looks like a chat before it can hold one: follow-up questions wait for Sprint 2's commit 12. The page reads the steps every second, as the Queue does, rather than streaming them, which is simpler and survives a reload, at up to a second's delay.

## The Assistant runs the loop before 7b measures it

- **Decision:** on 12 November 2026 the owner moved 7c before 7b. The Assistant runs the loop and shows each step as a live checklist, while the Queue and evaluations stay on one call, the measured default, until 7b compares the two.
- **Reason:** the checklist is the clearest demonstration of what the agent does and why, and it costs nothing to build with the stub model. The Assistant is where a person watches one ticket, so it's where the steps are worth seeing.
- **Trade-off:** the Assistant now runs a design nobody has measured against one call, and costs up to 7 model calls a ticket, capped at CHF 0.01. If 7b finds the loop doesn't earn its cost, the Assistant goes back to one call, and the checklist shows one call's stations.

## Keeping the loop, by a rule set before the runs

- **Decision:** on 13 November 2026, before any loop run, the owner agreed this rule. For each model, keep the loop if, on the development sample, the low end of its net saving per ticket is above what one call saves on the same tickets, with no security mistake on any set, no more invalid answers than one call on the same tickets, at under CHF 0.10 a ticket. Three models run the loop: Gemini 3.1 Flash-Lite, the default; Qwen 3.7 Flash, the benchmark rule's pick and the cheapest; and Claude Haiku 5.5, a Claude model likely the best at calling tools. Each runs 67 tickets: the development sample (36), the unseen sample (6) and the full rules set (25), for about CHF 0.75 in all, after a five-ticket check of each.
- **Reason:** setting the rule first stops the result from choosing the rule. The full rules set holds the repeat-lockout tickets, so the safety test means something; its five-ticket version may not include them. Invalid answers are in the rule because the model choice was overridden on them before. One call's side comes from its saved full runs, cut to the loop's tickets, so the comparison is paired and costs nothing.
- **Trade-off:** 36 development tickets show only a large difference, so "no clear gain" is a likely answer. Six unseen tickets are too few to judge saving there, so they count only for safety. Running every model on the loop would cost about CHF 10 on the full sets, for an answer the samples may already give. Full-set loop runs happen only for a model the rule keeps, and only with the owner's go-ahead on their cost.
- **Result (13 November 2026, 201 loop tickets and 201 one-call tickets, about CHF 0.30 in all):** the rule keeps the loop for none of the three. On the 36 development tickets, one call saves CHF 9.25 a ticket with Haiku 5.5 and the loop CHF -5.78; Qwen goes from CHF 0.94 to -5.19, and Gemini from CHF 1.78 to 1.03. Haiku investigates most thoroughly, 3.2 lookups a ticket, 37 of the 39 labelled checks run and every citation valid, and still gets worse. The main reason is a flaw in the loop's design, not noise: `lookup_requester` gives the model the records' lockout count, which one call hides on purpose (see "Known limitations"). On INC-ALP-0036 and INC-ALP-0057 the records say 0 lockouts while the ticket describes repeats, and every model cited the 0 to rule SEC-04 out, so Haiku and Qwen each made 2 security mistakes against one call's 0 and 1. Haiku also sent 4 escalations to the wrong team after its checks. Gemini barely investigates, 0.4 lookups a ticket, and 8 of its 14 citations named steps that never ran, which code dropped. On the rules set Gemini's loop saves CHF 9.76 against one call's 7.84, its only gain. Qwen's and Haiku's one call were re-run on the same 67 tickets with the current instructions, for about CHF 0.05, so both sides of each pair share instructions, labels and knowledge base.
- **Owner's call (13 November 2026):** the Assistant keeps the loop, against the rule's verdict, and the lockout count stays in `lookup_requester` for now. The economic model is to be revisited first, since it may not weigh what investigating is worth to a technician, such as the handover. The Queue and evaluations stay on one call.


## The handover and citations, filled in by code

- **Decision:** a loop escalation carries a handover that code writes from the records, the ticket and the loop's own steps: the requester, device, priority, SLA and its deadline in Zürich business hours, applications, the checks with their results, similar incidents and what's still unknown. The model writes only the likely cause, what it ruled out and the next step. Each lookup's reply names its step id, the model cites the steps its decision rests on, and code drops any citation of a step that didn't run, and counts it.
- **Reason:** the facts are already in code's hands, so asking the model to copy them only adds a chance to get them wrong. A receiving team trusts a handover whose facts are known to come from the records. Checking citations is the cheapest guard against a decision that claims evidence it never saw.
- **Trade-off:** the SLA deadline comes from each queue's typical SLA in `data/kb/escalation-queues.md`, at 9 business hours a day, not from the imported tickets' own SLA plans, whose names don't agree with each other. A typed Assistant ticket has no submitted time or applications, so its deadline starts when it's triaged. One call has no steps to cite, so its escalations have no handover yet.

## The loop as one node that calls itself

- **Decision:** the loop is one `investigate` node, run once per model turn, that routes back to itself until the model decides or a limit stops it. The lookups it asks for run inside the node. The conversation and each step are in the graph's state, so each turn is a checkpoint.
- **Reason:** a checkpoint per turn is what lets 7c's checklist show each step as it lands, by reading the run's state, and lets a crashed run resume at its last turn. Running the lookups in the same node keeps a turn's tokens and cost on its own steps.
- **Trade-off:** a turn's lookups run after its model call, in the same node. Since commit 5 the retry wraps the model call alone, so a failure after the answer never asks the model again.

## The last turn may only decide

- **Decision:** after its 6th lookup, failed or not, the model gets one more turn with only `record_decision` offered. Lookups asked for past the limit in one turn aren't run, and say so. Code escalates to `DESK-SUPPORT` only when that last turn still doesn't decide, or when the run has spent CHF 0.01.
- **Reason:** cutting the loop off right at the limit would throw away six lookups' worth of evidence that a decision could use. Counting failed calls means a model that keeps sending broken calls still stops.
- **Trade-off:** the step limit is really 7 model turns, which the cost estimate assumes.

## Code decides what each lookup reads

- **Decision:** the model never names a ticket or a person. `run_check` reads the recorded checks of the ticket being worked, `lookup_requester` reads that ticket's requester, and an argument the schema doesn't have, such as a ticket id, is refused. Similar tickets come from a file of the knowledge base split's tickets only, `data/tickets/past_tickets.json`, with their root cause and first resolution step, searched by shared words.
- **Reason:** a ticket's text is untrusted, so it mustn't be able to steer a tool to another ticket or a held-out answer. The knowledge base split is already the playbooks' raw material, so its outcomes add no answer the agent shouldn't have. A plain word search needs no new service before Qdrant holds incidents in Sprint 2.
- **Trade-off:** checks are the technician's recorded results, not a live system, so a check the ticket's record lacks has no result, even where a real system would answer. Word overlap misses a similar ticket written in other words.

## One call's version doesn't change

- **Decision:** the loop's guide, lookups and limits join a run's version only for the loop design. A one-call run's version is computed as before, and runs record their design.
- **Reason:** the repeat guard has to tell the two designs apart, but saved one-call runs shouldn't look stale because new code was added beside them.
- **Trade-off:** a change to `agent/lookups.py` doesn't change a one-call version, which is right, since one call never runs it.

## Code writes the facts in a handover

- **Decision:** code fills in what it knows, including checks and evidence from tool results. The model writes only the likely cause, what's ruled out and the next step, citing that evidence.
- **Reason:** a one-sentence summary can't save the next team any work, and a model writing the facts could invent them.
- **Trade-off:** a larger ticket format, and the handover's quality needs its own measure.

## Run the check again after a fix

- **Decision:** after an approved fix, the check that failed runs again. The ticket closes if it passes, and escalates with both results if not.
- **Reason:** a tool that reports success doesn't prove the problem has gone, and a checkable result is what later autonomy has to rest on.
- **Trade-off:** the records hold no results from after a fix, so this is simulated, and the demo has to say so.

## Three sprints, one per course week

- **Decision:** Sprint 1 proves the agent locally, Sprint 2 makes it a system with Langfuse, Qdrant and Supabase, and Sprint 3 delivers it on Azure with Microsoft Foundry. The plan was cut from 23 commits to 18, keeping every tool and dropping dataset work, self-improvement and a third design.
- **Reason:** each sprint answers one question, and the order follows the risk: first whether it works, then whether it runs, then whether a client can trust it.
- **Trade-off:** there's no batch screen until Sprint 2, so the workflow that proves the value comes later than it would if we built it on SQLite first. In exchange, nothing gets built twice.
- **Update, 10 November 2026:** the sprints became the three phases of a reusable framework, `docs/FRAMEWORK.md`: feasibility on one machine, integrate and extend, and production. The business case moved to Sprint 1, because the budget is a feasibility question, and serving the lookup tools over MCP moved to Sprint 2's new commit 12 with the conversation, because it's integration. The loop itself stays in Sprint 1, where it's measured against one call.

## One home for each kind of data

- **Decision:** git holds the knowledge base and labels, Qdrant holds a search index, Supabase holds operational records, and Langfuse holds traces.
- **Reason:** with several services, two copies of the truth is the likeliest failure. An index that can be rebuilt can never disagree with its source for long.
- **Trade-off:** three services and three sets of keys for a project that could run on one Postgres database with `pgvector`.

## Qdrant over pgvector

- **Decision:** use Qdrant for search, even though Supabase includes `pgvector`.
- **Reason:** hybrid search suits tickets full of error codes, which embeddings match poorly. It's also a skill employers ask for.
- **Trade-off:** one more service. If hybrid search doesn't beat dense search on our scores, `pgvector` would be the simpler answer, and we'd say so.

## Move the search first, change it later

- **Decision:** the knowledge base moved to Qdrant with the same units, model and scores, before anything about search changes. Vectors are normalized and compared by dot product, which is the cosine similarity the thresholds were set on. Each query scores every section, and `retrieval.py` keeps its interface.
- **Reason:** if the scores move when only the engine changed, it's a bug. On all 206 practice tickets, in memory and in Qdrant Cloud, the results and playbook rankings are identical to the NumPy search, and no score differs by more than 0.0000002.
- **Trade-off:** scoring all 99 sections per query doesn't scale to a large knowledge base, and each search is now a network call. Both are fine at this size, and a top-k query is a one-line change once thresholds don't need every score.

## A stale index stops search

- **Decision:** each point records the knowledge base version and embedding model it was built from. Search checks them once and stops with the fix, `uv run -m agent.index`, instead of rebuilding on its own. Tests and `poe check` search in memory, so they stay offline.
- **Reason:** answers from an outdated index look right and are quietly wrong. Rebuilding from the app would make any running copy write to the shared index.
- **Trade-off:** a knowledge base change needs one more command before the app or a live evaluation runs.

## Langfuse Cloud, not self-hosted

- **Decision:** use Langfuse's hosted service, in its EU region.
- **Reason:** self-hosting needs Postgres, ClickHouse, Redis and blob storage, which is too much to run for a demo.
- **Trade-off:** traces leave our infrastructure, so redaction must come first. The hosted region needs confirming before we send anything.

## Langfuse traces through LangChain, and only its own spans

- **Decision:** trace through LangChain's callback, so every graph step and model call is recorded with no change to the graph. The client exports only Langfuse's own spans, masks emails, employee ids and IP addresses, and is off in tests.
- **Reason:** the Anthropic SDK traces each call itself, and Langfuse exports those spans by default, which counted every call's cost twice and bypassed the mask.
- **Trade-off:** another tool's OpenTelemetry spans won't reach Langfuse unless we allow them. The mask is a few patterns, not a full redaction, which Sprint 3's guardrails take further.

## Saved runs become Langfuse experiments by replay

- **Decision:** `evals.langfuse_upload` mirrors the practice sets as datasets and replays each set's newest saved run as an experiment. Its task returns the saved decision, and its scores come from our scoring code.
- **Reason:** history moves to Langfuse with no model calls, and the scores match the Scoreboard exactly.
- **Trade-off:** replayed traces carry the upload time, not the run's, which goes in metadata. They show the decision, not the model call behind it.

## Method over dataset

- **Decision:** the project shows a method for automating a process with AI, and IT support is the example. The labels are frozen after the owner's review, and later work goes into evals, observability, integration and deployment instead of the dataset.
- **Reason:** the tickets are synthetic, so their quirks teach little that transfers. Employers want to see how a problem is framed, measured, made safe and shipped.
- **Trade-off:** the labels stay approximate, drafted by rules with two causes reviewed by hand, so some measured mistakes are probably label errors. The README says so.

## Microsoft Foundry as a layer, not the platform

- **Decision:** use Foundry for models and Content Safety, and keep the agent, its gates and rules in LangGraph and our own code. Langfuse stays the one place for traces and experiments.
- **Reason:** Foundry is in demand in Zürich, and using its catalogue lets us compare vendors on the same exam. The human gates and resumable checkpoints are the core of the design, and Foundry Agent Service would replace them.
- **Trade-off:** we don't show Foundry's agent and tracing features, and two consoles stay in play, Azure for the model and Langfuse for traces.

## Azure instead of AWS

- **Decision:** deploy on Azure, with Container Apps, Key Vault, managed identity and API Management, and use Claude through Microsoft Foundry.
- **Reason:** Swiss enterprises often run on Microsoft, and doing it on a different cloud from the course shows the ideas are understood, not copied.
- **Trade-off:** Claude in Foundry has no Swiss or EU data zone that we could confirm, and a global deployment can route requests to the US. So the app can be Swiss-hosted while model calls aren't. Redaction carries that risk, and the direct Anthropic API is plan B.

## A structured decision, not keywords

- **Decision:** the model fills in one Pydantic class through a forced tool call, `record_decision`: rationale first, then cause, path, steps, tool and its input, queue, summary and priority. The tools and queues it may name are listed in the schema. Anything unreadable, or a tool or queue that doesn't exist, becomes an escalation to `DESK-SUPPORT`.
- **Reason:** scoring needs a clean path, tool, queue and cause on every ticket, and reading the path from keywords in free text failed quietly. Putting the rationale first makes the model reason before it commits.
- **Trade-off:** the fix tools are no longer bound as tools. The model names one in the decision, and code checks it. A forced tool call also rules out extended thinking with some models, which commit 8 tests.

## Two yardsticks

- **Decision:** every score sits beside always giving the most common answer and a TF-IDF and logistic-regression classifier trained on the knowledge base split. Both are free and run with the evaluation.
- **Reason:** "better than nothing" isn't a baseline. A model call has to beat a free model to earn its cost.
- **Trade-off:** the imported tickets are templated, so the classifier is a flattering bar on the development set (92% on path) and a weak one on short, real requests (36%). It can't name a team for a family it never saw. The rules set and unseen families keep it honest.

## Margins, kappa and costs in francs

- **Decision:** each share shows a 95% Wilson margin, and path agreement shows Cohen's kappa. Model cost is converted at an assumed USD 1 = CHF 0.80, kept in `evals/scoring.py`.
- **Reason:** 25 tickets give a margin near ±17%, so a small gap between two runs is noise. Kappa gives a constant answer no credit.
- **Trade-off:** the exchange rate is a fixed assumption, not a live one.

## Five tables, and states computed from them

- **Decision:** Supabase holds batches, tickets, decisions, reviews and events. A decision is apart from its ticket, a review apart from its decision, and the audit trail is one append-only table with a `kind` and a JSON `detail`. Whether a ticket waits for review isn't stored: it's a decision with no review. Allowed values are `check` constraints on text, not Postgres enums.
- **Reason:** what the agent said and what a person said must never overwrite each other, because comparing them is the measure. A stored status would be a second source of truth that drifts. Text checks are easier to change than enums.
- **Trade-off:** no table per event kind, so an event's detail isn't checked by the database. Reviewers are plain names until sign-in.

## Row-level security with no policies

- **Decision:** every table has row-level security on and no policies. The backend uses the direct database connection, and the browser never talks to Supabase.
- **Reason:** Supabase serves every `public` table over a REST API, and its publishable key is meant to be public. Without row-level security, anyone with that key could read and write tickets.
- **Trade-off:** the dashboard can't read Supabase on its own. Everything goes through the backend, which is where the rules live anyway.

## The board writes through to Supabase, and reads it back on start

- **Decision:** the board keeps its view in memory for the dashboard's polling, and saves each step to the store before showing it. It reads Supabase only when the backend starts. Tickets left queued or working then go back to the agent, and a ticket with a decision never does.
- **Reason:** the board polls every second, and a round trip to the pooler takes far longer here than reading memory. Saving first means the board never shows what isn't recorded.
- **Trade-off:** only one backend can run the Queue, because a second wouldn't see the first's changes until it restarted. A worker stopped mid-call costs that call again on restart.

## One store, two versions, one set of tests

- **Decision:** `backend/store.py` has a Postgres and a memory version, and each test of the store runs against both. The Postgres tests use a throwaway Postgres 17 in Docker, with the real migrations.
- **Reason:** the fast tests and the browser tests use memory, so it must behave as Postgres does, or they prove nothing. Running the same tests on both catches any drift.
- **Trade-off:** `poe check` now needs Docker, and its first run downloads the Postgres image.

## A technician's verdict is a Langfuse score

- **Decision:** every review sends `technician_verdict` (approved, corrected or rejected) to the ticket's trace, and the dashboard shows the trace's own steps from Langfuse.
- **Reason:** the trace then answers both questions in one place: why the agent decided, and whether a person agreed. Langfuse can filter and chart the verdicts with no code of ours.
- **Trade-off:** Langfuse needs a few seconds to show a new trace, so the dashboard asks again for up to 30 seconds. With tracing off, the panel says so.

## Parallel searches share one opening

- **Decision:** the embedding model and the Qdrant client open once under a lock, the client waits up to 30 seconds, and the search step retries a failed connection up to 3 times.
- **Reason:** two Queue workers opening Qdrant at once timed out on a slow network. A retried search costs nothing, unlike a retried model call.
- **Trade-off:** a dead network now takes longer to fail.

## The "How it works" page is built from the code

- **Decision:** `GET /api/overview` reads the route from LangGraph's own graph, the tools from `agent/tool_schemas.py`, the model and price from `agent/config.py`, and the results and example tickets from the newest development run. Only the plain-English explanations live in `backend/overview.py`.
- **Reason:** a page that explains the agent is only worth reading if it is true. Tests fail when a node or tool has no explanation, when the gates differ from the nodes that wait for a person, or when a drawn line isn't a route the graph takes.
- **Trade-off:** the explanations still need a person to keep them accurate, and the examples come from whichever development run is newest.

## Retrieval has its own page, and one rule decides a match

- **Decision:** saved retrieval scores keep each ticket's ranked playbooks, and the Retrieval tab draws them, replacing the Scoreboard's retrieval tables. `why_matched` in `agent/retrieval.py` is the one place that decides a match, and both search and the page's "Try a search" use it.
- **Reason:** a hit rate alone can't show why the thresholds sit where they do. The per-ticket scores show the gap between the weakest right match and the strongest unseen one, and a reader can test the rule on their own words for free.
- **Trade-off:** a saved development score grows from 1 KB to about 140 KB. Each ticket keeps only its best five playbooks, enough to explain it.

## A mistake costs money only when the technician misses it

- **Decision:** the business case prices the mistake bill times the share of wrong decisions a technician misses, assumed at 90% caught. The Queue measures the real share, from the labels of the decisions technicians approved.
- **Reason:** every decision is reviewed. Pricing every mistake as uncaught made each ticket lose CHF 68 on the development set, which contradicts the review the design depends on. Counting none would hide the risk.
- **Trade-off:** the headline rests on one assumption. The page shows where it turns, at 89% with the baseline, and lets a reader move it. The three security mistakes are CHF 6,000 of the CHF 9,960 bill, so the rules in Sprint 1's commit 6 should move it most.

## Choosing the model by net saving, by a rule set before the runs

- **Decision:** ten light models run through one harness on the full development, unseen and rules sets, and are ranked by net saving per ticket. The choice is the cheapest model on the Pareto front of net saving against cost whose net saving is within the margin of the best, with no security mistake on the rules set. Each lab's own API serves its models where we have a key, and OpenRouter the rest, pinned to one provider each.
- **Reason:** price alone favours a model that loses money through mistakes, and accuracy alone ignores what each model costs. Setting the rule first stops the result from choosing the rule. Pinning makes a run repeatable and its data path known.
- **Trade-off:** one run per model, so a gap within the margin is a tie. The instructions were tuned on Claude, which may favour it. Qwen's only provider can't force the decision tool, so it's only offered it.
- **Result (9 November 2026, about 2'550 model calls including re-runs, about CHF 2.25 billed against CHF 1.26 at list token prices):** on development, Qwen 3.7 Flash saves CHF 6.88 a ticket, Claude Haiku 5.5 CHF 6.86, GPT-6 Luna CHF 6.60 and Gemini 3.1 Flash-Lite CHF 6.49, all within one margin of each other, against Haiku 4.5's CHF 0.97. GLM 5.3 Flash and DeepSeek V4.1 Flash lose money even at their lowest reasoning effort, and GPT-5 nano leaves out required fields. The rule picks Qwen, but Qwen gives no decision on 31 of 52 unseen tickets and its host region is unconfirmed, against `docs/SWISS.md`. GPT-6 Luna is the next on the front, with no invalid answer on any set. **The default model isn't changed yet:** the owner will choose once the rule's gaps, invalid answers and region, are settled.
- **Why the classifier wins on development:** it saves CHF 10.72 a ticket there, more than any model, and loses CHF 8.00 on unseen families. Each ticket's label comes from its cause, and the family alone gives the right answer for 114 of 129 development tickets, so a classifier trained on the same families learns that map. 24 of GPT-6 Luna's 31 development misses are labelled auto-fix and escalated, and in 13 of them the playbook's own escalation rule supports escalating: many people affected, or the fix already tried. The owner kept the labels as they are, so development measures agreement with the cause-based labels, and the rules and unseen sets carry more weight than their size.

## Gemini 3.1 Flash-Lite as the default model, for now

- **Decision:** on 10 November 2026 the owner chose Gemini 3.1 Flash-Lite, through OpenRouter pinned to Google Vertex in the EU, over the rule's pick, Qwen 3.7 Flash.
- **Reason:** the four leaders tie on development, and paired tests can't separate them. Gemini saves the most on families with no playbook, CHF 3.31 a ticket against Qwen's loss of CHF 2.46, gives no invalid answers on either set, is the fastest at a median of 1.3 s, and keeps data in the EU. Qwen is cheaper by CHF 0.80 per 1'000 tickets, which is negligible next to a CHF 6 saving. `labs/model-comparison.ipynb` has the analysis.
- **Trade-off:** the rule written before the runs is overridden by conditions it didn't cover: saving on unseen families, invalid answers and region. The next benchmark should write them into the rule first. Gemini is weaker on disk encryption and laptop performance, and the loop is to be measured on it, so the choice may change once the loop runs.

## Retries around the call, not the node

- **Decision:** a model call that fails before the model answers, on a dropped connection, a rate limit or a server error, is tried again up to 3 times, with a wait of 1, then 2 seconds. The retry wraps the call itself, in `_ask` in `agent/graph.py`, not the LangGraph node that holds it. Searches keep their node retry.
- **Reason:** a node retry runs the whole node again, so anything that fails after the answer, such as reading the decision or running a lookup, would ask the model again and pay for a second answer. Around the call, only a call that never answered is repeated. A retried search costs nothing, so it can stay on the node.
- **Trade-off:** waits are short, so a provider down for longer than about 3 seconds fails the ticket, which the Queue then shows as failed.

## Each action runs once, by its key

- **Decision:** every action is keyed by its ticket and what it does, the tool and its input, in `agent/actions.py`. The key is claimed in the `actions` table before the action runs and keeps its outcome after. A second attempt returns the first outcome. A key claimed with no outcome, an action cut off by a restart, is held for a person, not run again. An action whose input doesn't fit its tool gives its key back, since nothing ran. The Assistant's actions are keyed by its run.
- **Reason:** a restart can come between an action and its record, and the board then waits for a decision that was already carried out. Running a real reset or opening a real ticket twice is worse than asking a person whether it happened. Claiming before running is the only order where a crash can't lead to a repeat.
- **Trade-off:** an action cut off mid-run needs a person to check it. A corrected decision is a different action, so it has its own key, and the same fix approved for the same ticket in two Assistant runs runs twice, because each run is its own ticket. The ticket isn't a foreign key, because an Assistant run acts before its record is saved.

## A batch's cost is stated before it starts

- **Decision:** the Queue states the next batch's model cost from the evaluations' own estimate, the dearest saved run's cost per ticket for today's model, and refuses a batch above CHF 0.25 or `QUEUE_BATCH_CAP_CHF`. A model with no price can't start a batch.
- **Reason:** one estimate for evaluations and the Queue means one number to trust. The dearest saved run errs on the side of stopping.
- **Trade-off:** a batch with the default model costs about CHF 0.01, so the cap only bites on a dear model or a much larger batch. A batch already started isn't stopped mid-way.

## A change ships only through the release gate

- **Decision:** `uv run -m evals.gate` runs a change on the two samples, 36 development and 6 unseen-family tickets, for about CHF 0.04 with the default model, or reuses a saved run of the same code. It refuses the change when, on either sample, path accuracy falls by more than the baseline's 95% margin of error or the mistake bill rises at all. Both runs of each sample go to Langfuse as experiments on the same dataset, and the gate reads their numbers back from there; if Langfuse hasn't shown them within a minute, it judges from the saved runs and says so. `--keep` makes a passing change the baseline, in `data/evals/baseline.json`.
- **Reason:** the margin on accuracy keeps the gate from refusing noise, and the mistake bill is the measure the business case turns on, so any rise is a reason to look. Reading back from Langfuse means what the gate judged is what anyone opening the experiments sees.
- **Trade-off:** the samples are small, so only a large fall in accuracy shows, and a rise of one mistake can refuse a harmless change from run to run. The live check showed both: a worse instruction left the development sample unchanged, 75% to 78%, and was refused on unseen families, 100% to 50%. A refused change's runs stay out of the repository. The gate isn't in CI yet, since it needs a model key.

## Known limitations

- **Synthetic knowledge base.** A real deployment needs real client documentation.
- **Simulated tools.** Production needs least-privilege service accounts for AD, Intune, PaperCut and ServiceNow.
- **Small corpus.** With 21 documents and 99 units, the thresholds and top 2 need revalidating at scale, and hundreds of units would need re-ranking.
- **Search by meaning only.** Error codes and bare titles match poorly. `T-012`, a short Outlook sign-in request, ranks `sso-mfa` first. Keyword matching arrives with Qdrant in Sprint 2.
- **The agent can invent parameters.** In a live Queue run it proposed a device id that isn't the requester's. It now reads the requester's username and device id, and the technician's review still catches the rest.
- **SEC-04 reads the records, not the ticket.** A count stated only in the text, such as "locked out twice today", is still the model's to read. On development the default model still unlocks INC-ALP-0036, a single lockout after a password reset that the labels send to security, on some runs and not others. A technician confirms every unlock in the Queue, and the Assistant hands every unlock to one.
- **Single turn only.** Some real L1 issues need back-and-forth, which this design can't handle.
- **No feedback loop.** The thresholds are set by inspection, not tuned from confirmed outcomes.
- **Retrieval's cost and latency aren't measured.** The on/off switch shows the difference but doesn't quantify it.
- **Fixed top 2.** A weak policy still comes back if it clears the threshold, and an ambiguous ticket can't pull a second playbook.
- **Hardcoded tool schemas.** They live in `agent/tool_schemas.py`. MCP would make them discoverable and keep credentials out of the agent.
- **English only.** CorpLabs is Swiss, so production needs multilingual embeddings and German instructions.
- **Partial ITSM alignment.** The ticket maps to ServiceNow's incident schema but omits `impact`, `urgency`, `cmdb_ci` and `work_notes`.
- **Paths vary on underspecified tickets.** "My VPN keeps disconnecting" has three documented causes, so it can land on different paths from run to run. Retrieval is deterministic.
- **The baseline rests on draft labels.** Causes are drafted by rules and not all read by the owner yet, so some of the agent's "mistakes" may be wrong labels. The baseline runs again once they are confirmed.
- **The share of mistakes caught is assumed.** The business case rests on 90%, and the Queue's reviews so far are too few to measure it.
