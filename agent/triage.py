"""Thin wrapper over the LangGraph triage graph.

`run_triage` keeps the pre-LangGraph contract (used by the evals): run the pipeline up
to the first human gate and return the decision as a plain dict. The graph is compiled
with an in-memory checkpointer, so the run simply pauses at any confirm_* /
self_serve_wait interrupt instead of executing anything.
"""

from functools import cache
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from agent.graph import build_graph, initial_state


@cache
def _graph():
    return build_graph(InMemorySaver())


def run_triage(query: str, use_retrieval: bool) -> dict:
    """Run triage and return a structured result dict."""
    # log_runs=False: eval/library callers must not write to the app's usage log.
    config: RunnableConfig = {
        "configurable": {"thread_id": uuid4().hex, "log_runs": False}
    }
    out = _graph().invoke(initial_state(query, use_retrieval), config)
    return {
        "retrieved": out["retrieved"],
        "use_retrieval": use_retrieval,
        "path": out["path"],
        "reasoning": out["reasoning"],
        "tool_name": out["tool_name"],
        "tool_input": out["tool_input"],
        "query": query,
    }
