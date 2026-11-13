"""The harness around the model on one ticket, for the Harness view, built from code.

What surrounds the model decides as much as the model does: what it reads, the one
tool it can call, the form it must fill, the limits it runs under and the checks
code makes on its answer. This module reads each from the code that runs: the
instructions from `agent/prompt.md`, search from `agent/retrieval.py`, the model from
`agent/models.py`, the form from `agent/decision.py` and the gates from the graph.
Only the plain-English explanations are written here, and tests fail when a field or
a check has none. The fixes the model may propose are counted, not drawn: the
Workflow view shows them.
"""

import re
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from agent import config, decision, graph, models, records, retrieval, rules
from agent.tool_schemas import FIX_TOOLS, QUEUES
from backend import overview
from evals import runner

ANSWER = (
    "For each ticket, code searches the knowledge base, then the model reads its"
    " instructions, the ticket and what search found, and answers once, by filling"
    " in one form. Code checks the form before a person sees it, and nothing runs"
    " until that person says yes."
)

# What the model reads, in the order it reads it, and where each part comes from.
READS: list[dict] = [
    {
        "name": "Instructions",
        "role": "system",
        "what": "How to triage: check the scope, diagnose, choose one path, record it.",
        "code": "agent/prompt.md",
    },
    {
        "name": "The fixes it may propose",
        "role": "system",
        "what": "Each fix's name, values and what it does, so it can name one.",
        "code": "tool_guide in agent/decision.py",
    },
    {
        "name": "The requester's record",
        "role": "user",
        "what": (
            "Their username, department, office, floor, device and groups, from the"
            " staff directory. Never their name or email, nor their lockout count,"
            " which code reads for SEC-04."
        ),
        "code": "requester_block in agent/graph.py",
    },
    {
        "name": "The ticket",
        "role": "user",
        "what": "The title and description, as the requester wrote them.",
        "code": "build_user_message in agent/graph.py",
    },
    {
        "name": "What search found",
        "role": "user",
        "what": (
            "The best playbook in full when it's a clear match, and any policy or"
            " reference close enough, each with its score. With no clear match it's"
            " told so, and answers from general knowledge."
        ),
        "code": "retrieve in agent/retrieval.py",
    },
]

# Each field of the decision form, in plain words, by its name in agent/decision.py.
FIELDS: dict[str, str] = {
    "rationale": "Its reasoning, written first so it reasons before it decides.",
    "cause": "The known cause it found in the playbook, copied exactly, or Unknown.",
    "path": "Self-serve, Auto-fix, Escalate or Out of scope.",
    "steps": "For Self-serve: the steps the requester follows.",
    "tool": "For Auto-fix: which of the fixes to propose.",
    "tool_input": "For Auto-fix: the values the fix needs, such as a device name.",
    "queue": "For Escalate: the team that owns the next step.",
    "summary": "For Escalate: one sentence for that team.",
    "priority": "How urgent the ticket is.",
}

# Every check code makes on the answer, what happens when it fails, and where.
CHECKS: list[dict] = [
    {
        "when": "The answer doesn't fit the form, or there's no form at all",
        "then": (
            f"It becomes an escalation to {decision.DEFAULT_QUEUE}, saying a person"
            " needs to look. It counts as an invalid decision in evaluations."
        ),
        "code": "read_decision in agent/decision.py",
    },
    {
        "when": f"The fix it names isn't one of the {len(FIX_TOOLS)} fixes",
        "then": f"It becomes an escalation to {decision.DEFAULT_QUEUE} instead.",
        "code": "_action in agent/decision.py",
    },
    {
        "when": f"The team it names isn't one of the {len(QUEUES)} queues, or none",
        "then": f"The ticket goes to {decision.DEFAULT_QUEUE}.",
        "code": "_action in agent/decision.py",
    },
    {
        "when": "The provider times out, is busy or drops the connection",
        "then": (
            f"The call is tried up to {graph.MODEL_ATTEMPTS} times. After that the"
            " ticket fails, and the Queue shows it to a person."
        ),
        "code": "MODEL_ATTEMPTS in agent/graph.py",
    },
    {
        "when": "The requester has 2+ lockouts in the records, on a lockout ticket",
        "then": (
            f"It goes to {rules.SECURITY_QUEUE} at {rules.SECURITY_PRIORITY} under"
            " SEC-04, whatever the model proposed, and the override is kept."
        ),
        "code": "sec04 in agent/rules.py",
    },
    {
        "when": "In the Assistant, the fix it names is a sensitive one",
        "then": (
            f"It becomes a ticket to {rules.TECHNICIAN_QUEUE} naming the fix, because"
            " only a technician may run it."
        ),
        "code": "sensitive_fix in agent/rules.py",
    },
    {
        "when": "The path is Out of scope",
        "then": "Nothing runs and no ticket is opened.",
        "code": "route_after_triage in agent/graph.py",
    },
]

