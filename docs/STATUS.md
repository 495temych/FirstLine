# Status

FirstLine triages one ticket at a time for CorpLabs AG in a React dashboard on a FastAPI backend, with Queue, Assistant, Scoreboard and Tickets tabs. Each ticket gets one model call, grounded in the best playbook and any matching policy. The model fills in a Pydantic decision through one forced tool call, writing its rationale first, then the cause, path, tool or queue. Code reads that decision and ends on one of four paths behind human confirmation gates. All 17 tools are simulated, and each has a risk tier and an owner. `docs/ROADMAP.md` says what comes next, around four promises: proven, safe, observable and shippable, and `docs/PROCESS.md` says how to run it.

The 745 closed incidents are imported to `data/tickets/` with fixed splits, and their answers are in `data/evals/incidents.json`. The knowledge base has 15 playbooks on one template, written only from the knowledge base split, plus the policies and queues. Retrieval matches sections: it hits 100% on the development set, 87% on the short rules-set requests, and wrongly matches a playbook on 4% of unseen-family tickets. The agent doesn't use the staff records yet.

All 745 imported tickets have a named cause, drafted by rules, and each cause has accepted paths, tools, queues and required checks. The labels are frozen. The owner settled the open label decisions and reviewed the two causes the agent disagreed with most: a scan backlog now escalates to `DESK-SUPPORT`, and an uninitialised TPM still does. The rest stay as drafted by rules. Held-out tickets stay out of the app: `/api/tickets` leaves them out, and `/api/evaluations` shows a held-out run's scores without its tickets.

The baseline is run and committed for the rules, development and unseen sets, with the two yardsticks beside each. The README's "Results" holds the numbers. In short, after the owner's review of two causes: path 80% on the rules set, 73% on development and 60% on unseen families, against 56%, 93% and 100% for the simple classifier. The agent doesn't yet beat both yardsticks. Three SEC-04 mistakes make up CHF 6,000 of the CHF 9,960 mistake bill on development, which is more than always escalating would cost. The run's retrieval score counts any matched policy on an unseen ticket as wrong, so it reads 63% there, while the retrieval score, which counts playbooks only, reads 96%.

Every Assistant and evaluation run is traced in Langfuse Cloud's EU region, with emails, employee ids and IP addresses masked. The three practice sets are Langfuse datasets, and the latest baseline runs are experiments scored by our own code, replayed from saved decisions with no model calls. The 27 runs in `logs.csv` are there too. Langfuse exports only its own spans, because the Anthropic SDK's own spans counted each call twice.

Knowledge base search runs on Qdrant Cloud: 99 sections in `kb_sections`, built from knowledge base `916db54c`. On all 206 practice tickets the results match the old NumPy search exactly, so the retrieval scores are unchanged: 100% hit rate on development and 4% false matches on unseen families. Past incidents and keyword search aren't in Qdrant yet.

The Queue works a batch end to end, in memory. "Load 8 tickets" takes development tickets from a simulated service desk, mixing kinds of request, and two workers triage them in priority order while the board updates every second. Each ticket opens with its decision, reasoning, knowledge used, proposed action and its Langfuse trace as a timeline of steps with time, tokens and cost. A technician approves, sends it to another team or rejects it with a reason; only then does the simulated action run, and the verdict goes to Langfuse as a score. The board counts review time and shows the net saving in CHF. A restart clears it, because Supabase isn't wired in yet. The agent still makes one call per ticket, with no investigation tools.

Supabase has the schema and nothing writes to it yet: five tables in `supabase/migrations/`, applied to the project and tested on a local Postgres 17. The database rejects an unknown path, an Assistant ticket in a batch, and a correction on a review that isn't "corrected". The publishable key reads no rows and can't insert. `logs.csv` and SQLite checkpoints are still what the app uses.

Spending is guarded in code. A run states its estimated cost first, stops above CHF 1 unless allowed more, and refuses to repeat a saved run. `--rescore` marks saved decisions against new labels with no model calls, and `--sample` runs 3 tickets per family. The Batch API and prompt caching aren't used yet.

## Who enforces each rule

From the rules in `docs/SPEC.md`. Later sprints close the gaps.

| Rule | Enforced by | Where |
|---|---|---|
| No fix runs without confirmation | Code | The model's decision is only read. `execute_tool` is reachable only through `confirm_fix`, and the API answers only the gate a run is waiting at |
| No ticket without confirmation | Code | `create_ticket` is reachable only through `confirm_ticket` |
| A declined fix gives a pre-filled ticket, with no model call | Code | `draft_ticket` |
| Failed self-serve goes to the same ticket confirmation | Code | `route_after_self_serve` |
| The agent never asks the user a question | Instructions only | `agent/prompt.md`, line 48 |
| Access requests are escalated, never out of scope | Instructions only | `agent/prompt.md`, line 21 |
| SEC-04: 2+ lockouts, in the records or the ticket, go to `SEC-INCIDENT` | Instructions only | Knowledge base and `agent/prompt.md`. Nothing in code knows a user's lockout count |
| Tool parameters are concrete values | Instructions, and code checks the tool and queue names | `agent/prompt.md`, line 52 |
| With retrieval off, no tools and no path | Code | `_call_model` binds the decision tool only with retrieval on, and `no_tools` ends the run |
| Every finished run is logged, and evaluation runs are not | Code, with one gap | The `log` node and `log_runs=False`. Retrieval-off runs are not logged either, which the rule doesn't say |
| No secrets or real client data in the repository | Partly | `.gitignore` covers `.env`. Nothing scans commits |
