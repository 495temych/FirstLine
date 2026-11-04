# TriagePilot — L1 IT Support Agent

TriagePilot does the first pass on L1 IT support tickets for a Swiss IT service provider: it looks up the client's knowledge base, picks one path, and proposes the next step for a technician to confirm.

### Problem

Most L1 tickets aren't hard — they're just troubleshooting simple, repetitive tasks. For an office worker, though, it doesn't feel small — work stops until someone shows up to fix it.

- **The work is repetitive, not complex.** Routine issues (software installs, OS config, workplace setup) sit in a queue until a technician is free, identifies the pattern, looks up the procedure, and acts. The fix is rarely novel — the dispatch delay is the struggle.
- **In Swiss SMEs, dispatch means travel.** A single technician often supports multiple client locations, since a small office can't justify a full-time on-site IT presence. Travel time to and from site is frequently a larger cost than the fix itself.
- **Skilled IT hours are expensive and scarce in this region.** Time spent traveling and pattern-matching a known issue is time not spent on the complex work only that technician can do.

**TriagePilot targets exactly that slice: high-frequency, well-documented, low-novelty tickets — resolved remotely, before a trip is even needed.**

### Stakeholder Profiles Breakdown

| Stakeholder | Job-to-be-Done | Pain | Gain — Basic | Gain — Surprising | Key metric |
|---|---|---|---|---|---|
| **Employees** | Get back to work with minimal disruption | Long wait for trivial issues; repeating context to technicians | Faster resolution for well-documented issues | Explainable, grounded self-serve guides for basic IT issues; generating a service ticket based on their issue automatically | Mostly qualitative, but IT issues influence productivity|
| **L1 Technicians** (on-site dispatch, multi-client) | Triage & resolve routine tickets, escalate the rest with context | Repetitive pattern-matching across multiple unfamiliar client environments; unclear user requests | Fewer routine tickets to resolve manually or dispatch for | AUTO_FIX shifts burden from diagnosis to confirmation; escalation write-ups auto-generated | Time-to-first-action|
| **L2/L3 Specialists** (remote, outsourced offshore)| Resolve complex issues without re-diagnosing from scratch; keep documentation up-to-date | Escalations under-documented; no live L1 to call back and clarify across timezones; quality varies by which L1 technician handled it | Escalations arrive with diagnostic summary + retrieval trace | Consistent documentation regardless of which technician escalated | Mean-time-to-resolution |
| **CTO** (of the IT service provider) | Keep cost-per-ticket low, maintain SLA & audit compliance; price and justify contracts | Cost-per-ticket opaque; no per-category automation visibility; audit risk on unlogged fixes | Lower cost-per-ticket; automation-rate reporting by client account | Automation-rate data becomes a pricing/contract lever — accounts with low automation potential (highly custom environments) can be identified and priced or staffed differently  | Cost-per-ticket by category; SLA compliance rate |

### Economic potential:

**Assumption:** ~4 tickets/day/technician, ~2 h avg per ticket including travel to and from client site.

| Automation rate | Time recovered/day | Value/technician/year |
|---|---|---|
| 30% (conservative) | ~2.4 h | ~CHF 32k |
| 50% (target) | ~4.0 h | ~CHF 53k |
| 70% (optimistic) | ~5.6 h | ~CHF 74k |

*(CHF 60/h fully-loaded technician cost, 220 working days/year, 2h/ticket including travel, 4 tickets/day.)*

For SME customers specifically, remote resolution via SELF_SERVE/AUTO_FIX removes the travel leg entirely for automatable tickets — this is not just faster resolution, it's a dispatch trip that never has to happen. Not netted against this figure: knowledge-base curation/maintenance effort, LLM inference cost per ticket, and technician review overhead during AUTO_FIX confirmation.

### Data potential
Every completed triage run (one that reaches a final state; RAG-off runs, which have no decision path, are not logged) appends a row to `logs.csv` — query, retrieved units, decision path, diagnostic summary, tool called, operator confirmation, escalation queue/priority, response time — and the app's "Live session stats" panel turns that into a running summary (path distribution, automation rate, avg response time) shown alongside the golden-set eval (see [Evaluation](#evaluation)). Over time, the same log supports:
- Retrieval threshold tuning, per category
- Cost-per-resolution-path analysis (AUTO_FIX cost vs. ESCALATE technician-hour cost)
- A natural link to quantitative/pricing-style analysis of automation vs. human dispatch

---

## Architecture

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	retrieve(retrieve)
	triage(triage)
	no_tools(no_tools)
	confirm_fix(confirm_fix)
	confirm_ticket(confirm_ticket)
	self_serve_wait(self_serve_wait)
	execute_tool(execute_tool)
	draft_ticket(draft_ticket)
	create_ticket(create_ticket)
	log(log)
	__end__([<p>__end__</p>]):::last
	__start__ -.-> no_tools;
	__start__ -.-> retrieve;
	confirm_fix -.-> draft_ticket;
	confirm_fix -.-> execute_tool;
	confirm_ticket -.-> create_ticket;
	confirm_ticket -.-> log;
	create_ticket --> log;
	draft_ticket --> confirm_ticket;
	execute_tool --> log;
	retrieve --> triage;
	self_serve_wait -.-> draft_ticket;
	self_serve_wait -.-> log;
	triage -.-> confirm_fix;
	triage -.-> confirm_ticket;
	triage -.-> log;
	triage -.-> self_serve_wait;
	log --> __end__;
	no_tools --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

*Generated from the compiled graph (`build_graph(...).get_graph().draw_mermaid()`), so it cannot drift from the code. Dotted edges are conditional routers (`graph.py`: `route_start`, `route_after_triage`, `route_after_confirm_fix`, `route_after_confirm_ticket`, `route_after_self_serve`); `confirm_fix`, `confirm_ticket` and `self_serve_wait` are the human gates.*

| Path | When | Operator action required? |
|---|---|---|
| **SELF_SERVE** | Fix is documented, safe, and user-executable | No — steps returned directly; "didn't resolve it" button escalates (see below) |
| **AUTO_FIX** | Fix is documented, reversible, better run by the agent | Yes — Confirm runs the tool; Cancel pre-fills an escalation ticket instead of just dropping the issue (see below) |
| **ESCALATE** | Info missing, infra-/hardware-/IAM-side issue, or low confidence | Yes — Confirm or Cancel before ticket is created |
| **OUT_OF_SCOPE** | Not a workplace-technology request at all | No — declined immediately |

---

## How to run

```bash
uv sync
cp .env.example .env    # then add your ANTHROPIC_API_KEY
uv run streamlit run app/main.py
```

Checks, with no API key needed: `uv run poe check`.

## Documentation

- [What it must do](docs/SPEC.md)
- [Where it's heading](docs/ROADMAP.md)
- [What's built, and which rules code enforces](docs/STATUS.md)
- [Design decisions and known limitations](docs/DECISIONS.md)

## Results
