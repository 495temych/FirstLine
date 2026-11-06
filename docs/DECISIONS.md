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

## Mixed-granularity retrieval

- **Decision:** embed each single-issue playbook whole, and split `company-profile.md` into one unit per `##` section.
- **Reason:** a mixed-topic file embedded whole dilutes its topics, and would bury the one paragraph, such as SEC-04, that decides the path.
- **Trade-off:** two kinds of unit in one index, and any new reference document has to be added to `REFERENCE_DOCS`.

## The 0.35 threshold with top 2

- **Decision:** return up to 2 units, ranked across all sources, each scoring at least 0.35.
- **Reason:** the threshold makes "no confident match" explicit, so the model isn't handed irrelevant grounding. Two units let one query pull a playbook and a policy section together.
- **Trade-off:** both numbers were set by inspection on a corpus of 17 units, and need revalidating at scale.

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

## Known limitations

- **Synthetic knowledge base.** A real deployment needs real client documentation.
- **Simulated tools.** Production needs least-privilege service accounts for AD, Intune, PaperCut and ServiceNow.
- **Small corpus.** With 12 documents and 17 units, the threshold and top 2 need revalidating at scale, and hundreds of units would need re-ranking.
- **Single turn only.** Some real L1 issues need back-and-forth, which this design can't handle.
- **No feedback loop.** The threshold is set by inspection, not tuned from confirmed outcomes.
- **Retrieval's cost and latency aren't measured.** The on/off switch shows the difference but doesn't quantify it.
- **Fixed top 2.** A weak second unit still comes back if it clears the threshold, and an ambiguous ticket can't pull a third.
- **Hardcoded tool schemas.** They live in `agent/tool_schemas.py`. MCP would make them discoverable and keep credentials out of the agent.
- **English only.** Limmatica is Swiss, so production needs multilingual embeddings and German instructions.
- **Partial ITSM alignment.** The ticket maps to ServiceNow's incident schema but omits `impact`, `urgency`, `cmdb_ci` and `work_notes`.
- **Paths vary on underspecified tickets.** "My VPN keeps disconnecting" has three documented causes, so it can land on different paths from run to run. Retrieval is deterministic.
