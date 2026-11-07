# Status

FirstLine triages one ticket at a time for CorpLabs AG in a React dashboard on a FastAPI backend, with a Scoreboard tab for saved evaluations and a read-only Tickets tab for the development tickets and their labels. Each ticket gets one model call, grounded in the best playbook and any matching policy, and ends on one of four paths behind human confirmation gates. All 17 tools are simulated, and each has a risk tier and an owner. `docs/ROADMAP.md` says what comes next, and `docs/PROCESS.md` says how to run it.

The 745 closed incidents are imported to `data/tickets/` with fixed splits, and their answers are in `data/evals/incidents.json`. The knowledge base has 15 playbooks on one template, written only from the knowledge base split, plus the policies and queues. Retrieval matches sections, and the Scoreboard shows its score for free. The hit rate rose from 94% to 100% on the development set, and false matches on unseen families fell from 96% to 4%. These tickets are templated, so short requests are the harder test: the rules set hits 87%. The agent doesn't use the new tickets or staff records yet.

The EVALS code is built, and it runs the 50 hand-written tickets, now called the rules set. All 745 imported tickets have a named cause, drafted by rules, and each cause has accepted paths, tools, queues and required checks. The Tickets tab shows the rules set and 181 imported tickets, with filters. The owner has settled the open label decisions. The full cause table is still in `briefs/LABEL_REVIEW.md`, for the owner to confirm. Held-out tickets stay out of the app.

## Who enforces each rule

From the rules in `docs/SPEC.md`. Later sprints close the gaps.

| Rule | Enforced by | Where |
|---|---|---|
| No fix runs without confirmation | Code | The model's tool call is only parsed. `execute_tool` is reachable only through `confirm_fix`, and the API answers only the gate a run is waiting at |
| No ticket without confirmation | Code | `create_ticket` is reachable only through `confirm_ticket` |
| A declined fix gives a pre-filled ticket, with no model call | Code | `draft_ticket` |
| Failed self-serve goes to the same ticket confirmation | Code | `route_after_self_serve` |
| The agent never asks the user a question | Instructions only | `agent/prompt.md`, line 52 |
| Access requests are escalated, never out of scope | Instructions only | `agent/prompt.md`, line 25 |
| SEC-04: 2+ lockouts, in the records or the ticket, go to `SEC-INCIDENT` | Instructions only | Knowledge base and `agent/prompt.md`. Nothing in code knows a user's lockout count |
| Tool parameters are concrete values | Instructions only | `agent/prompt.md`, line 56 |
| With retrieval off, no tools and no path | Code | `_call_model` binds tools only with retrieval on, and `no_tools` ends the run |
| Every finished run is logged, and evaluation runs are not | Code, with one gap | The `log` node and `log_runs=False`. Retrieval-off runs are not logged either, which the rule doesn't say |
| No secrets or real client data in the repository | Partly | `.gitignore` covers `.env`. Nothing scans commits |
