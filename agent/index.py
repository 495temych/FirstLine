"""Builds the knowledge base index in Qdrant Cloud, from the files in git.

`uv run -m agent.index` embeds every section on this machine and replaces the
collection, so it's safe to run again. Run it after any knowledge base change.
"""

import os

from agent import retrieval


def main() -> None:
    if not os.getenv("QDRANT_URL"):
        raise SystemExit("Add QDRANT_URL and QDRANT_API_KEY to .env.")
    client = retrieval.cloud_client()
    count = retrieval.build_index(client)
    problem = retrieval.index_problem(client)
    if problem:
        raise SystemExit(f"The index didn't check out: {problem}.")
    print(
        f"{count} sections in {retrieval.COLLECTION}, "
        f"knowledge base {retrieval.kb_version()}"
    )


if __name__ == "__main__":
    main()
