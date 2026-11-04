"""LangGraph orchestration for TriagePilot: state, nodes, routers, build_graph().

Flow (see README for the rendered diagram):

    START ─ use_retrieval? ─ off → no_tools → END
                           └ on  → retrieve → triage ─ path:
        OUT_OF_SCOPE → log
        SELF_SERVE   → self_serve_wait
        AUTO_FIX     → confirm_fix
        ESCALATE     → confirm_ticket

Rules this module follows:
  * Nodes return partial state updates and never mutate `state` in place.
  * `interrupt()` nodes (confirm_fix, confirm_ticket, self_serve_wait) do nothing else:
    on resume LangGraph re-runs the node from its first line, so side effects live in
    separate nodes (execute_tool, create_ticket) that only run after the answer is
    stored.
  * Routers are pure functions of state that return node names from a closed Literal
    set.
"""

import csv
import time
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any, Literal

import anthropic
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, interrupt
from typing_extensions import TypedDict

from agent import tools
from agent.config import LOG_FILE, model_name
from agent.retrieval import retrieve
from agent.tool_schemas import TOOLS

_PROMPT_FILE = Path(__file__).parent / "prompt.md"

LOG_FIELDS = [
    "timestamp",
    "query",
    "retrieved_units",
    "decision_path",
    "diagnostic_summary",
    "tool_called",
    "confirmed",
    "escalation_queue",
    "priority",
    "response_time_sec",
]

HEADER_MARKERS = 2  # the opening and closing ** of a bare markdown header
MIN_SUMMARY_CHARS = 15  # shorter lines are labels, not a diagnosis

PATH_KEYWORDS = ("OUT_OF_SCOPE", "SELF_SERVE", "AUTO_FIX", "ESCALATE")


# ── State ───────────────────────────────────────────────────────────────────────
class GraphState(TypedDict):
    query: str
    use_retrieval: bool
    retrieved: list[dict]
    reasoning: str
    # SELF_SERVE | AUTO_FIX | ESCALATE | OUT_OF_SCOPE | NO_TOOLS ("" before triage)
    path: str
    tool_name: str | None
    tool_input: dict | None
    # Operator answers keyed by gate: "fix" (confirm_fix), "ticket" (confirm_ticket),
    # "resolved" (self_serve_wait). Each node writes back the full merged dict.
    human_decision: dict[str, bool]
    ticket_draft: dict | None
    tool_result: dict | None
    response_time_sec: float
    usage: dict | None


def initial_state(query: str, use_retrieval: bool) -> GraphState:
    """Full input for a new run. Every field is reset because the Streamlit app reuses
    one thread_id per session — anything omitted would leak in from the previous run."""
    return {
        "query": query,
        "use_retrieval": use_retrieval,
        "retrieved": [],
        "reasoning": "",
        "path": "",
        "tool_name": None,
        "tool_input": None,
        "human_decision": {},
        "ticket_draft": None,
        "tool_result": None,
        "response_time_sec": 0.0,
        "usage": None,
    }


# ── Pure helpers ────────────────────────────────────────────────────────────────
def build_user_message(query: str, retrieved: list[dict], use_retrieval: bool) -> str:
    if retrieved:
        blocks = []
        for u in retrieved:
            label = u["doc"] + (f" § {u['section']}" if u["section"] else "")
            blocks.append(
                f"**{label}** (similarity score: {u['score']:.2f})\n\n{u['text']}"
            )
        n = len(retrieved)
        return (
            f"User issue: {query}\n\n"
            f"---\n"
            f"Retrieved KB context — {n} unit{'s' if n != 1 else ''} "
            f"(may be from different source documents; synthesize across all of "
            f"them):\n\n" + "\n\n---\n\n".join(blocks)
        )
    if use_retrieval:
        return (
            f"User issue: {query}\n\n"
            f"---\n"
            f"Retrieval returned no confident match for this query. "
            f"Proceed using general knowledge only."
        )
    return f"User issue: {query}"


def _is_header_line(line: str) -> bool:
    # Skip bare markdown headers like "**Step 1 — Diagnose**" — we want the sentence
    # that follows, not the section label.
    return (
        line.startswith("**")
        and line.endswith("**")
        and line.count("**") == HEADER_MARKERS
    )


