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

from agent import records, tracing
from agent.graph import build_graph, initial_state
from agent.rules import Mode


@cache
def _graph():
    return build_graph(InMemorySaver())


def run_triage(
    query: str,
    use_retrieval: bool,
    requester: str | None = None,
    mode: Mode = "queue",
) -> dict:
    """Run triage up to its first gate and return the decision, after the rules.

    `requester` is an AD username from the staff directory, and with None the model
    sees no record. The Queue and the evaluations run in "queue" mode.
    """
    config: RunnableConfig = {
        "configurable": {"thread_id": uuid4().hex},
        "callbacks": tracing.callbacks(),
    }
    state = initial_state(query, use_retrieval, records.requester(requester), mode)
    out = _graph().invoke(state, config)
    return {
        "retrieved": out["retrieved"],
        "use_retrieval": use_retrieval,
        "path": out["path"],
        "reasoning": out["reasoning"],
        "cause": out["cause"],
        "tool_name": out["tool_name"],
        "tool_input": out["tool_input"],
        "usage": out["usage"],
        "response_time_sec": out["response_time_sec"],
        "rule": out["rule"],
        "requester": requester,
        "query": query,
    }
