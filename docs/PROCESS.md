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
- `uv run -m evals` evaluates the development set, with 25 model calls. `--tiny` makes 5, and `--set held_out` runs the held-out set.
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
- Live runs cost money. Use them only when a check needs them.
- Never open the held-out set when changing the instructions, and never give the agent an answer file.
- `logs.csv` and `checkpoints.sqlite` are real usage data. Keep them out of tests.