def diagnostic_summary(reasoning: str, default: str = "") -> str:
    """First substantive line of the model's reasoning."""
    return next(
        (
            line.strip()
            for line in (reasoning or "").split("\n")
            if len(line.strip()) > MIN_SUMMARY_CHARS
            and not _is_header_line(line.strip())
        ),
        default,
    )


def message_blocks(msg: AIMessage) -> list[dict]:
    """Normalize an AIMessage into ordered {"type": "text"|"tool_use", ...} blocks."""
    content = msg.content
    if isinstance(content, str):
        blocks = [{"type": "text", "text": content}] if content else []
    else:
        blocks = [
            {"type": "text", "text": b} if isinstance(b, str) else b for b in content
        ]
    if not any(b.get("type") == "tool_use" for b in blocks):
        blocks += [
            {"type": "tool_use", "name": tc["name"], "input": tc["args"]}
            for tc in msg.tool_calls
        ]
    return blocks


def parse_path(blocks: list[dict]) -> dict:
    """Decide the triage path from the model's content blocks. Pure; no I/O.

    Text blocks set the path via keyword scan; tool_use blocks always win. If the model
    chose ESCALATE in text but never called the ticket tool, a minimal ticket is
    synthesized so the confirmation card can always render.
    Returns: path, reasoning, tool_name, tool_input.
    """
    path = "ESCALATE"
    reasoning = ""
    tool_name = None
    tool_input = None

    for block in blocks:
        if block.get("type") == "text":
            reasoning = block["text"]
            if tool_name is None:  # don't let text override a tool-use decision
                # Use the LAST occurrence of any path keyword — the agent's final
                # "Path chosen: X" sentence wins over earlier mentions in reasoning.
                last_pos, chosen = -1, None
                for candidate in PATH_KEYWORDS:
                    pos = block["text"].rfind(candidate)
                    if pos > last_pos:
                        last_pos, chosen = pos, candidate
                if chosen:
                    path = chosen
        elif block.get("type") == "tool_use":
            tool_name = block["name"]
            tool_input = block["input"]
            path = "ESCALATE" if tool_name == "create_escalation_ticket" else "AUTO_FIX"

    if path == "ESCALATE" and tool_name is None:
        tool_name = "create_escalation_ticket"
        first_line = next(
            (
                line.strip()
                for line in (reasoning or "").split("\n")
                if len(line.strip()) > MIN_SUMMARY_CHARS
            ),
            "Issue escalated — technician review required.",
        )
        tool_input = {
            "queue": "DESKTOP-SUPPORT",
            "summary": first_line[:150],
            "priority": "P3-Normal",
        }

    return {
        "path": path,
        "reasoning": reasoning,
        "tool_name": tool_name,
        "tool_input": tool_input,
    }


def ticket_for(state: GraphState) -> dict:
    """The ticket the operator is being asked to confirm: a drafted one (declined fix /
    self-serve fallback) or the model's own create_escalation_ticket call."""
    draft = state.get("ticket_draft")
    if draft:
        return draft
    ti = state["tool_input"] or {}
    return {
        "source": "escalate",
        "queue": ti.get("queue", "DESKTOP-SUPPORT"),
        "priority": ti.get("priority", "P3-Normal"),
        "summary": ti.get("summary", "—"),
    }


def build_log_row(state: GraphState, now: datetime) -> dict:
    units = state["retrieved"] or []
    retrieved_units = (
        ";".join(
            u["doc"] + (f"::{u['section']}" if u["section"] else "") for u in units
        )
        or "none"
    )
    tool_input = state["tool_input"] or {}
    is_escalate = state["path"] == "ESCALATE"
    # `confirmed` is only meaningful for AUTO_FIX, the one path where declining prevents
    # an action. It records the fix decision, not the follow-up ticket's.
    fix = state["human_decision"].get("fix")
    confirmed = "" if state["path"] != "AUTO_FIX" or fix is None else str(fix).lower()
    return {
        "timestamp": now.isoformat(),
        "query": state["query"],
        "retrieved_units": retrieved_units,
        "decision_path": state["path"],
        "diagnostic_summary": diagnostic_summary(state["reasoning"])[:150],
        "tool_called": state["tool_name"] or "",
        "confirmed": confirmed,
        "escalation_queue": tool_input.get("queue", "") if is_escalate else "",
        "priority": tool_input.get("priority", "") if is_escalate else "",
        "response_time_sec": f"{state['response_time_sec']:.2f}",
    }


