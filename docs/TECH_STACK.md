# Tech stack

- `agent/`: a LangGraph graph with `langchain-anthropic`, and `run_triage` as the entry point. It uses `claude-haiku-4-5-20251001` by default, or the model in the environment variable `MODEL_NAME` if set. The model's decision is a Pydantic class, which the model fills in through one forced tool call. Retrieval embeds locally with `sentence-transformers` and `all-MiniLM-L6-v2`.
- `backend/`: FastAPI around the graph, with no triage logic of its own. Every operation has an `operation_id`, a one-line docstring and no optional inputs.
- `dashboard/`: React, Vite and TypeScript in strict mode, with Assistant, Scoreboard and Tickets tabs. It reaches the agent only through the API. `docs/BRAND.md` has its look.
- `e2e/`: Playwright tests of the real API and graph, with a stub model.
- `evals/`: the evaluation runner and scoring. Scoring is plain code. The simple-classifier yardstick uses scikit-learn, and nothing else is trained.
- `data/`: the knowledge base, invented client records and labelled tickets. The agent never sees the answer files in `data/evals/`.
- `checkpoints.sqlite` holds graph state and `logs.csv` holds the usage log. Both are at the repo root and out of git.

Services arrive in Sprint 2 and hosting in Sprint 3. Each is added here in full by the commit that brings it in.

- **Qdrant:** search over knowledge base sections and past incidents.
- **Supabase:** Postgres for tickets, decisions, reviews, the audit trail and checkpoints, then sign-in.
- **Langfuse:** traces, datasets, experiments and scores.
- **Microsoft Azure:** Container Apps, Key Vault, managed identity, API Management and Claude in Foundry.

Python 3.12 with uv, all in `pyproject.toml`. Node 26 with npm, in the root `package.json`. The Anthropic key is `ANTHROPIC_API_KEY` in `.env`. Paths and settings are in `agent/config.py`.
