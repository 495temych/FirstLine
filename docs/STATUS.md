# Status

FirstLine triages one ticket at a time for CorpLabs AG in a React dashboard on a FastAPI backend, with Assistant, Scoreboard and Tickets tabs. Each ticket gets one model call, grounded in the best playbook and any matching policy. The model fills in a Pydantic decision through one forced tool call, writing its rationale first, then the cause, path, tool or queue. Code reads that decision and ends on one of four paths behind human confirmation gates. All 17 tools are simulated, and each has a risk tier and an owner. `docs/ROADMAP.md` says what comes next, and `docs/PROCESS.md` says how to run it.

The 745 closed incidents are imported to `data/tickets/` with fixed splits, and their answers are in `data/evals/incidents.json`. The knowledge base has 15 playbooks on one template, written only from the knowledge base split, plus the policies and queues. Retrieval matches sections: it hits 100% on the development set, 87% on the short rules-set requests, and wrongly matches a playbook on 4% of unseen-family tickets. The agent doesn't use the staff records yet.

All 745 imported tickets have a named cause, drafted by rules, and each cause has accepted paths, tools, queues and required checks. The owner has settled the open label decisions, but the full cause table in `briefs/LABEL_REVIEW.md` is still waiting for their read. Held-out tickets stay out of the app: `/api/tickets` leaves them out, and `/api/evaluations` shows a held-out run's scores without its tickets.

The baseline is run and committed for the rules, development and unseen sets, with the two yardsticks beside each. The README's "Results" holds the numbers. In short: path 80% on the rules set, 70% on development and 60% on unseen families, against 36%, 92% and 92% for the simple classifier. The agent doesn't yet beat both yardsticks, and three SEC-04 mistakes make up CHF 6,000 of the CHF 10,020 mistake bill on development. The run's retrieval score counts any matched policy on an unseen ticket as wrong, so it reads 63% there, while the retrieval score, which counts playbooks only, reads 96%.

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
