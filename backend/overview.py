"""How FirstLine works, for the "How it works" page, built from the code that runs.

The page draws the route a ticket takes from LangGraph's own graph, lists the tools
from `agent/tool_schemas.py`, prices the model from `agent/config.py` and quotes the
latest saved evaluation. Only the plain-English explanations are written here, and
tests fail when a node or tool has none, so the page can't fall behind the code.
"""

import os
from functools import cache

from fastapi import APIRouter
from langgraph.checkpoint.memory import InMemorySaver

from agent import config
from agent.graph import build_graph
from agent.tool_schemas import ESCALATION_TOOL, QUEUES, TOOL_POLICY, TOOLS
from backend import economics
from evals import runner

GOAL = "Every ticket gets a correct first pass before a technician touches it."
WORTH_IT = (
    "It's worth doing if the technician time it saves, in Swiss francs, is well "
    "above what it costs, and nothing unsafe happens."
)
EXAMPLE_SET = "dev"  # examples come from the development set, never the held-out one

# What happens at each node of the graph, in plain words.
STATIONS: dict[str, dict] = {
    "retrieve": {
        "name": "Search the knowledge base",
        "does": (
            "Finds the playbook sections closest in meaning to the ticket, and any "
            "policy that applies. Weak matches are dropped, so a ticket from an "
            "unknown family gets no playbook rather than a wrong one."
        ),
        "cannot": "Change anything. It only reads the knowledge base.",
        "code": "retrieve_node in agent/graph.py, search in agent/retrieval.py",
    },
    "triage": {
        "name": "Decide",
        "does": (
            "One call to the model, which fills in a fixed decision form: its "
            "reasoning first, then the likely cause, the path, and the tool or team."
        ),
        "cannot": (
            "Run anything. The model only proposes, and code checks that every tool "
            "and team it names exists."
        ),
        "code": "triage in agent/graph.py, the form in agent/decision.py",
    },
    "no_tools": {
        "name": "Answer without the knowledge base",
        "does": (
            "With retrieval switched off, the model answers in plain text with no "
            "tools. It exists only to measure what the knowledge base adds."
        ),
        "cannot": "Propose a fix or a ticket.",
        "code": "no_tools in agent/graph.py",
    },
    "confirm_fix": {
        "name": "Approve the fix",
        "does": "Stops and shows the person the fix, with the reason. Nothing has run.",
        "cannot": "Continue until a person says yes or no.",
        "code": "confirm_fix in agent/graph.py",
        "gate": True,
    },
    "execute_tool": {
        "name": "Run the fix",
        "does": "Runs the approved tool with the values the model proposed.",
        "cannot": "Run a tool nobody approved. Every tool here is simulated.",
        "code": "execute_tool in agent/graph.py, tools in agent/tools.py",
    },
    "self_serve_wait": {
        "name": "Did the steps help?",
        "does": "Sends the requester steps to try, and waits for their answer.",
        "cannot": "Close the ticket until the person says the steps worked.",
        "code": "self_serve_wait in agent/graph.py",
        "gate": True,
    },
    "draft_ticket": {
        "name": "Draft a ticket",
        "does": (
            "Writes a ticket from what's already known when a fix was declined or "
            "the steps didn't help, with no new model call."
        ),
        "cannot": "Send it. The next station asks first.",
        "code": "draft_ticket in agent/graph.py",
    },
    "confirm_ticket": {
        "name": "Approve the ticket",
        "does": (
            "Shows the person the team, priority and summary before anything is sent."
        ),
        "cannot": "Open a ticket until a person says yes.",
        "code": "confirm_ticket in agent/graph.py",
        "gate": True,
    },
    "create_ticket": {
        "name": "Open the ticket",
        "does": "Opens the approved ticket in the chosen team's queue.",
        "cannot": "Choose a team that doesn't exist: the 13 queues are fixed in code.",
        "code": "create_ticket in agent/graph.py",
    },
}

# Each path's line after "Decide", and where it goes when the person says no.
LINES: list[dict] = [
    {
        "path": "SELF_SERVE",
        "label": "Self-serve",
        "means": "Steps the requester can follow alone.",
        "stations": ["self_serve_wait"],
        "otherwise": ["draft_ticket", "confirm_ticket", "create_ticket"],
        "otherwise_when": "If the steps didn't help",
    },
    {
        "path": "AUTO_FIX",
        "label": "Auto-fix",
        "means": "A known fix that a tool can run, once a person approves it.",
        "stations": ["confirm_fix", "execute_tool"],
        "otherwise": ["draft_ticket", "confirm_ticket", "create_ticket"],
        "otherwise_when": "If the fix is declined",
    },
    {
        "path": "ESCALATE",
        "label": "Escalate",
        "means": "Another team must act, so it hands over with what's known.",
        "stations": ["confirm_ticket", "create_ticket"],
        "otherwise": [],
        "otherwise_when": "If the ticket is declined, nothing is sent",
    },
    {
        "path": "OUT_OF_SCOPE",
        "label": "Out of scope",
        "means": "Not an IT request, so no action is taken.",
        "stations": [],
        "otherwise": [],
        "otherwise_when": "",
    },
]
TRUNK = ["retrieve", "triage"]

TIERS = {
    "routine": "A person may approve it for their own account or device.",
    "sensitive": "It touches access, security or shared systems, so a technician only.",
}

