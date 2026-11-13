"""LangGraph orchestration for FirstLine: state, nodes, routers, build_graph().

Flow (see README for the rendered diagram):

    START ─ use_retrieval? ─ off → no_tools → END
                           └ on  → retrieve ─ design? ─ one call → triage ─┐
                                                       └ loop → investigate ⟲ ─┤
                                                         (at a limit → at_limit)┘
                                                                     → enforce ─ path:
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

import time
from functools import cache
from pathlib import Path
from typing import Literal

import anthropic
import openai
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, interrupt
from qdrant_client.http.exceptions import ResponseHandlingException
from typing_extensions import TypedDict

from agent import config, handover, loop, rules, tools
from agent.config import Design, model_name
from agent.decision import (
    DECISION_TOOL,
    DECISION_TOOL_NAME,
    DEFAULT_PRIORITY,
    DEFAULT_QUEUE,
    UNREADABLE,
    read_decision,
    tool_guide,
)
from agent.models import any_tool, chat_model, tool_choice
from agent.retrieval import retrieve

_PROMPT_FILE = Path(__file__).parent / "prompt.md"


HEADER_MARKERS = 2  # the opening and closing ** of a bare markdown header
MIN_SUMMARY_CHARS = 15  # shorter lines are labels, not a diagnosis


# ── State ───────────────────────────────────────────────────────────────────────
class GraphState(TypedDict):
    query: str
    use_retrieval: bool
    # The requester's record from data/records, or None when nobody is named.
    requester: dict | None
    mode: rules.Mode
    retrieved: list[dict]
    reasoning: str
    cause: str
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
    # Set when a rule in agent/rules.py changed the model's decision.
    rule: rules.Override | None
    # The imported ticket being worked, whose recorded checks run_check reads.
    ticket_id: str | None
    design: Design
    # The loop's conversation with the model, and each call it made.
    messages: list[AnyMessage]
    steps: list[loop.Step]
    # Why the loop stopped before deciding: "lookups" or "cost", else None.
    stopped: str | None
    # The loop's checked citations, {"kept": [...], "dropped": [...]}, its notes for
    # the receiving team, and the handover code builds for an escalation.
    citations: dict | None
    notes: dict | None
    handover: handover.Handover | None


def initial_state(
    query: str,
    use_retrieval: bool,
    requester: dict | None,
    mode: rules.Mode,
    ticket_id: str | None = None,
) -> GraphState:
    """Full input for a new run. Every field is set, so nothing is left to chance.
    The design is DESIGN's, or the default. `ticket_id` names an imported ticket."""
    return {
        "query": query,
        "use_retrieval": use_retrieval,
        "requester": requester,
        "mode": mode,
        "retrieved": [],
        "reasoning": "",
        "cause": "",
        "path": "",
        "tool_name": None,
        "tool_input": None,
        "human_decision": {},
        "ticket_draft": None,
        "tool_result": None,
        "response_time_sec": 0.0,
        "usage": None,
        "rule": None,
        "ticket_id": ticket_id,
        "design": config.design(),
        "messages": [],
        "steps": [],
        "stopped": None,
        "citations": None,
        "notes": None,
        "handover": None,
    }


# ── Pure helpers ────────────────────────────────────────────────────────────────
# What a technician would use from the record. The name and email stay out, and so
# does the lockout count: SEC-04 reads it in code, and a count of 0 in the records
# talked the model out of the lockouts a ticket describes (docs/DECISIONS.md).
REQUESTER_FIELDS = ("id", "department", "office", "floor", "groups")
DEVICE_FIELDS = ("id", "model", "image", "age_years", "battery_health", "dock")


def requester_block(requester: dict | None) -> str:
    """The requester's record as the model reads it, or nothing without one."""
    if requester is None:
        return ""
    lines = [f"- {field}: {requester.get(field)}" for field in REQUESTER_FIELDS]
    device = requester.get("device") or {}
    lines += [f"- device {field}: {device.get(field)}" for field in DEVICE_FIELDS]
    return (
        "Requester record (from the staff directory; `id` is the AD username and "
        "`device id` the device):\n" + "\n".join(lines) + "\n\n"
    )


def build_user_message(
    query: str,
    retrieved: list[dict],
    use_retrieval: bool,
    requester: dict | None = None,
) -> str:
    return requester_block(requester) + _issue_message(query, retrieved, use_retrieval)


def _issue_message(query: str, retrieved: list[dict], use_retrieval: bool) -> str:
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


