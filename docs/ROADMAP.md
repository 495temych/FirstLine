# Roadmap

FirstLine is an L1 IT support agent for a Swiss IT service provider, built as a portfolio project for Zurich employers. UnderCover is the model for the engineering practice, not the product.

**The idea: the agent proposes, the system enforces, and a scoreboard proves it works.**

This file holds the current sprint in detail and only a rough list after it. Each commit ships one working MVP. When the sprint ends we review it, plan again and rewrite this file.

## Sprint 1: prove it, then enforce it

Today the agent has no trusted score, can't see a user's records, and only its instructions stop a routine unlock after repeat lockouts. By the end of this sprint we have a real baseline and code enforces SEC-04, on top of the API and React dashboard that have now replaced Streamlit.

| # | Commit | What you can see afterwards |
|---|---|---|
| 1 | **Baseline.** Finish the label review, then run and commit the evaluations | Real numbers in the README and on the Scoreboard |
| 2 | **Records reach the agent.** Triage takes a requester and gets their record | Pick a user, and the same ticket gets a different answer |
| 3 | **Lockout guard.** Code applies SEC-04 after the model decides | The model proposes an unlock, and code turns it into `SEC-INCIDENT` |
| 4 | **Thin API.** Done, built ahead of commits 1 to 3 | A full ticket, gates included, works from `/docs` |
| 5 | **React dashboard.** Done, with all three tabs. Streamlit is gone | Triage, Scoreboard and Tickets in the browser |

Commit 1 needs you first: the label review is yours. After it, `docs/EVALS.md`, `docs/PLAN_EVALS.md` and `briefs/LABEL_REVIEW.md` are deleted.

### Success criteria

The number after each one is the commit that meets it.

**Data (`data/`)**

- [ ] (1) Every label is reviewed, and no `review` flag is left in `data/evals/`.
- [ ] (2) Every ticket's requester exists in `data/records/users.json`, checked by the existing tests.

**Evaluations (`evals/`)**

- [ ] (1) Development set, held-out set and one stronger model are run and committed. This should cost under $1, going by the 5-ticket trial.
- [ ] (1) The README's "Results" section shows path accuracy, automation rate, mistake cost and cost per ticket.
- [ ] (2) The runner passes each ticket's requester, and the 5 `records` tickets in the development set beat the baseline.
- [ ] (3) The development set has no CHF 2,000 mistakes, and overall path accuracy is no worse than the baseline.

**Agent: LangGraph and Claude (`agent/`)**

- [ ] (2) `run_triage` takes a requester, and the model sees that user's record. With no requester it behaves as it does today.
- [ ] (2) The session that changes the instructions doesn't open the held-out set or `briefs/LABEL_REVIEW.md`.
- [ ] (3) A pure function in `agent/rules.py` overrides the decision when a user with 2+ lockouts gets `unlock_ad_account`, or any other non-escalated path on a ticket that retrieved `account-access`. The result is ESCALATE to `SEC-INCIDENT`.
- [ ] (3) A test with a stub model that proposes the unlock ends at `SEC-INCIDENT`, and the fix can't run.
- [ ] (3) A user with 2 lockouts and a printer ticket is not overridden.
- [ ] (3) `docs/STATUS.md` shows SEC-04 as enforced by code.

**Retrieval: sentence-transformers**

- [ ] (1, 3) No change this sprint: 17 units, and retrieval accuracy matches the baseline.

**API: FastAPI (`backend/`)**

- [x] (4) Three routes: start a triage, answer a gate, read one run, plus read-only routes for the dashboard's other data. The graph holds all the logic.
- [x] (4) Tests with a stub model cover all four paths, a confirmed fix, a declined fix and a failed self-serve.
- [x] (4) No route can run a fix or create a ticket without passing its gate.
- [x] (4) `uv run uvicorn backend.main:app` serves `/docs`, and starting the app makes no model calls.

**Storage: SQLite and CSV**

- [x] (4) A ticket paused at a gate survives an API restart and can be resumed.
- [x] (4) `logs.csv` keeps its format, and API runs are logged like app runs.

**Dashboard: React, Vite and TypeScript (`dashboard/`)**

