# FirstLine

## The context

FirstLine is an L1 IT support triage agent for Sihlwerk IT AG, a fictional Swiss IT service provider. Its first client is the fictional Limmatica AG. It is built as a portfolio project for Swiss employers, the way a production team would build it. The owner reviews plans and builds, and you plan, build and check the work.

## Start here

IMPORTANT: before you plan, build or change anything, read each of these in full:

1. `docs/SPEC.md`: what the business needs
2. `docs/ROADMAP.md`: the current sprint and where the product is heading
3. `docs/TECH_STACK.md`: the tech choices
4. `docs/CODE_STANDARDS.md`: how to write the code
5. `docs/PROCESS.md`: how to run, plan, build and check the work
6. `docs/STATUS.md`: what's built and which rules code enforces
7. `docs/DECISIONS.md`: design decisions, their trade-offs and the known limitations
8. `docs/BRAND.md`: how the dashboard looks, before any dashboard work

Until the baseline is done, also read `docs/EVALS.md` and `docs/PLAN_EVALS.md`.

## Folders

- `agent/`: the graph, tools, tool schemas, retrieval and instructions. `run_triage` is the entry point, and `config.py` holds paths and settings
- `backend/`: the FastAPI app and usage statistics
- `dashboard/`: the React app
- `e2e/`: browser tests, and the stub server they run against
- `evals/`: the evaluation runner and scoring
- `data/kb/`: the knowledge base
- `data/tickets/`: the imported tickets and their fixed splits
- `data/records/`: invented client records
- `data/evals/`: labelled tickets, their answers, incident answers, and saved runs and retrieval scores
- `docs/`: project documents
- `briefs/`: notes waiting for a sprint, when there are any

Each package keeps its tests in its own `tests/` folder.

## This machine

The repository is in an iCloud-synced folder.

- The virtual environment must stay in `.venv.nosync`, with `.venv` a link to it. iCloud skips `*.nosync`. Never rebuild it as a plain `.venv`.
- `node_modules` must likewise be a link to `node_modules.nosync`. `npm install` replaces the link with a real folder, so after any install that does, run `rm -rf node_modules.nosync && mv node_modules node_modules.nosync && ln -s node_modules.nosync node_modules`.
- If `prettier: command not found` appears, or a link called `node_modules 2`, iCloud has restored an old copy of the folder. `node_modules.nosync` is still complete. Run `rm -f "node_modules 2"; mv node_modules node_modules.old.nosync && ln -s node_modules.nosync node_modules`. Don't `rm -rf` or move the restored folder out of the repository first, because both hang on files iCloud hasn't downloaded.
- If anything hangs, check for offloaded files first: `find . -flags +dataless | wc -l`.
