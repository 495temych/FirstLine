# Decisions

Each design decision so far, with its reason and its trade-off. The background below it is what the README used to carry in full.

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
- **Reason:** a pending confirmation is stored thread state rather than Streamlit session variables, with no server to run.
- **Trade-off:** one machine only. The app also keeps `thread_id` in session state, so a paused thread can't be reopened from the UI after a restart.

## Logging from the final state

- **Decision:** the `log` node writes one row, once, when a run reaches a final state.
- **Reason:** `confirmed` is known by then, and there is a single place that writes the log.
- **Trade-off:** a run left at a confirmation card and abandoned for a new query is never logged.

## Mistake costs

- **Decision:** score mistakes in CHF, not just accuracy.
- **Reason:** a routine unlock on a possible compromise is far worse than a needless escalation, and a plain accuracy score treats them the same.
- **Trade-off:** the costs are assumptions. CHF 120 comes from 2 hours at CHF 60, and CHF 2,000 is an estimate that dominates the total.

## Known limitations

- **Synthetic knowledge base.** All KB articles were written for this demo. Real deployment needs actual company documentation.
- **Mocked tool execution.** No real actions are taken. Production requires service accounts with least-privilege access to AD, Intune, PaperCut, and ServiceNow.
- **Small corpus (12 docs, 17 retrievable units).** Threshold calibration and top-k retrieval need revalidation at scale. Re-ranking becomes necessary at hundreds of units.
- **Single-turn only.** Some real L1 issues genuinely require back-and-forth. The current architecture can't handle those — single-turn is a constraint, not just a design choice.
- **No feedback loop for threshold tuning.** The 0.35 threshold is set by inspection. Production would use operator-confirmed outcomes (was the retrieval actually helpful?) to tune it per-category. This connects directly to RAG-on vs. RAG-off cost tradeoff analysis.
- **RAG cost/latency tradeoff not measured.** RAG-on adds one embedding inference + file I/O per query. For high-volume deployments, a cost/latency comparison of RAG-on vs. RAG-off is a valid economic input — the toggle in the demo makes this comparison observable but not quantified.
- **MCP as natural evolution.** The current function-calling tool schemas are hardcoded in `agent/tool_schemas.py`. MCP would replace this with a discoverable, credential-isolated connector layer — making tool updates a config change rather than a code change.
- **German-language support missing.** Limmatica AG is a Swiss company. KB articles and the triage prompt are English-only. A production deployment needs multilingual embeddings and a German prompt.
- **ITSM schema alignment is partial.** The escalation ticket maps to ServiceNow's incident schema but omits `impact`, `urgency`, `cmdb_ci` (configuration item), and `work_notes`. A complete integration would populate these from the KB article and device context.
- **Fixed top-k, not top-p.** Retrieval always returns up to 2 units (gated by the 0.35 threshold). Top-p (nucleus) retrieval over normalized scores — keep units until cumulative similarity mass crosses a cutoff — would give adaptive breadth instead: one obviously-dominant match returns alone, a genuinely ambiguous query can pull more than 2. Not implemented; the corpus is too small right now to tell the two approaches apart empirically.
- **Path accuracy varies run to run on underspecified queries.** `evals/runner.py`'s golden set found one query ("My VPN keeps disconnecting" alone) where single-shot classification legitimately lands on different paths across runs, because the KB article documents multiple causes and the query doesn't disambiguate between them. See [Evaluation](#evaluation).

## Background

### Why LangGraph, in detail

The triage flow has three human gates, and which one comes next depends on earlier answers (decline a fix → draft a ticket → confirm the ticket). Before, that lived in a string state machine in `app.py` (`tool_state`, `decline_ticket`, `pending_log_row`) plus a function that patched `logs.csv` after the fact. As a `StateGraph`:

- **Gates are nodes.** `confirm_*` and `self_serve_wait` only call `interrupt()` and store the answer; the side effects (`execute_tool`, `create_ticket`) are separate nodes that can only run after an answer exists.
- **One typed state, one log write.** `GraphState` carries everything; the `log` node writes the row once, from the final state, so `confirmed` is known when it is written.
- **Testable routing.** Routers are pure functions with `Literal` return types, and `parse_path` is a pure function. `agent/tests/test_graph.py` covers both, plus every flow end-to-end with a fake model.
- **Durable pauses.** The app uses a SQLite checkpointer, so a pending confirmation is part of the stored thread state rather than Streamlit session variables. `triage` retries transient Anthropic API errors only (`RetryPolicy`).

Trade-off: a run is logged when it reaches a final state, so a run left sitting at a confirmation card and abandoned by starting a new query is not logged.

### How the paths behave

**Scope check:** OUT_OF_SCOPE is reserved for requests unrelated to workplace technology (weather, personal advice, general knowledge, creative tasks). An IT-related request that needs identity/access-management, security-team, or admin-level action beyond user self-service — adding someone to a security group, granting elevated permissions, a suspected account compromise — is not out of scope. It's real IT work that exceeds desktop-support scope, so it routes to ESCALATE, not OUT_OF_SCOPE.

**SELF_SERVE fallback:** if the returned steps don't fix it, the run waits at `self_serve_wait` with two buttons, "This resolved it" (logs and ends) and "This didn't resolve it — escalate to a technician", which routes through `draft_ticket` into the same ticket-preview/Confirm/Cancel gate as ESCALATE — reusing `create_escalation_ticket` rather than adding a new tool. The generated summary explicitly notes self-serve was already attempted, so the receiving technician doesn't repeat those steps; queue defaults to `DESKTOP-SUPPORT`, priority `P3-Normal`.

**AUTO_FIX decline:** declining a proposed fix doesn't end the flow either. The `draft_ticket` node pre-fills an escalation ticket from the diagnosis already produced in that response — no second model call — carrying the declined tool's name, a fixed reason ("User declined proposed automated fix; issue persists"), the existing diagnostic summary, and a `P3-Normal` default priority. That ticket gets its own, separate Confirm ("Send to ServiceNow") / Cancel step before `create_escalation_ticket` actually runs. Accepting AUTO_FIX and declining it both end up at the same human-confirmation pattern — they diverge only in what's being confirmed, not in whether confirmation is required.

**RAG off:** none of the four paths above apply. The agent is given no tools at all for that call, so it cannot classify or act — it just returns hedged, ungrounded text, and the UI shows a distinct `NO TOOLS (RAG OFF)` badge instead of a path badge.

### How it works

**Stack:** Claude API via `langchain-anthropic` (generation + tool-use), LangGraph (orchestration, human-in-the-loop interrupts, SQLite checkpointer), `sentence-transformers` with `all-MiniLM-L6-v2` (local embeddings — no API cost per query), Streamlit (frontend driven by graph state).

**Knowledge base:** 12 Markdown files. 11 are single-issue playbooks, each embedded whole as one retrieval unit. The 12th, `company-profile.md`, is a multi-topic org reference (systems, escalation queues, policies) — it's split into one unit per `##` section instead, so a query can match its one relevant section directly rather than the whole mixed-topic file. 17 retrievable units total. `retrieve()` returns up to the top 2 units (cosine similarity, threshold 0.35 per unit) ranked together regardless of source doc — this is what lets one query pull both an issue playbook and a policy section in the same call. Within each matched unit, individual lines are re-scored against the same query embedding for sentence-level highlighting (threshold 0.25) — same model, no extra inference cost, no additional dependencies.

**Decision flow:** single-shot (one LLM call per query). The model receives the query + up to 2 retrieved KB units — possibly from different source documents — and must classify immediately into SELF_SERVE / AUTO_FIX / ESCALATE / OUT_OF_SCOPE, synthesizing across all retrieved units, and call the appropriate tool. No multi-turn — missing information forces an explicit ESCALATE with reasoning rather than a clarifying question. When RAG is off, no tools are offered at all (not just no retrieval) — the agent can only respond in plain, ungrounded text; see the RAG on/off toggle below.

**Tool execution:** the agent returns a structured tool call (name + parameters). The app shows the proposed action to the operator before anything runs. On Confirm, the tool is dispatched. On Cancel, behavior depends on the path: for ESCALATE, nothing changes and no ticket is created; for AUTO_FIX, declining pre-fills an escalation ticket from the diagnosis already in that response (no new model call) and asks for a separate confirmation before it's sent. Every terminal state is logged with a timestamp.

### Why a knowledge base matters

A dispatch technician supporting multiple SME clients can't hold each client's environment in their head — Limmatica's AD group names aren't the same as the next client's, and policies get updated independently of any single technician's memory. Without retrieval, the model faces the same problem: it can only give generic advice — it has no way to know Limmatica's internal portal addresses, script paths, AD group names, or policy codes. The KB articles contain details that no pre-trained model, and no technician juggling several clients, could reliably carry:

- `vpn-gp.limmatica.corp` — the GlobalProtect gateway address post-migration
- `\\IT-TOOLS\Scripts\reset-vpn-profile.ps1` — the exact remediation script
- `Finance-RW` — the AD group that governs shared-drive access for Finance users
- `SEC-04` — the internal policy requiring escalation after 2+ lockouts in 24 h
- Q1 2026 AnyConnect → GlobalProtect migration context

This is where RAG's value is structural, not incidental: each client's KB lives and updates independently in its own retrieval source, so a technician (or the agent acting on their behalf) always pulls the *current* policy and config for *that* client at query time — without needing to have memorized it, and without risking a stale or cross-client mix-up.

**RAG on/off toggle**: Without RAG, an LLM falls back to generic, hedged advice with no specific references to client company's IT environment.

### Where this could run

| Integration point | How | ServiceNow field mapping |
|---|---|---|
| ServiceNow intake | REST API POST to `/api/now/table/incident` | `app.queue` → `assignment_group` |
| Ticket ID | Auto-generated `INC{random}` (simulated) | `app.ticket_id` → `number` |
| Caller | `current.user` resolved via Okta | `app.requested_by` → `caller_id` |
| Priority | `P3-Normal` / `P2-High` / `P1-Critical` | `app.priority` → `priority` (3/2/1) |
| Short description | One-sentence diagnostic from LLM | `app.summary` → `short_description` |
| Category | IT Support / Endpoint | hardcoded → `category` |

The tool schema (`create_escalation_ticket`) is already structured to map 1-to-1 onto a ServiceNow incident record. Wiring it to a real instance is a configuration change, not a redesign.

## Evaluation

The app surfaces two independent measurements side by side, each in its own expander, clearly labeled — neither stands in for the other.

**Evaluations** (`evals/`) run a labelled set through the real pipeline and save the result for the Scoreboard. The 25 development tickets are for working on the agent. The 25 held-out tickets check that a change generalizes. Both sets are ours, not an external benchmark. Scoring is plain code.

Path accuracy can vary from run to run on underspecified tickets such as "My VPN keeps disconnecting". Retrieval is deterministic.

**Live session stats** (`app/stats.py`, reading `logs.csv`) is a different measurement: real usage, not a fixed test set. `logs.csv` starts empty, and one row is appended after every query actually run through the app — timestamp, query, retrieved units, decision path, diagnostic summary, tool called, operator confirmation (AUTO_FIX rows only), escalation queue/priority (ESCALATE rows only), and measured response time. The app's "Live session stats" expander reads this file fresh on every render — never cached, unlike the golden-set numbers above — and reports total logged queries, count and % by decision path, automation rate (SELF_SERVE + AUTO_FIX over total minus OUT_OF_SCOPE), and average response time by path, labeled explicitly as **"Agent response time (proxy for MTTR — measures decision latency, not full ticket resolution)"** since it only times the model call that produces a decision, not how long a human then takes to act on it. Below five logged queries, the panel says the sample is too small for a stable rate rather than presenting a percentage as reliable. Run it standalone: `uv run -m app.stats`.

---

<details>
<summary><strong>RAG design decisions</strong></summary>

- **One file per KB article, except reference docs** — the 11 issue playbooks are each one retrieval unit (whole file, no chunking overhead, no boundary ambiguity). `company-profile.md` is different: it's a multi-topic org reference (systems, escalation queues, policies, quirks), not a single-issue article, so treating it as one unit would dilute its embedding across unrelated topics and bury the one section actually relevant to a query. It's chunked by `##` heading instead — one retrievable unit per section — so e.g. its "Governing policies" section can rank on its own merits.
- **Why company-profile.md needed this specifically:** it's the one doc every other KB article assumes as background (policy numbers, queue ownership, naming conventions) rather than a resolvable issue in itself. Embedded whole, a query like a lockout question would match it only weakly overall even though one paragraph (SEC-04) is exactly what determines the path — chunking surfaces that paragraph directly instead of relying on the model to find it inside a large, mixed-topic block.
- **Top-k=2, ranked across all units regardless of source doc** — `retrieve()` returns up to 2 units above the 0.35 threshold from one flat index spanning atomic docs and reference sections alike. This is what enables cross-document grounding: a query can pull one issue-playbook unit and one policy-section unit in the same call, and the agent is prompted to synthesize both rather than assume single-source grounding.
- **Threshold 0.35** — without it, retrieval always returns something, even for queries with no KB match, and the model may hallucinate grounding. The threshold makes the "no confident match" case explicit; it applies per-unit, so top-k can return 0, 1, or 2 units.
- **Sentence-level highlights** — same `all-MiniLM-L6-v2` model scores individual sentences against the query, threshold 0.25 (looser than the 0.35 unit-level threshold, since a highlight is illustrative, not a retrieval gate). Shows the reviewer exactly which lines triggered the retrieval decision. No additional dependencies.
- **Single-shot classification** — multi-turn dialogue adds latency, requires session state, and obscures the classification logic. Single-turn forces the agent to be explicit about missing information, which produces better escalation summaries than open-ended exchanges.
- **Human-in-the-loop on both AUTO_FIX and ESCALATE** — AUTO_FIX is obvious (don't silently unlock accounts). ESCALATE also gets a gate because opening a ticket routes to an on-call queue, starts an SLA clock, and notifies a technician. Both are consequential.

</details>

<details>
<summary><strong>Extending with MCP</strong></summary>

The tools here are called via Anthropic's native tool-use API (`tools=` in `messages.create`). MCP (Model Context Protocol) is the natural next step:

- **Service discovery** — agent discovers available tools (AD, Intune, ServiceNow connectors) at runtime via the MCP server manifest, without hardcoding schemas in the agent.
- **Credential isolation** — each connector runs in its own MCP server with scoped service-account credentials, keeping secrets out of the agent process.
- **Reuse across agents** — the same MCP connector for ServiceNow can be shared by this triage agent, a change-management agent, and an on-call bot without duplicating integration code.
- **Live KB sync** — an MCP resource server can expose the KB article directory, letting the agent pull the latest doc content at query time rather than from a static embedded index.

</details>

<details>
<summary><strong>Evaluation metrics for production RAG</strong></summary>

- **MTTR per path** — the primary business metric. Baseline against queue-mediated L1 (4–8 h target). Track separately for SELF_SERVE, AUTO_FIX, and ESCALATE so regressions are path-specific.
- **Retrieval accuracy@1** — fraction of queries where the top-ranked KB article is the correct one. Baseline requires a labelled query→article mapping.
- **Path accuracy** — fraction of queries classified into the correct path. Requires a held-out test set with ground-truth labels.
- **Escalation accuracy** — fraction of escalated tickets that the receiving technician confirms were correctly escalated.
- **Tool parameter validity** — fraction of AUTO_FIX calls with only concrete parameter values (no unresolved `current.user` in production).
- **False AUTO_FIX rate** — fraction of AUTO_FIX executions that fail or require a follow-up ticket.

</details>