- [x] (5) Triage shows ticket text, retrieved units, path, reasoning and the confirmation card. Scoreboard, Tickets and live statistics match what Streamlit showed.
- [x] (5) All four paths work through the API in the browser, including declining a fix.
- [x] (5) TypeScript is in strict mode with no `any`, and vitest covers the gate logic.
- [x] (5) It reads well at phone width, with one small set of colours and fonts in `docs/BRAND.md`.
- [ ] (2) A requester picker sits on the Triage tab.
- [ ] (3) The dashboard shows when a rule changed the agent's decision.

**Checks and CI**

- [ ] (all) `uv run poe check` passes on every commit, with the coverage threshold unchanged.
- [x] (4) `poe check` and its coverage include `backend/`.
- [x] (5) `poe check` also runs ESLint, `tsc`, vitest and Playwright, and GitHub Actions installs Node.

## Do we need something like UnderCover's `context/`?

Not now. It solves a problem we don't have. UnderCover's data governance team hands seven files to an agent behind an AWS Gateway, so the files need an MCP server of their own and a record of where each came from. We have one agent, one client and one process.

| UnderCover | FirstLine today | Verdict |
|---|---|---|
| `policy_wording.md`, `claims_manual.md` | `data/kb/` | Already have it |
| `claim_rules.yaml` | SEC-04 in the text of `company-profile.md` | Only the rule we enforce needs a value. It's a constant in `agent/rules.py` for now |
| `glossary.yaml`, `plans.yaml`, `reference_data.yaml` | Nothing like them is needed | Skip |
| `data_dictionary.yaml` | Fields in `users.json` explain themselves | Skip for now. Its `personal` flag is useful once we take personal data out of logs |
| Source, owner and review date on each file | KB articles already have an owner and a last-updated date | Keep doing this |
| MCP server and Gateway | One process | Skip |
| Agent memory per customer | `recent_tickets` in the records | Skip |

Look at this again when a second client arrives. Each client will need its own knowledge base and rule values, and one small rules file per client would be the first thing to add.

## How to make this a solid project

Employers will spend a few minutes on this, so each point should be something they can see.

1. **Let numbers make the claim.** Replace the README's assumed 50% automation with the measured rate, next to accuracy, mistake cost and cost per ticket.
2. **Close rule gaps by how much harm they do.** `docs/STATUS.md` lists four rules that only the instructions enforce, and SEC-04 is the costliest. Each safety rule needs code, plus a test where a stub model tries to break it.
3. **Treat evaluations as regression tests.** Run the development set after every agent change and commit the result. Run the held-out set only at sprint review, so it stays a fair check.
4. **Fail towards a technician.** A timeout, API error or unreadable answer should become an escalation, never a crash or a silent fix.
5. **Make every decision traceable.** Limmatica is a financial services firm, so someone will ask who approved what and why. Each ticket should show what was retrieved, proposed, overridden and confirmed.
6. **Take Swiss data protection seriously.** `logs.csv` stores raw ticket text, and that text goes to a model hosted abroad. Say so plainly, then keep personal data out of logs.
7. **Keep one of everything.** One front end, one decision format, one place for rules. Delete what gets replaced.
8. **Make it easy to see.** Few people will clone it. A hosted demo and a two-minute walkthrough do more than another feature, and the demo needs a budget cap first.
9. **Stay honest.** Label assumptions, publish limitations and show the mistakes on the Scoreboard. It's rare in portfolio projects, and it earns trust.

## After this sprint

These are candidates, not commitments. Each sprint picks from them when we plan it.

- **Audit:** SQLite tickets and an audit trail behind the API.
- **Harden:** a dashboard build served by the backend, traces, a budget cap, prompt-injection tests and personal data out of logs.
- **Demo:** hosted, with a walkthrough.
- **Inbox:** a batch of tickets with an agent loop, read-only tools, a dispatcher with no model and a review queue. It shares Triage's decision format, rules and scoring.
- **Swiss:** German tickets, a second client and costs in CHF.

The demo all this builds towards: load 25 tickets, some in German, one with a prompt injection. Agents work them at once. Code blocks a repeat lockout, even if the model proposes an unlock. A technician approves the rest. The Scoreboard shows accuracy, cost per ticket and CHF saved.

## Not for now

Sign-in, cloud databases, AWS, agents that rewrite their own prompts, real integrations, a context layer.
