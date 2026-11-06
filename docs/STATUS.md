# Status

TriagePilot triages one ticket at a time in a React dashboard on a FastAPI backend, with a Scoreboard tab for saved evaluations and a read-only Tickets tab for the development tickets and their labels. Each ticket gets one model call, grounded in the top 2 knowledge base units, and ends on one of four paths behind human confirmation gates. All 10 remediation tools are simulated. `docs/ROADMAP.md` says what comes next, and `docs/PROCESS.md` says how to run it.

The EVALS code is built. The baseline is waiting for the label review, in the Tickets tab for the development set and `briefs/LABEL_REVIEW.md` for the held-out set. The held-out set stays out of the app.

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
| SEC-04: 2+ lockouts go to `SEC-INCIDENT` | Instructions only | Knowledge base and `agent/prompt.md`. Nothing in code knows a user's lockout count |
| Tool parameters are concrete values | Instructions only | `agent/prompt.md`, line 56 |
| With retrieval off, no tools and no path | Code | `_call_model` binds tools only with retrieval on, and `no_tools` ends the run |
| Every finished run is logged, and evaluation runs are not | Code, with one gap | The `log` node and `log_runs=False`. Retrieval-off runs are not logged either, which the rule doesn't say |
| No secrets or real client data in the repository | Partly | `.gitignore` covers `.env`. Nothing scans commits |
