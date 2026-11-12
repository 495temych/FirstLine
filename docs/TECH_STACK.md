# Tech stack

- `agent/`: a LangGraph graph with `langchain-anthropic`, and `run_triage` as the entry point. It uses `google/gemini-3.1-flash-lite` through OpenRouter by default, pinned to Google Vertex in the EU, or the model in the environment variable `MODEL_NAME` if set. `agent/models.py` lists every model the benchmark compares, with its price, region and lowest reasoning effort: Claude through Anthropic, OpenAI's models through OpenAI with `langchain-openai`, and the rest through OpenRouter's OpenAI-compatible API, each pinned to one provider that doesn't keep prompts. The model's decision is a Pydantic class, which the model fills in through one forced tool call. Retrieval embeds locally with `sentence-transformers` and `all-MiniLM-L6-v2`.
- `backend/`: FastAPI around the graph, with no triage logic of its own. Every operation has an `operation_id`, a one-line docstring and no optional inputs.
- `dashboard/`: React, Vite and TypeScript in strict mode, in three groups: Try it (Queue, Assistant), Is it worth it? (Money, Models) and How it works (Workflow, Harness, Retrieval, Tickets, Evaluations). Each view has its own link, such as `?view=models`. It reaches the agent only through the API. `docs/BRAND.md` has its look: a sidebar, top bar and page header on every page, in Instrument Sans and IBM Plex Mono.
- `e2e/`: Playwright tests of the real API and graph, with a stub model.
- `evals/`: the evaluation runner and scoring. Scoring is plain code. The simple-classifier yardstick uses scikit-learn, and nothing else is trained.
- `data/`: the knowledge base, invented client records and labelled tickets. The agent never sees the answer files in `data/evals/`.
- Graph state and the usage record live in Supabase, or in memory without `SUPABASE_DB_URL`. The old `logs.csv` stays at the repo root, out of git, for the Langfuse upload only.

Services arrive in Sprint 2 and hosting in Sprint 3. Each is added here in full by the commit that brings it in.

- **Langfuse** (`langfuse` 5.0, kept below 5.1 until that settles): Langfuse Cloud in the EU region traces every Assistant, Queue and evaluation run through LangChain's callback, in `agent/tracing.py`. It exports only its own spans, and masks emails, employee ids and IP addresses first. Practice sets are Langfuse datasets, and saved runs are experiments. Tracing is off without `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`, and tests switch it off.

- **Qdrant** (`qdrant-client` 1.20): Qdrant Cloud holds the knowledge base sections in `kb_sections`, embedded on this machine and built by `uv run -m agent.index`. Its region isn't recorded yet. Search refuses an index built from another knowledge base or embedding model. Without `QDRANT_URL`, and in tests and `poe check`, the same code searches an in-memory index built on first use.
- **Supabase** (Postgres 17, EU Central): the system of record. The schema is in `supabase/migrations/`: batches, tickets, decisions, reviews and an append-only audit trail. Row-level security is on with no policies, so the publishable key reads nothing, and the backend connects directly through `SUPABASE_DB_URL`, the session pooler. The Queue reads and writes it through `backend/store.py` with `psycopg` 3 and `psycopg-pool`, or keeps the same record in memory without `SUPABASE_DB_URL`. `uv run -m backend.migrate` applies new migrations and records them in `schema_migrations`. The store's tests run on a throwaway Postgres 17 through `testcontainers`, so `poe check` needs Docker. LangGraph's checkpoints use `langgraph-checkpoint-postgres`, whose tables `backend.migrate` creates with row-level security on. Sign-in comes later.

Still to come:

- **Qdrant, next:** past incidents, and keyword search beside meaning for error codes.
- **Microsoft Azure:** Container Apps, Key Vault, managed identity, API Management and Claude in Foundry.

Python 3.12 with uv, all in `pyproject.toml`. Node 26 with npm, in the root `package.json`. The Anthropic key is `ANTHROPIC_API_KEY` in `.env`. The benchmark also needs `OPENAI_API_KEY` and `OPENROUTER_API_KEY`. Paths and settings are in `agent/config.py`.
