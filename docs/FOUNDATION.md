# The foundation

From our engineering lead.

## Where we're heading

TriagePilot works, and the pilot in `docs/SPEC.md` describes what it does. Next we want evaluations we can trust, a backend that enforces our rules, an agent that can investigate before it decides, and batch triage. `docs/ROADMAP.md` sets out the order, and each step comes as its own brief. Before any of them, the project needs the base a production team would expect: documents a coding agent can work from, one command that checks everything, and a layout with room to grow.

**Nothing the user or the technician sees changes in this brief.** Same paths, same tools, same instructions, same model, same screens.

## What we want

1. **Documents for the coding agent.**
   - `AGENTS.md` at the root, and a `CLAUDE.md` that holds only `@AGENTS.md`. It gives the context, a "Start here" list of the documents below to read in full before any work, the tech choices, the code standards, the plan-then-implement process, the folders, and the rules. Keep it short enough to read in full.
   - In `docs/`:
     - `SPEC.md`: moved from `briefs/SPEC.md`
     - `ROADMAP.md`: moved from `briefs/ROADMAP.md`
     - `STATUS.md`: what is built and how to run it
     - `DECISIONS.md`: one short entry for each design decision already made, each with its reason and its trade-off, taken from the README. These are LangGraph, single-shot triage, local embeddings, mixed-granularity retrieval, the 0.35 threshold with top 2, no tools with retrieval off, the SQLite checkpointer, and logging from the final state. The README's known limitations go here too.
   - In `STATUS.md`, list each rule in `docs/SPEC.md` and say whether the code enforces it or only the agent's instructions do. Later briefs close those gaps.
2. **The plan-then-implement process.**
   - "Please plan X" writes `docs/PLAN_X.md`, with phases and checkbox success criteria the agent can verify itself, and stops.
   - "Please implement the plan for X" builds the phases in order. For each phase: build it with tests, check every criterion, tick it off, update `STATUS.md`, and commit.
   - Each later brief starts in `briefs/` and is moved to `docs/` when its work begins.
   - This brief is the one exception. `retrieval.py` indexes every `.md` file in `docs/`, so nothing else can go there until the knowledge base has moved. Moving it is the first phase, and this brief and its plan stay in `briefs/` until that phase is done.
3. **Data out of the code.**
   - The knowledge base moves from `docs/` to `data/kb/`, unchanged.
   - `knowledge-base/`, an untracked duplicate of the knowledge base, is deleted.
   - The golden set moves from `eval.py` to `data/evals/golden.json`, with the same 10 tickets and labels.
4. **A package layout.**
   - `agent/`: graph, tools, tool schemas, retrieval and the instructions, with `run_triage` as the entry point
   - `app/`: the Streamlit app and the usage statistics
   - `evals/`: the evaluation runner
   - each with its own `tests/`

## Our engineering team's choices

- **uv**: `pyproject.toml` and `uv.lock` replace `requirements.txt`. The test and check tools go in a dev group. Python 3.12. The virtual environment stays in `.venv.nosync` with a `.venv` link to it, because the repository sits in an iCloud-synced folder and iCloud skips `*.nosync`.
- **Checks**, run by `uv run poe check` (poethepoet):
  - ruff format and lint, with the same rule set as our reference project (`E F W I B SIM UP PL S PT C90`, complexity at most 10)
  - pyright
  - pytest with coverage of `agent/` and `evals/` at 80% or more
  - Streamlit's `AppTest` smoke tests for `app/`
- **A pre-commit hook** (the `pre-commit` framework) runs the same checks on every commit. Never skip it with `--no-verify`.
- **GitHub Actions** runs `uv run poe check` on every push and pull request, with no API key.
- **Never lower a threshold**, turn off a rule or exclude a file to get a green run. Fix the code, or stop and ask.
- **The model**: `claude-haiku-4-5-20251001` by default, or the model in `MODEL_NAME` if set. Add a `.env.example` with `ANTHROPIC_API_KEY` and `MODEL_NAME` and no values.
- **Tests never call a model.** They use a stub, as `tests/test_graph.py` does today.
- **README**: this is what employers read first. Keep the problem, the architecture diagram, how to run, and links to `docs/`. Move the deep detail to `docs/DECISIONS.md`. Keep a "Results" heading, empty until the evaluations brief fills it.
- **`.gitignore`**: add `.env.*` except `.env.example`, `.ruff_cache/`, `.coverage`, `htmlcov/`, `.streamlit/secrets.toml`, `.agents/`, `.claude/skills/` and `.claude/settings.local.json`.
- **The Streamlit skill** stays out of git. `.agents/skills/` and `.claude/skills/` hold symlinks into the installed Streamlit package, which dangle on a fresh clone. `.claude/settings.local.json` is personal.

## What stays the same

- The agent's instructions, word for word. They move to `agent/` as they are.
- The graph, its nodes, routers, interrupts and retry policy.
- The format of `logs.csv` and `checkpoints.sqlite`. An existing log and a session paused mid-run both still work after the move.
- The 18 existing tests, moved next to the code they test.

## What done looks like

- `uv sync` then `uv run poe check` is green, with `.env` moved out of the way.
- After `uv sync`, `.venv` is still a link to `.venv.nosync`.
- `docs/` holds only project documents, and `knowledge-base/` is gone.
- The pre-commit hook blocks a commit that fails a check.
- The GitHub Actions workflow is in place, and the same checks pass in a fresh clone with no `.env`.
- `uv run streamlit run app/main.py` starts the app. One ticket for each of the four paths behaves as it did before, and the stats panel still reads the existing `logs.csv`.
- `uv run -m evals` gives the same path and retrieval results as `python eval.py` did before the move, within the known run-to-run variation on "My VPN keeps disconnecting".
- `docs/STATUS.md` is up to date, and `AGENTS.md` lists every document in `docs/`.