# ── Model ───────────────────────────────────────────────────────────────────────
@cache
def _get_llm() -> ChatAnthropic:
    # max_retries=0: transient API errors are retried by the node's RetryPolicy, not
    # twice over by the SDK as well.
    settings: dict[str, Any] = {
        "model": model_name(),
        "max_tokens": 1024,
        "max_retries": 0,
    }
    return ChatAnthropic(**settings)


def _is_api_error(exc: BaseException) -> bool:
    """Retry transient Anthropic failures only (network, timeout, 429, 5xx/529)."""
    return isinstance(
        exc,
        (
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.InternalServerError,
        ),
    )


_API_RETRY = RetryPolicy(max_attempts=3, retry_on=_is_api_error)


def _call_model(state: GraphState) -> tuple[AIMessage, float]:
    llm = _get_llm()
    if state["use_retrieval"]:
        # Tools are withheld entirely when RAG is off, not just retrieval — the agent
        # must reason in plain text only and cannot propose or execute any action.
        llm = llm.bind_tools(TOOLS)
    messages = [
        SystemMessage(_PROMPT_FILE.read_text()),
        HumanMessage(
            build_user_message(
                state["query"], state["retrieved"], state["use_retrieval"]
            )
        ),
    ]
    t0 = time.perf_counter()
    msg = llm.invoke(messages)
    return msg, time.perf_counter() - t0


# ── Nodes ───────────────────────────────────────────────────────────────────────
def retrieve_node(state: GraphState) -> dict:
    return {"retrieved": retrieve(state["query"])}


def usage_of(msg: AIMessage) -> dict:
    meta = msg.usage_metadata or {}
    return {
        "input_tokens": meta.get("input_tokens", 0),
        "output_tokens": meta.get("output_tokens", 0),
    }


def triage(state: GraphState) -> dict:
    msg, elapsed = _call_model(state)
    return {
        **parse_path(message_blocks(msg)),
        "response_time_sec": elapsed,
        "usage": usage_of(msg),
    }


def no_tools(state: GraphState) -> dict:
    """RAG off: one plain-text call with no tools, so there is nothing to classify."""
    msg, elapsed = _call_model(state)
    reasoning = "".join(
        b["text"] for b in message_blocks(msg) if b.get("type") == "text"
    )
    return {
        "retrieved": [],
        "path": "NO_TOOLS",
        "reasoning": reasoning,
        "tool_name": None,
        "tool_input": None,
        "response_time_sec": elapsed,
    }


def confirm_fix(state: GraphState) -> dict:
    approved = interrupt(
        {
            "kind": "confirm_fix",
            "tool_name": state["tool_name"],
            "tool_input": state["tool_input"] or {},
        }
    )
    return {"human_decision": {**state["human_decision"], "fix": bool(approved)}}


def confirm_ticket(state: GraphState) -> dict:
    approved = interrupt({"kind": "confirm_ticket", "ticket": ticket_for(state)})
    return {"human_decision": {**state["human_decision"], "ticket": bool(approved)}}


def self_serve_wait(state: GraphState) -> dict:
    resolved = interrupt({"kind": "self_serve"})
    return {"human_decision": {**state["human_decision"], "resolved": bool(resolved)}}


def execute_tool(state: GraphState) -> dict:
    tool_name = state["tool_name"]
    if tool_name is None:
        raise ValueError("execute_tool needs a proposed tool")
    return {"tool_result": tools.dispatch(tool_name, state["tool_input"] or {})}


