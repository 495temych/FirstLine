# Process

```bash
uv sync
uv run pre-commit install
npm install
cp .env.example .env
npm run dev
```

Put your key in `.env` as `ANTHROPIC_API_KEY`. `MODEL_NAME` is optional. `npm run dev` starts the backend on port 8000 and the dashboard on http://localhost:5173. The first ticket downloads `all-MiniLM-L6-v2` (~90 MB). The dashboard needs Node 26 or at least 22.22, as in `.nvmrc`.

`uv run poe check` runs every check, with no API key:

- ruff (format and lint)
- pyright
- pytest with 80% coverage of `agent/`, `backend/` and `evals/`
- the retrieval score, which runs the local embedding model and no chat model
- Prettier, ESLint, `tsc` and vitest with 80% coverage of `dashboard/`
- Playwright, against the real API and graph with a stub model, on ports 8010 and 5183

The store's tests start a throwaway Postgres 17 in Docker, so Docker must be running. They never touch Supabase.

The pre-commit hook and GitHub Actions run the same command.

Other commands:

- `npm run format` formats the Python and TypeScript.
- `uv run -m evals` evaluates the rules set, with 25 model calls, and scores the two yardsticks beside it. `--set dev` (129 calls) and `--set unseen_dev` (52) run the imported practice sets, and the three cost about CHF 1 together. `--tiny` makes 5 calls on the rules set, and `--sample` takes 3 tickets per family of `dev` (36) or `unseen_dev` (6). The held-out sets (`rules_held_out`, `held_out`, `unseen_held_out`) run once, at sprint review.
- Every run prints its estimated cost first and stops above CHF 1 unless `--max-chf` allows more. It also refuses to repeat a saved run with the same model, instructions, tools and knowledge base unless `--again` is passed.
- `--model` picks any model in `agent/models.py`, such as `uv run -m evals --set dev --model gpt-6-luna`. `uv run -m backend.benchmark` ranks every model's newest full run by net saving per ticket, with the Pareto front, as the Models view does. It makes no model calls.
- `uv run -m evals --rescore` marks the newest full run of each set against the current labels, with no model calls. Name runs to re-score particular ones, such as `--rescore 20261107T195842-dev`.
- `uv run -m evals.langfuse_upload` copies the practice sets to Langfuse as datasets, the newest full run of each as an experiment, and `logs.csv` as traces. It makes no model calls, skips what's already there, and never sends a held-out ticket. New runs are traced as they happen when the Langfuse keys are in `.env`, and `LANGFUSE_TRACING=false` turns that off.
- `uv run -m agent.index` rebuilds the knowledge base index in Qdrant Cloud. Run it after any change in `data/kb/`, because search refuses a stale index. It's free: embeddings are made on this machine.
- The Supabase schema lives in `supabase/migrations/`, one timestamped SQL file per change, never edited after it's applied. A change is a new file. `uv run -m backend.migrate` applies the files not yet applied, each in its own transaction, and records them in `schema_migrations`. `--record FILE` marks a file applied without running it, as was done once for the first, which was applied by hand.
- `uv run -m evals.label_tickets` gives every imported ticket its named cause again, from `data/evals/causes.json`.
- `uv run -m evals --retrieval` scores retrieval on the development sets, with no model calls. `--split` picks another set, and `--save` keeps the result for the Retrieval view.
- `uv run -m evals.import_tickets` imports the tickets again, as `data/tickets/SOURCE.md` explains.
- The Queue tab loads 8 development tickets at a time and triages them with real model calls, about CHF 0.03 a batch. The board is saved in Supabase, so restarting `npm run dev` brings it back and finishes what was left. Without `SUPABASE_DB_URL` it lives in memory, and a restart clears it.
- `uv run -m backend.stats` prints the usage statistics.
- `uv run uvicorn backend.main:app` runs the backend alone, with its API at http://127.0.0.1:8000/docs.

## Sprints

We work in three sprints, one per phase of `docs/FRAMEWORK.md`, and `docs/ROADMAP.md` holds them, with success criteria for the current one. Each commit ships one focused MVP, fully working and tested. When a sprint ends, we run the held-out set, review the work, and plan the next sprint by rewriting the roadmap.

## Planning

When asked to plan, as in "Please plan sprint 2", rewrite `docs/ROADMAP.md` with the sprint's commits and, for each part of the tech stack, checkbox success criteria you can verify yourself. Then stop for review.

## Implementing

When asked to implement, as in "Please implement commit 3", build that one commit:

1. Build it, with tests.
2. Check every success criterion for that commit and fix whatever fails.
3. Tick off its criteria and update `docs/STATUS.md`.
4. Commit, show the running result, and stop for review.

## Docs

The docs disclose progressively: `AGENTS.md` is the map, each doc opens with what it's for and where its details live, and the details come after.

- **One home per fact.** A rule, number or decision is written once, in the doc it belongs to. Others link to it instead of repeating it.
- **Principles above rules above code.** A principle doc (`docs/BUDGET.md`, `docs/SWISS.md`) says why, `docs/PROCESS.md` and `docs/TECH_STACK.md` say what we do here, and the code is the final word.
- **Change it in its home.** When a fact changes, change the one place it lives, and check that nothing else restates it.

## Rules

- Tests never call a model. Use a stub. `conftest.py` makes an unstubbed model raise, and the browser tests use `e2e/server.py`.
- Never lower a threshold, turn off a rule or exclude a file to get a green run. Fix the code, or stop and ask.
- Never use `git commit --no-verify`.
- Never push without asking.
- Ask before anything irreversible.
- Keep `docs/STATUS.md` up to date.
- Live runs cost money. Follow "Spending" below.
- Never open the held-out set when changing the instructions, and never give the agent an answer file.
- Supabase, `logs.csv` and `checkpoints.sqlite` hold real usage data. Keep them out of tests: tests use memory or a throwaway Postgres.

## Spending

The owner pays for every model call, so we spend as little as gets a trustworthy number. The principles are in `docs/BUDGET.md`, and these are the rules for model runs. A full practice run of 206 tickets costs about CHF 1 today.

- **Ask before any run over CHF 1**, and say what it costs and why it's needed. Smaller runs still get a line saying what they cost.
- **Never re-run the model when only the labels change.** Use `--rescore`, which is free.
- **Practise on a sample**: `--tiny` on the rules set and `--sample` on `dev` and `unseen_dev`, 47 tickets for about CHF 0.25. Run a full set once per commit, to record its result.
- **Try new designs and models on the sample first.** Run them in full only if they clearly win on it.
- **Run the held-out sets once**, at sprint review.
- **Never run the same thing twice.** If the instructions, tools, knowledge base and model are unchanged, reuse the saved run. The runner refuses a repeat unless `--again` is passed.
- **Prefer the cheapest model that passes**, and justify any bigger one with numbers.

| Tool | What it saves | Built |
|---|---|---|
| `--rescore` | Marks saved decisions against new labels, with no model calls | Yes |
| `--sample` | Runs 3 tickets per family instead of the whole set | Yes |
| A spending cap | Estimates the cost first and stops above CHF 1 unless `--max-chf` allows more | Yes |
| A repeat guard | Refuses a run that's already saved, unless `--again` is passed | Yes |
| Batch API | Half price on every evaluation run | Not yet |
| Prompt caching | Roughly 30–50% off the input that repeats on every call, to confirm on one small run | Not yet |
