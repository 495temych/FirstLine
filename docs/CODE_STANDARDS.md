# Code standards

1. Keep it simple, and build only what the documents ask for.
2. Nodes return partial state and never mutate `state`. Routers are pure functions.
3. Side effects never live in an `interrupt()` node, because it re-runs from its first line on resume.
4. Paths and settings go in `agent/config.py`.
5. Add no `# noqa`, `# type: ignore`, `eslint-disable` or `any`.
6. The API stays thin: triage logic and gates live in the graph, and the dashboard only shows them.