LOOP = (
    "The model answers in one pass: it's given the requester's record, but it can't"
    " look up a device, run a check or search again, so all it knows is what it was"
    " given."
    " The loop, with four read-only lookups, is built and tested without a model, but"
    " it isn't the default: commit 7b measures it against this one call, and keeps it"
    " only if it earns its extra cost."
)


def _sections(text: str) -> list[str]:
    """The instructions' steps and rules, by their bold headings."""
    return re.findall(r"(?m)^\*\*([^*\n]+)\*\*[ \t]*$", text)


def _form() -> list[dict]:
    schema = decision.Decision.model_json_schema()
    required = set(schema.get("required", []))
    return [
        {
            "name": name,
            "means": FIELDS[name],
            "required": name in required,
            "choices": prop.get("enum") or None,
        }
        for name, prop in schema["properties"].items()
    ]


def _model() -> dict:
    name = config.model_name()
    model = models.MODELS.get(name)
    return {
        "name": name,
        "label": models.label(name),
        "lab": model.lab if model else "anthropic",
        "provider": model.provider if model else None,
        "region": model.region if model else "US",
        "effort": model.effort if model else None,
        "max_tokens": models.MAX_TOKENS,
        "attempts": graph.MODEL_ATTEMPTS,
        "forced": models.tool_choice(name, decision.DECISION_TOOL_NAME) != "auto",
    }


def _examples() -> list[dict]:
    """The development tickets the default model's latest full run decided."""
    run = next((r for r in runner.default_runs() if r["set"] == "dev"), None)
    if run is None:
        return []
    return [
        {"id": t["id"], "title": t["text"].partition("\n")[0], "family": t["family"]}
        for t in run["tickets"]
    ]


def view() -> dict:
    text = config.PROMPT_FILE.read_text()
    gates = [s["name"] for s in overview.STATIONS.values() if s.get("gate")]
    return {
        "answer": ANSWER,
        "instructions": {
            "file": "agent/prompt.md",
            "words": len(text.split()),
            "sections": _sections(text),
            "text": text,
        },
        "search": {
            "embedding_model": retrieval.EMBEDDING_MODEL,
            "sure": retrieval.PLAYBOOK_SURE,
            "threshold": retrieval.PLAYBOOK_THRESHOLD,
            "margin": retrieval.PLAYBOOK_MARGIN,
            "support": retrieval.SUPPORT_THRESHOLD,
            "top_k": retrieval.TOP_K,
        },
        "reads": READS,
        "fixes": len(FIX_TOOLS),
        "model": _model(),
        "tool": {
            "name": decision.DECISION_TOOL_NAME,
            "description": decision.DECISION_TOOL["description"],
            "fields": _form(),
        },
        "checks": CHECKS,
        "loop": {"built": False, "calls": 1, "text": LOOP},
        "gates": gates,
        "examples": _examples(),
    }


def read(ticket_id: str) -> dict | None:
    """What the model read for one development ticket, and what the default model
    answered in its latest saved run. Search runs on this machine, with no model call.
    """
    run = next((r for r in runner.default_runs() if r["set"] == "dev"), None)
    ticket = next(
        (t for t in (run or {}).get("tickets", []) if t["id"] == ticket_id), None
    )
    if run is None or ticket is None:
        return None
    found = retrieval.retrieve(ticket["text"])
    return {
        "id": ticket_id,
        "run": run["id"],
        "found": [
            {k: u[k] for k in ("doc", "kind", "section", "score")} for u in found
        ],
        "message": graph.build_user_message(
            ticket["text"], found, True, records.requester(ticket.get("requester"))
        ),
        "answer": {
            "path": ticket["path"],
            "cause": ticket.get("cause"),
            "tool": ticket.get("tool"),
            "queue": ticket.get("queue"),
            "invalid": bool(ticket.get("invalid")),
            "right": str(ticket["action_correct"]) == "True",
            "expected": ticket["expected_paths"],
        },
    }


router = APIRouter()


@router.get("/api/harness", operation_id="read_harness")
def read_harness() -> dict:
    """What surrounds the model on one ticket: what it reads, the one tool it can
    call, the form, its limits and the checks on its answer.
    """
    return view()


@router.get("/api/harness/tickets/{ticket_id}", operation_id="read_harness_ticket")
def read_harness_ticket(
    ticket_id: Annotated[str, Path(pattern=r"^[A-Z0-9-]{1,40}$")],
) -> dict:
    """What the model read for one development ticket, and what it answered."""
    found = read(ticket_id)
    if found is None:
        raise HTTPException(404, "No saved decision for that development ticket.")
    return found
