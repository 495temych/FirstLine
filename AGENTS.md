# TriagePilot

## The context

TriagePilot is an L1 IT support triage agent for Sihlwerk IT AG, a fictional Swiss IT service provider. Its first client is the fictional Limmatica AG. It is built as a portfolio project for Swiss employers, the way a production team would build it. The owner reviews plans and builds, and you plan, build and check the work.

## Start here

IMPORTANT: before you plan, build or change anything, read each of these in full:

1. `docs/SPEC.md`: what the business needs
2. `docs/ROADMAP.md`: where the product is heading
3. `docs/STATUS.md`: what's built, how to run it, and which rules code enforces
4. `docs/DECISIONS.md`: design decisions, their trade-offs and the known limitations

Finished briefs and their plans stay in `docs/` as a record: `docs/FOUNDATION.md` and `docs/PLAN_FOUNDATION.md`.

## Tech stack

- Python 3.12 with uv, all in `pyproject.toml`
- LangGraph with `langchain-anthropic`. The model is `claude-haiku-4-5-20251001`, or `MODEL_NAME` if set
- `sentence-transformers` for local embeddings
- Streamlit for the app
- SQLite for checkpoints, and CSV for the usage log

## Folders

- `agent/`: the graph, tools, tool schemas, retrieval and instructions. `run_triage` is the entry point, and `config.py` holds paths and settings
- `app/`: the Streamlit app and usage statistics
- `evals/`: the evaluation runner
- `data/kb/`: the knowledge base
- `data/evals/`: the evaluation set
- `docs/`: project documents
- `briefs/`: briefs not yet started

Each package keeps its tests in its own `tests/` folder.

## Code standards

- Keep it simple, and build only what the documents ask for.
- Nodes return partial state and never mutate `state`. Routers are pure functions.
- Side effects never live in an `interrupt()` node, because it re-runs from its first line on resume.
- Paths and settings go in `agent/config.py`.
- Add no `# noqa` or `# type: ignore`.

## Process

Briefs start in `briefs/`, written in the customer's voice, and move to `docs/` when their work begins.

- **"Please plan X"** writes `docs/PLAN_X.md`, with phases and checkbox success criteria you can verify yourself. Then stop for review.
- **"Please implement the plan for X"** builds the phases in order. For each phase: build it with tests, check every criterion, tick it off, update `docs/STATUS.md`, and commit.

`uv run poe check` runs ruff, pyright and pytest with 80% coverage. The pre-commit hook and GitHub Actions run the same command.

## Rules

- Tests never call a model. Use a stub. `conftest.py` makes an unstubbed model raise.
- Never lower a threshold, turn off a rule or exclude a file to get a green run. Fix the code, or stop and ask.
- Never use `git commit --no-verify`.
- Never push without asking.
- Ask before anything irreversible.
- Keep `docs/STATUS.md` up to date.
- Live runs cost money, and opening the app runs the evaluation. Use them only when a check needs them.
- `logs.csv` and `checkpoints.sqlite` are real usage data. Keep them out of tests.

## This machine

The repository is in an iCloud-synced folder.

- The virtual environment must stay in `.venv.nosync`, with `.venv` a link to it. iCloud skips `*.nosync`. Never rebuild it as a plain `.venv`.
- If anything hangs, check for offloaded files first: `find . -flags +dataless | wc -l`.