def draft_ticket(state: GraphState) -> dict:
    """Pre-fill a ticket from the diagnosis already in state, with no model call."""
    if state["path"] == "SELF_SERVE":
        summary = (
            "Self-serve steps did not resolve the issue. "
            f"Original query: {state['query']}"
        )
        return {
            "ticket_draft": {
                "source": "self_serve",
                "queue": "DESKTOP-SUPPORT",
                "priority": "P3-Normal",
                "summary": summary[:150],
            }
        }

    declined_tool = state["tool_name"] or "unknown"
    reason = "User declined proposed automated fix; issue persists"
    summary = diagnostic_summary(
        state["reasoning"], default="Automated fix did not run; issue not yet resolved."
    )
    ticket_summary = f"{summary} {reason} (declined: {declined_tool})."
    return {
        "ticket_draft": {
            "source": "decline",
            "queue": "DESKTOP-SUPPORT",
            # No model-assigned priority exists on this path, so use the same default as
            # the other synthesized tickets.
            "priority": "P3-Normal",
            "summary": ticket_summary[:150],
            "declined_tool": declined_tool,
            "reason": reason,
            "diagnostic_summary": summary,
        }
    }


def create_ticket(state: GraphState) -> dict:
    t = ticket_for(state)
    return {
        "tool_result": tools.dispatch(
            "create_escalation_ticket",
            {"queue": t["queue"], "summary": t["summary"], "priority": t["priority"]},
        )
    }


def log(state: GraphState, config: RunnableConfig) -> dict:
    """Append one row with the final state. Callers that only want the decision (eval)
    pass configurable `log_runs=False` so evaluations don't pollute logs.csv."""
    if not config.get("configurable", {}).get("log_runs", True):
        return {}
    row = build_log_row(state, datetime.now(UTC))
    # Header goes out once — when the file doesn't exist yet or is empty.
    needs_header = not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerow(row)
    return {}


TriageRoute = Literal["log", "self_serve_wait", "confirm_fix", "confirm_ticket"]


# ── Routers (pure) ──────────────────────────────────────────────────────────────
def route_start(state: GraphState) -> Literal["retrieve", "no_tools"]:
    return "retrieve" if state["use_retrieval"] else "no_tools"


def route_after_triage(state: GraphState) -> TriageRoute:
    routes: dict[str, TriageRoute] = {
        "OUT_OF_SCOPE": "log",
        "SELF_SERVE": "self_serve_wait",
        "AUTO_FIX": "confirm_fix",
        "ESCALATE": "confirm_ticket",
    }
    return routes[state["path"]]


def route_after_confirm_fix(
    state: GraphState,
) -> Literal["execute_tool", "draft_ticket"]:
    return "execute_tool" if state["human_decision"]["fix"] else "draft_ticket"


def route_after_confirm_ticket(state: GraphState) -> Literal["create_ticket", "log"]:
    return "create_ticket" if state["human_decision"]["ticket"] else "log"


def route_after_self_serve(state: GraphState) -> Literal["log", "draft_ticket"]:
    return "log" if state["human_decision"]["resolved"] else "draft_ticket"


# ── Graph ───────────────────────────────────────────────────────────────────────
def build_graph(checkpointer):
    g = StateGraph(GraphState)

    g.add_node("retrieve", retrieve_node)
    g.add_node("triage", triage, retry_policy=_API_RETRY)
    g.add_node("no_tools", no_tools, retry_policy=_API_RETRY)
    g.add_node("confirm_fix", confirm_fix)
    g.add_node("confirm_ticket", confirm_ticket)
    g.add_node("self_serve_wait", self_serve_wait)
    g.add_node("execute_tool", execute_tool)
    g.add_node("draft_ticket", draft_ticket)
    g.add_node("create_ticket", create_ticket)
    g.add_node("log", log)

    g.add_conditional_edges(START, route_start)
    g.add_edge("no_tools", END)
    g.add_edge("retrieve", "triage")
    g.add_conditional_edges("triage", route_after_triage)
    g.add_conditional_edges("confirm_fix", route_after_confirm_fix)
    g.add_conditional_edges("confirm_ticket", route_after_confirm_ticket)
    g.add_conditional_edges("self_serve_wait", route_after_self_serve)
    g.add_edge("execute_tool", "log")
    g.add_edge("draft_ticket", "confirm_ticket")
    g.add_edge("create_ticket", "log")
    g.add_edge("log", END)

    return g.compile(checkpointer=checkpointer)
