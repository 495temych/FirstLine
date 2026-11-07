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

## The SQLite checkpointer

- **Decision:** store graph state in `checkpoints.sqlite`.
- **Reason:** a pending confirmation is stored thread state, with no database server to run. Each ticket has its own thread, and its id is in the dashboard's URL, so a paused ticket survives a reload or a backend restart.
- **Trade-off:** one machine only.

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

- **Decision:** the Scoreboard reads saved evaluations, and the live statistics read `logs.csv`. Neither stands in for the other.
- **Reason:** a fixed labelled set measures quality, and real usage shows volume and speed.
- **Trade-off:** response time covers the agent's decision only, not the fix, so it is a proxy for time to resolution. Below five logged runs the app says the sample is too small.

## The Queue is the core product

- **Decision:** build around a first pass on every ticket, with the Queue as the core and the Assistant as a front door. The headline measure is technician time per ticket against model cost.
- **Reason:** only about a third of tickets show failures L1 could fix alone, so most of the value is in right-first-time routing and investigation, not in resolving tickets.
- **Trade-off:** that third is a rough measure from who owns each failing check, and the time saved rests on assumed minutes, because the records have no handling times.

## No trained model

- **Decision:** the dataset supplies the knowledge base, evaluations, simulated checks and a privacy test. We train nothing except a simple classifier, which is a yardstick and never decides a ticket.
- **Reason:** 745 templated synthetic tickets would teach a model the generator's pattern. A free classifier shows whether Claude earns its cost on routing.
- **Trade-off:** the classifier may score very well on tickets this alike, which says as much about the data as about Claude. Its value then rests on investigation and write-ups.

## Three sprints, one per course week

- **Decision:** Sprint 1 proves the agent locally, Sprint 2 makes it a system with Qdrant, Supabase and Langfuse, and Sprint 3 delivers it on Azure.
- **Reason:** each sprint answers one question, and the order follows the risk: first whether it works, then whether it runs, then whether a client can trust it.
- **Trade-off:** there's no batch screen until Sprint 2, so the workflow that proves the value comes later than it would if we built it on SQLite first. In exchange, nothing gets built twice.

## One home for each kind of data

- **Decision:** git holds the knowledge base and labels, Qdrant holds a search index, Supabase holds operational records, and Langfuse holds traces.
- **Reason:** with several services, two copies of the truth is the likeliest failure. An index that can be rebuilt can never disagree with its source for long.
- **Trade-off:** three services and three sets of keys for a project that could run on one Postgres database with `pgvector`.

## Qdrant over pgvector

- **Decision:** use Qdrant for search, even though Supabase includes `pgvector`.
- **Reason:** hybrid search suits tickets full of error codes, which embeddings match poorly. It's also a skill employers ask for.
- **Trade-off:** one more service. If hybrid search doesn't beat dense search on our scores, `pgvector` would be the simpler answer, and we'd say so.

## Langfuse Cloud, not self-hosted

- **Decision:** use Langfuse's hosted service, in its EU region.
- **Reason:** self-hosting needs Postgres, ClickHouse, Redis and blob storage, which is too much to run for a demo.
- **Trade-off:** traces leave our infrastructure, so redaction must come first. The hosted region needs confirming before we send anything.

## Azure instead of AWS

- **Decision:** deploy on Azure, with Container Apps, Key Vault, managed identity and API Management, and use Claude through Microsoft Foundry.
- **Reason:** Swiss enterprises often run on Microsoft, and doing it on a different cloud from the course shows the ideas are understood, not copied.
- **Trade-off:** Claude in Foundry has no Swiss or EU data zone that we could confirm, and a global deployment can route requests to the US. So the app can be Swiss-hosted while model calls aren't. Redaction carries that risk, and the direct Anthropic API is plan B.

## Known limitations

- **Synthetic knowledge base.** A real deployment needs real client documentation.
- **Simulated tools.** Production needs least-privilege service accounts for AD, Intune, PaperCut and ServiceNow.
- **Small corpus.** With 21 documents and 99 units, the thresholds and top 2 need revalidating at scale, and hundreds of units would need re-ranking.
- **Search by meaning only.** Error codes and bare titles match poorly. `T-012`, a short Outlook sign-in request, ranks `sso-mfa` first. Keyword matching arrives with Qdrant in Sprint 2.
- **Single turn only.** Some real L1 issues need back-and-forth, which this design can't handle.
- **No feedback loop.** The thresholds are set by inspection, not tuned from confirmed outcomes.
- **Retrieval's cost and latency aren't measured.** The on/off switch shows the difference but doesn't quantify it.
- **Fixed top 2.** A weak policy still comes back if it clears the threshold, and an ambiguous ticket can't pull a second playbook.
- **Hardcoded tool schemas.** They live in `agent/tool_schemas.py`. MCP would make them discoverable and keep credentials out of the agent.
- **English only.** CorpLabs is Swiss, so production needs multilingual embeddings and German instructions.
- **Partial ITSM alignment.** The ticket maps to ServiceNow's incident schema but omits `impact`, `urgency`, `cmdb_ci` and `work_notes`.
- **Paths vary on underspecified tickets.** "My VPN keeps disconnecting" has three documented causes, so it can land on different paths from run to run. Retrieval is deterministic.
