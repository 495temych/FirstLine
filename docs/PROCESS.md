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

The pre-commit hook and GitHub Actions run the same command.

Other commands:

- `npm run format` formats the Python and TypeScript.
- `uv run -m evals` evaluates the rules set, with 25 model calls, and scores the two yardsticks beside it. `--set dev` (129 calls) and `--set unseen_dev` (52) run the imported practice sets, and the three cost about CHF 1 together. `--tiny` makes 5 calls on the rules set, and `--sample` takes 3 tickets per family of `dev` (36) or `unseen_dev` (6). The held-out sets (`rules_held_out`, `held_out`, `unseen_held_out`) run once, at sprint review.
- Every run prints its estimated cost first and stops above CHF 1 unless `--max-chf` allows more. It also refuses to repeat a saved run with the same model, instructions, tools and knowledge base unless `--again` is passed.
- `uv run -m evals --rescore` marks the newest full run of each set against the current labels, with no model calls. Name runs to re-score particular ones, such as `--rescore 20261107T195842-dev`.
- `uv run -m evals.langfuse_upload` copies the practice sets to Langfuse as datasets, the newest full run of each as an experiment, and `logs.csv` as traces. It makes no model calls, skips what's already there, and never sends a held-out ticket. New runs are traced as they happen when the Langfuse keys are in `.env`, and `LANGFUSE_TRACING=false` turns that off.
- `uv run -m evals.label_tickets` gives every imported ticket its named cause again, from `data/evals/causes.json`.
- `uv run -m evals --retrieval` scores retrieval on the development sets, with no model calls. `--split` picks another set, and `--save` keeps the result for the Scoreboard.
- `uv run -m evals.import_tickets` imports the tickets again, as `data/tickets/SOURCE.md` explains.
- `uv run -m backend.stats` prints the usage statistics.
- `uv run uvicorn backend.main:app` runs the backend alone, with its API at http://127.0.0.1:8000/docs.

## Sprints

We work in three sprints, and `docs/ROADMAP.md` holds them, with success criteria for the current one. Each commit ships one focused MVP, fully working and tested. When a sprint ends, we run the held-out set, review the work, and plan the next sprint by rewriting the roadmap.

## Planning

When asked to plan, as in "Please plan sprint 2", rewrite `docs/ROADMAP.md` with the sprint's commits and, for each part of the tech stack, checkbox success criteria you can verify yourself. Then stop for review.

## Implementing

When asked to implement, as in "Please implement commit 3", build that one commit:

1. Build it, with tests.
2. Check every success criterion for that commit and fix whatever fails.
3. Tick off its criteria and update `docs/STATUS.md`.
4. Commit, show the running result, and stop for review.

## Rules

- Tests never call a model. Use a stub. `conftest.py` makes an unstubbed model raise, and the browser tests use `e2e/server.py`.
- Never lower a threshold, turn off a rule or exclude a file to get a green run. Fix the code, or stop and ask.
- Never use `git commit --no-verify`.
- Never push without asking.
- Ask before anything irreversible.
- Keep `docs/STATUS.md` up to date.
- Live runs cost money. Follow "Spending" below.
- Never open the held-out set when changing the instructions, and never give the agent an answer file.
- `logs.csv` and `checkpoints.sqlite` are real usage data. Keep them out of tests.

## Spending

The owner pays for every model call, so we spend as little as gets a trustworthy number. A full practice run of 206 tickets costs about CHF 1 today.

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