def decision_arguments(msg: AIMessage) -> dict | None:
    """The arguments of the model's decision, if it recorded one."""
    calls = [b for b in message_blocks(msg) if b.get("type") == "tool_use"]
    return calls[0]["input"] if calls else None


def ticket_for(state: GraphState) -> dict:
    """The ticket the operator is being asked to confirm: a drafted one (declined fix /
    self-serve fallback) or the model's own create_escalation_ticket call."""
    draft = state.get("ticket_draft")
    if draft:
        return draft
    ti = state["tool_input"] or {}
    return {
        "source": "escalate",
        "queue": ti.get("queue", DEFAULT_QUEUE),
        "priority": ti.get("priority", DEFAULT_PRIORITY),
        "summary": ti.get("summary", "—"),
    }


# ── Model ───────────────────────────────────────────────────────────────────────
@cache
def _client(name: str) -> BaseChatModel:
    return chat_model(name)


def _get_llm() -> BaseChatModel:
    return _client(model_name())


def _is_api_error(exc: BaseException) -> bool:
    """Retry transient API failures only (network, timeout, 429, 5xx/529)."""
    return isinstance(
        exc,
        (
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.InternalServerError,
            openai.APIConnectionError,
            openai.RateLimitError,
            openai.InternalServerError,
        ),
    )


MODEL_ATTEMPTS = 3  # a model call that fails for a passing reason is tried this often
_API_RETRY = RetryPolicy(max_attempts=MODEL_ATTEMPTS, retry_on=_is_api_error)


def _is_search_error(exc: BaseException) -> bool:
    """Retry a search that couldn't reach the index. A retry costs nothing."""
    return isinstance(exc, ResponseHandlingException)


_SEARCH_RETRY = RetryPolicy(max_attempts=3, retry_on=_is_search_error)


def _opening(state: GraphState, extra: str = "") -> list[AnyMessage]:
    """The instructions and the ticket, as the model's first two messages."""
    instructions = _PROMPT_FILE.read_text()
    if state["use_retrieval"]:
        instructions += f"\n\n**Remediation tools**\n{tool_guide()}"
    message = build_user_message(
        state["query"], state["retrieved"], state["use_retrieval"], state["requester"]
    )
    return [SystemMessage(instructions + extra), HumanMessage(message)]


def _call_model(state: GraphState) -> tuple[AIMessage, float]:
    llm = _get_llm()
    if state["use_retrieval"]:
        # Tools are withheld entirely when RAG is off, not just retrieval — the agent
        # must reason in plain text only and cannot propose or execute any action.
        choice = tool_choice(model_name(), DECISION_TOOL_NAME)
        llm = llm.bind_tools([DECISION_TOOL], tool_choice=choice)
    messages = _opening(state)
    t0 = time.perf_counter()
    msg = llm.invoke(messages)
    return msg, time.perf_counter() - t0


# ── Nodes ───────────────────────────────────────────────────────────────────────
def retrieve_node(state: GraphState) -> dict:
    return {"retrieved": retrieve(state["query"])}


def usage_of(msg: AIMessage) -> dict:
    """Tokens, and the cost when the provider reports it, as OpenRouter does."""
    meta = msg.usage_metadata or {}
    reported = (msg.response_metadata.get("token_usage") or {}).get("cost")
    return {
        "input_tokens": meta.get("input_tokens", 0),
        "output_tokens": meta.get("output_tokens", 0),
        "cost_usd": None if reported is None else float(reported),
    }


def triage(state: GraphState) -> dict:
    msg, elapsed = _call_model(state)
    return {
        **read_decision(decision_arguments(msg)),
        "response_time_sec": elapsed,
        "usage": usage_of(msg),
    }


def _tool_calls(msg: AIMessage) -> list[dict]:
    """Every call in a turn, with unreadable ones kept, so each fails as a step."""
    broken = [
        {"name": call.get("name") or "unknown", "args": None, "id": call.get("id")}
        for call in msg.invalid_tool_calls
    ]
    return [dict(call) for call in msg.tool_calls] + broken


def _turn_usage(msg: AIMessage, elapsed: float) -> dict:
    """One model turn's time, tokens and cost, priced from the list when unreported."""
    usage = usage_of(msg)
    if usage["cost_usd"] is None:
        usage["cost_usd"] = config.cost_usd(
            model_name(), usage["input_tokens"], usage["output_tokens"]
        )
    return {"time_sec": elapsed, **usage}


