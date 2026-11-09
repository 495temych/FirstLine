# FirstLine

## The context

FirstLine is an L1 IT support triage agent for CorpLabs AG, a fictional company headquartered in Zürich. It is built as a portfolio project for Swiss employers, the way a production team would build it. The owner reviews plans and builds, and you plan, build and check the work.

## Start here

IMPORTANT: before you plan, build or change anything, read each of these in full:

1. `docs/BUSINESS_GOAL.md`: what success means, and how we count it
2. `docs/SPEC.md`: what the business needs
3. `docs/ROADMAP.md`: the current sprint and where the product is heading
4. `docs/TECH_STACK.md`: the tech choices
5. `docs/CODE_STANDARDS.md`: how to write the code
6. `docs/PROCESS.md`: how to run, plan, build and check the work
7. `docs/STATUS.md`: what's built and which rules code enforces
8. `docs/DECISIONS.md`: design decisions, their trade-offs and the known limitations
9. `docs/BRAND.md`: how the dashboard looks, before any dashboard work
10. `docs/EXPLAINABILITY.md`: how a page explains the project, before any dashboard work

## Folders

- `agent/`: the graph, tools, tool schemas, retrieval and instructions. `run_triage` is the entry point, and `config.py` holds paths and settings
- `backend/`: the FastAPI app and usage statistics
- `dashboard/`: the React app
- `e2e/`: browser tests, and the stub server they run against
- `evals/`: the evaluation runner and scoring
- `data/`: start with `data/README.md`, which explains how we use the dataset
- `data/kb/`: the knowledge base
- `data/tickets/`: the imported tickets and their fixed splits
- `data/records/`: staff records, with invented devices, groups and lockouts
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