SERVICES: list[dict] = [
    {
        "name": "Git",
        "holds": "The knowledge base, labels and evaluation runs",
        "truth": True,
        "env": None,
    },
    {
        "name": "Anthropic",
        "holds": "Nothing of ours. It answers each model call",
        "truth": False,
        "env": "ANTHROPIC_API_KEY",
    },
    {
        "name": "Qdrant",
        "holds": "The search index, rebuilt from git at no cost",
        "truth": False,
        "env": "QDRANT_URL",
    },
    {
        "name": "Supabase",
        "holds": "Tickets, decisions, reviews, the audit trail and paused runs",
        "truth": True,
        "env": "SUPABASE_DB_URL",
    },
    {
        "name": "Langfuse",
        "holds": "A trace of every run, and the technicians' verdicts",
        "truth": True,
        "env": "LANGFUSE_PUBLIC_KEY",
    },
]

LIMITS: list[str] = [
    "It has never seen a real client's documentation: the knowledge base is synthetic.",
    "Every tool is simulated. Production needs least-privilege service accounts.",
    "One model call per ticket, with no checks of its own yet. That arrives with "
    "the investigation loop.",
    "It can invent a value, such as a device id that isn't the requester's. The "
    "person who approves is the safeguard until it can look the requester up.",
    "Search works by meaning only, so bare error codes match poorly.",
    "English only, though CorpLabs is Swiss.",
]


def _example_tickets() -> dict[str, dict]:
    """One ticket per path the agent got right, from the newest development run."""
    runs = [r for r in runner.default_runs() if r["set"] == EXAMPLE_SET]
    if not runs:
        return {}
    examples: dict[str, dict] = {}
    for ticket in runs[0]["tickets"]:
        right = str(ticket["path_correct"]) == "True"
        if right and ticket["path"] not in examples:
            title, _, _ = ticket["text"].partition("\n")
            examples[ticket["path"]] = {
                "id": ticket["id"],
                "title": title,
                "family": ticket["family"],
                "cause": ticket["cause"],
                "retrieved": _listed(ticket["retrieved"]),
                "tool": _none(ticket["tool"]),
                "queue": _none(ticket["queue"]),
            }
    return examples


def _none(value: object) -> str | None:
    return None if value in (None, "None", "") else str(value)


def _listed(value: object) -> list[str]:
    """Saved runs keep lists as their text, such as "['vpn', 'sec-02']"."""
    if isinstance(value, list):
        return [str(v) for v in value]
    text = str(value).strip("[]")
    return [part.strip(" '\"") for part in text.split(",") if part.strip(" '\"")]


def _result() -> dict | None:
    """The latest development run's headline numbers."""
    runs = [r for r in runner.default_runs() if r["set"] == EXAMPLE_SET]
    if not runs:
        return None
    run = runs[0]
    s = run["summary"]
    return {
        "run": run["id"],
        "date": run["date"],
        "n": s["n"],
        "path_accuracy": s["path_accuracy"],
        "path_margin": s["path_margin"],
        "cost_per_ticket_chf": s["cost_per_ticket_chf"],
        "time_per_ticket_sec": s["time_per_ticket_sec"],
        "classifier_path_accuracy": run["yardsticks"]["classifier"]["path_accuracy"],
    }


@cache
def graph_edges() -> set[tuple[str, str]]:
    """Every edge in the graph the agent runs."""
    graph = build_graph(InMemorySaver()).get_graph()
    return {(edge.source, edge.target) for edge in graph.edges}


@cache
def graph_nodes() -> list[str]:
    graph = build_graph(InMemorySaver()).get_graph()
    return [node for node in graph.nodes if not node.startswith("__")]


def tools() -> list[dict]:
    rows = []
    for tool in TOOLS:
        policy = TOOL_POLICY.get(tool["name"], {})
        rows.append(
            {
                "name": tool["name"],
                "does": " ".join(tool["description"].split()),
                "tier": policy.get("tier", "sensitive"),
                "owner": policy.get("owner"),
                "escalation": tool["name"] == ESCALATION_TOOL,
            }
        )
    return rows


def model() -> dict:
    name = config.model_name()
    price = config.PRICES.get(name)
    return {
        "name": name,
        "input_usd_per_million": price[0] if price else None,
        "output_usd_per_million": price[1] if price else None,
        "calls_per_ticket": 1,
        "how": (
            "One forced tool call fills in a fixed decision form, reasoning first, "
            "so the model explains before it decides."
        ),
        "why": (
            "The cheapest Claude model that does the job today. A comparison of "
            "models on a sample, with their cost, comes in Sprint 1's last commit."
        ),
    }


router = APIRouter()


@router.get("/api/overview", operation_id="read_overview")
def read_overview() -> dict:
    """How FirstLine works: goal, route, model, tools and services, from the code."""
    return {
        "goal": {
            "sentence": GOAL,
            "worth_it": WORTH_IT,
            "minutes_by_hand": economics.MINUTES_BY_HAND,
            "review_minutes": economics.REVIEW_MINUTES,
            "chf_per_hour": economics.CHF_PER_HOUR,
            "break_even": economics.break_even(economics.REVIEW_MINUTES),
        },
        "result": _result(),
        "trunk": TRUNK,
        "lines": LINES,
        "stations": {node: {"gate": False, **STATIONS[node]} for node in graph_nodes()},
        "examples": _example_tickets(),
        "model": model(),
        "tools": tools(),
        "tiers": TIERS,
        "queues": QUEUES,
        "services": [
            {
                "name": s["name"],
                "holds": s["holds"],
                "truth": s["truth"],
                "connected": s["env"] is None or bool(os.getenv(s["env"])),
            }
            for s in SERVICES
        ],
        "limits": LIMITS,
        "versions": runner.current_versions(),
    }
