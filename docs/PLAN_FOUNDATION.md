# Plan: the foundation

Builds what `FOUNDATION.md` asks for: a package layout, one check command, a pre-commit hook, CI and short documents. Nothing the user or the technician sees changes. Three phases, each building on the last.

## For your review

1. **Two captions in the app change.** `app.py:353` and `app.py:406` name `python analyze_logs.py` and `python eval.py`. Those commands stop working, so the captions change to `uv run -m app.stats` and `uv run -m evals`. They are the only on-screen changes.
2. **Two ruff rules are relaxed in tests.** `S101` and `PLR2004` are ignored under `*/tests/*`, as in UnderCover. Everything else stays on, with no new `# noqa` or `# type: ignore`.
3. **The project is installed as a package**, using `hatchling`. Streamlit only puts `app/` on the path, so `app/main.py` couldn't import `agent` otherwise. I tried this on a throwaway project and it worked.
4. **`logs.csv` and `checkpoints.sqlite` stay at the repo root.** A small `agent/config.py` holds the paths, so the move can't silently start an empty log inside `agent/`.
5. **Live checks use about 34 Haiku calls.** Eval before and after is 20, opening the app is 10, and four UI tickets are 4. Tests make none.
6. **Work stays on `langgraph-port`**, and nothing is pushed until you ask. CI therefore first runs when you approve a push.

## Target layout

```
AGENTS.md  CLAUDE.md  README.md  pyproject.toml  uv.lock  conftest.py
.env.example  .pre-commit-config.yaml  .github/workflows/check.yml
logs.csv  checkpoints.sqlite          (ignored, at the root)
agent/    __init__.py  config.py  graph.py  tools.py  tool_schemas.py
          retrieval.py  triage.py  prompt.md  tests/
app/      __init__.py  main.py  stats.py  tests/
evals/    __init__.py  __main__.py  runner.py  tests/
data/     kb/  evals/golden.json
docs/     SPEC.md  ROADMAP.md  STATUS.md  DECISIONS.md
          FOUNDATION.md  PLAN_FOUNDATION.md
```

## Phase 1: move the knowledge base and switch to uv

The knowledge base goes first because `retrieval.py:44` indexes every `.md` file in `docs/`. Nothing else can go there until it has moved.

Before any change, save the output of `.venv/bin/python eval.py` to `briefs/baseline-eval.txt`, and the installed package versions beside it. Then:

- Move the knowledge base to `data/kb/` and delete `knowledge-base/`.
- Move `SPEC.md`, `ROADMAP.md`, `FOUNDATION.md` and this plan to `docs/`, and start `docs/STATUS.md`.
- Add `pyproject.toml`, `uv.lock` and `.env.example`, update `.gitignore`, and remove `requirements.txt` and `pytest.ini`.
- Keep dependencies at today's versions, so this brief doesn't upgrade LangGraph by accident.

**Success criteria**

- [x] `briefs/baseline-eval.txt` shows 10 queries.
- [x] `diff -rq docs knowledge-base` shows no difference before `knowledge-base/` is deleted.
- [x] `data/kb/` holds the 12 files as pure renames, and a new test asserts 17 units with none from project documents.
- [x] After `uv sync`, `.venv` is still a link to `.venv.nosync`, and direct dependencies match the saved versions.
- [x] `uv run pytest -q` passes.

## Phase 2: packages and checks

Moves the code to its final place, then adds the checks and fixes what they find.

- `agent/config.py` holds the paths and `model_name()`, and loads `.env`. A blank `MODEL_NAME` counts as unset, because `.env.example` is copied with blanks.
- `GOLDEN_SET` becomes `data/evals/golden.json`, and the runner turns its lists back into sets.
- The 18 tests move next to their code.
- `poe check` runs ruff format and lint, pyright and pytest with 80% coverage. The pre-commit hook and GitHub Actions run the same command.
- A root `conftest.py` makes the model and the encoder raise unless a test stubs them.
- New tests cover retrieval with a stub encoder, the tools, the config and the eval runner. `AppTest` smoke tests cover each of the four paths with a stub model, a temporary log and a temporary checkpoint file.

Today's check findings are small and mechanical: 87 long lines, 9 files to format, 25 pyright errors (mostly test typing) and a few lint fixes. Nothing is over complexity 10. Long lines are mostly strings the model or the user reads, so they must be split without changing their text. If installing `torch` makes CI too slow, CI uses the CPU build.

**Success criteria**

- [x] `uv run poe check` passes with coverage at 80% or more, and `grep -rn "noqa\|type: ignore" agent app evals conftest.py` finds nothing.
- [x] `agent/prompt.md`, the JSON of `TOOLS` and the graph's Mermaid output match commit `ef89ead`, checked by a short script.
- [x] `golden.json` holds the same 10 tickets and labels as `eval.py` at `ef89ead`.
- [x] Tests show the default model with `MODEL_NAME` unset or blank, and the override when set.
- [x] Running the tests leaves `logs.csv` and `checkpoints.sqlite` unchanged.
- [x] A staged file with an unused import makes `git commit` fail, and a clean commit passes with no `--no-verify`.
- [x] `uv run poe check` passes in a fresh clone in a temporary folder, with no `.env`, and `.github/workflows/check.yml` runs that same command.

## Phase 3: documents and the before-and-after check

Writes what the coding agent and employers read, then compares the result with Phase 1.

- `AGENTS.md`, with `CLAUDE.md` holding only `@AGENTS.md`. It includes the `.venv.nosync` rule, the iCloud `dataless` check for hangs, and `uv run pre-commit install` for a new clone.
- `docs/STATUS.md`, with how to run the app, the demo queries, and the spec's rules marked as enforced by code or by the instructions only.
- `docs/DECISIONS.md`, with the 8 decisions, how the evaluation works, and the known limitations.
- `README.md`: the problem with its stakeholder and economics sections, the architecture diagram, how to run, links to `docs/`, and an empty "Results" heading.

Back up `logs.csv` and `checkpoints.sqlite` before the live UI run, and restore them after it.

**Success criteria**

- [ ] `AGENTS.md` names every file in `docs/`.
- [ ] `docs/STATUS.md` covers all 11 rules, and `docs/DECISIONS.md` has all 8 decisions and all 11 limitations.
- [ ] The README has an empty "Results" heading, its links resolve, and no document outside `FOUNDATION.md` and this plan still says `python eval.py`, `pip install` or `streamlit run app.py`.
- [ ] `uv run -m evals` matches `briefs/baseline-eval.txt`, allowing for the known variation on "My VPN keeps disconnecting".
- [ ] In the browser, one ticket for each path behaves as before, a declined fix gives a pre-filled ticket, and the stats panel shows the existing runs from the root `logs.csv`.
- [ ] On a copy of `checkpoints.sqlite`, the 3 paused threads load and resume to the end.
- [ ] `briefs/baseline-eval.txt` is deleted, `uv run poe check` passes on the final commit, and nothing has been pushed.