def _total(usage: dict | None, turn: dict) -> dict:
    before = usage or {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    cost = None
    if before["cost_usd"] is not None and turn["cost_usd"] is not None:
        cost = before["cost_usd"] + turn["cost_usd"]
    return {
        "input_tokens": before["input_tokens"] + turn["input_tokens"],
        "output_tokens": before["output_tokens"] + turn["output_tokens"],
        "cost_usd": cost,
    }


def _step(
    number: int, turn: int, call: dict, outcome: loop.Outcome, cost: dict
) -> loop.Step:
    return {
        "id": f"s{number}",
        "turn": turn,
        "tool": call["name"],
        "input": call.get("args") or {},
        "result": outcome["result"],
        "ok": outcome["ok"],
        "found": outcome["found"],
        "time_sec": cost["time_sec"],
        "input_tokens": cost["input_tokens"],
        "output_tokens": cost["output_tokens"],
        "cost_usd": cost["cost_usd"],
    }


def _loop_model(left: int) -> Runnable:
    """The model with the lookups and the decision, or only the decision once the
    lookups are used up."""
    if left > 0:
        offered = [*loop.LOOKUP_TOOLS, loop.LOOP_DECISION_TOOL]
        return _get_llm().bind_tools(offered, tool_choice=any_tool(model_name()))
    choice = tool_choice(model_name(), DECISION_TOOL_NAME)
    return _get_llm().bind_tools([loop.LOOP_DECISION_TOOL], tool_choice=choice)


FREE = {"time_sec": 0.0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}


def _run_lookups(
    state: GraphState, calls: list[dict], left: int, turn: int, cost: dict
) -> tuple[list[loop.Step], list[AnyMessage]]:
    """Run the turn's lookups, up to the limit, and the replies the model reads."""
    steps, replies = list(state["steps"]), []
    for index, call in enumerate(calls):
        started = time.perf_counter()
        if index < left:
            outcome = loop.run_call(call, state["ticket_id"], _requester_id(state))
        else:
            over = f"Over the limit of {config.MAX_LOOKUPS} lookups."
            outcome = loop.Outcome(ok=False, result=over, found=[], reply=over)
        spent = cost if index == 0 else FREE
        took = {**spent, "time_sec": spent["time_sec"] + time.perf_counter() - started}
        step = _step(len(steps) + 1, turn, call, outcome, took)
        steps.append(step)
        call_id = call.get("id") or f"call-{len(steps)}"
        # The model reads each step's id, so it can cite the steps it relied on.
        reply = f"Step {step['id']}. {outcome['reply']}"
        replies.append(ToolMessage(reply, tool_call_id=call_id))
    return steps, replies


def investigate(state: GraphState) -> dict:
    """One turn of the loop: the model looks something up or decides.

    The lookups it asks for run here, read-only, with the ticket and requester code
    holds. After its last lookup the model may only decide. A turn with no call, or
    an unreadable decision, goes to a person, as in one call.
    """
    left = config.MAX_LOOKUPS - loop.lookups_used(state["steps"])
    messages = state["messages"] or _opening(state, "\n\n" + loop.guide())
    t0 = time.perf_counter()
    msg = _loop_model(left).invoke(messages)
    cost = _turn_usage(msg, time.perf_counter() - t0)
    turn = sum(isinstance(m, AIMessage) for m in messages) + 1
    calls = _tool_calls(msg)
    decision = next((c for c in calls if c["name"] == DECISION_TOOL_NAME), None)
    update: dict = {
        "usage": _total(state["usage"], cost),
        "response_time_sec": state["response_time_sec"] + cost["time_sec"],
    }
    if decision is not None or not calls:
        made = read_decision(decision["args"] if decision else None, loop.LoopDecision)
        extra = made.pop("extra", {})
        call = decision or {"name": DECISION_TOOL_NAME, "args": {}}
        outcome: loop.Outcome = {
            "ok": made["reasoning"] != UNREADABLE,
            "result": made["path"],
            "found": [],
            "reply": "",
        }
        step = _step(len(state["steps"]) + 1, turn, call, outcome, cost)
        return {
            **update,
            **made,
            "steps": [*state["steps"], step],
            "messages": [*messages, msg],
            "citations": loop.cite(extra.get("evidence", []), state["steps"]),
            "notes": {key: extra.get(key, "") for key in ("ruled_out", "next_step")},
        }
    steps, replies = _run_lookups(state, calls, left, turn, cost)
    stopped = None
    if left <= 0:
        stopped = "lookups"
    elif loop.cost_chf(steps) >= config.MAX_LOOP_CHF:
        stopped = "cost"
    return {
        **update,
        "steps": steps,
        "messages": [*messages, msg, *replies],
        "stopped": stopped,
    }


def _requester_id(state: GraphState) -> str | None:
    return (state["requester"] or {}).get("id")


def at_limit(state: GraphState) -> dict:
    """The loop stopped before deciding: escalate what it found, with no model call."""
    return loop.stop_decision(state["steps"], state["stopped"] or "lookups")


def enforce(state: GraphState) -> dict:
    """Apply the rules in code to the model's decision. They can overrule it."""
    proposed: rules.Proposal = {
        "path": state["path"],
        "tool_name": state["tool_name"],
        "tool_input": state["tool_input"],
    }
    decision, override = rules.enforce(
        proposed, state["requester"], state["retrieved"], state["mode"]
    )
    update: dict = {**decision, "rule": override}
    if state["design"] == "loop" and decision["path"] == "ESCALATE":
        update["handover"] = handover.build(state, decision["tool_input"] or {})
    return update


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
                "queue": DEFAULT_QUEUE,
                "priority": DEFAULT_PRIORITY,
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
            "queue": DEFAULT_QUEUE,
            # No model-assigned priority exists on this path, so use the same default as
            # the other synthesized tickets.
            "priority": DEFAULT_PRIORITY,
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


# LangGraph's END, whose value this is, typed so the routers can return it.
DONE: Literal["__end__"] = "__end__"

TriageRoute = Literal["__end__", "self_serve_wait", "confirm_fix", "confirm_ticket"]
LoopRoute = Literal["enforce", "at_limit", "investigate"]


# ── Routers (pure) ──────────────────────────────────────────────────────────────
def route_start(state: GraphState) -> Literal["retrieve", "no_tools"]:
    return "retrieve" if state["use_retrieval"] else "no_tools"


def route_design(state: GraphState) -> Literal["triage", "investigate"]:
    return "investigate" if state["design"] == "loop" else "triage"


def route_after_investigate(state: GraphState) -> LoopRoute:
    if state["path"]:
        return "enforce"
    return "at_limit" if state["stopped"] else "investigate"


def route_after_triage(state: GraphState) -> TriageRoute:
    routes: dict[str, TriageRoute] = {
        "OUT_OF_SCOPE": DONE,
        "SELF_SERVE": "self_serve_wait",
        "AUTO_FIX": "confirm_fix",
        "ESCALATE": "confirm_ticket",
    }
    return routes[state["path"]]


def route_after_confirm_fix(
    state: GraphState,
) -> Literal["execute_tool", "draft_ticket"]:
    return "execute_tool" if state["human_decision"]["fix"] else "draft_ticket"


def route_after_confirm_ticket(
    state: GraphState,
) -> Literal["create_ticket", "__end__"]:
    return "create_ticket" if state["human_decision"]["ticket"] else DONE


def route_after_self_serve(state: GraphState) -> Literal["__end__", "draft_ticket"]:
    return DONE if state["human_decision"]["resolved"] else "draft_ticket"


# ── Graph ───────────────────────────────────────────────────────────────────────
def build_graph(checkpointer):
    g = StateGraph(GraphState)

    g.add_node("retrieve", retrieve_node, retry_policy=_SEARCH_RETRY)
    g.add_node("triage", triage, retry_policy=_API_RETRY)
    g.add_node("no_tools", no_tools, retry_policy=_API_RETRY)
    g.add_node("confirm_fix", confirm_fix)
    g.add_node("confirm_ticket", confirm_ticket)
    g.add_node("self_serve_wait", self_serve_wait)
    g.add_node("execute_tool", execute_tool)
    g.add_node("draft_ticket", draft_ticket)
    g.add_node("create_ticket", create_ticket)

    g.add_conditional_edges(START, route_start)
    g.add_edge("no_tools", END)
    g.add_node("investigate", investigate, retry_policy=_API_RETRY)
    g.add_node("at_limit", at_limit)
    g.add_node("enforce", enforce)
    g.add_conditional_edges("retrieve", route_design)
    g.add_edge("triage", "enforce")
    g.add_conditional_edges("investigate", route_after_investigate)
    g.add_edge("at_limit", "enforce")
    g.add_conditional_edges("enforce", route_after_triage)
    g.add_conditional_edges("confirm_fix", route_after_confirm_fix)
    g.add_conditional_edges("confirm_ticket", route_after_confirm_ticket)
    g.add_conditional_edges("self_serve_wait", route_after_self_serve)
    g.add_edge("execute_tool", END)
    g.add_edge("draft_ticket", "confirm_ticket")
    g.add_edge("create_ticket", END)

    return g.compile(checkpointer=checkpointer)
