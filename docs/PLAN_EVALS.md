# Plan: evaluations

Builds `docs/EVALS.md`. The plan stops at the label review, because a baseline on unreviewed labels would mean nothing.

## Phase 1: data

Records in `data/records/users.json`. Tickets and answers in `data/evals/`. `golden.json` goes.

- [x] 20 users, 25 + 25 tickets, every ticket has an answer and a known requester.
- [x] Every expected unit, tool and queue exists, checked by a test.

## Phase 2: measuring

`run_triage` returns tokens and time. `evals/scoring.py` scores tickets, and `evals/runner.py` runs, saves and reports.

- [x] Tests cover each mistake cost, a failed ticket, an unknown price and the version hash.
- [x] No module in `agent/` or `app/` names an answer file, checked by a test.

## Phase 3: Scoreboard

Triage and Scoreboard tabs. The evaluation panel goes, so opening the app makes no model calls.

- [x] Smoke tests cover both tabs with and without saved runs.
- [x] `uv run -m evals --tiny` saves a result the Scoreboard shows in the browser.
- [x] `uv run poe check` passes.

## Phase 4: baseline (after the label review)

- [ ] A person has reviewed the labels.
- [ ] Development set, held-out set and one stronger model are run and committed.
- [ ] The README's "Results" section is filled in.
