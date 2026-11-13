"""The loop design's parts that don't call the model: the lookups as tools, running
one call safely, the record of each step, and the decision when a limit is reached.

The graph's `investigate` node calls the model and uses these. The model may call the
four lookups in agent/lookups.py and record_decision, and nothing else. A call to any
other tool, or with arguments that name another ticket, is refused and kept as a
failed step. Code passes the ticket and requester, so the model can't choose them.
"""

import json
from pathlib import Path
from typing import TypedDict

from pydantic import BaseModel, Field, ValidationError

from agent import config, lookups
from agent.decision import DECISION_TOOL_NAME, Decision
from agent.tool_schemas import ESCALATION_TOOL

GUIDE_FILE = Path(__file__).parent / "investigate.md"
RESULT_CHARS = 150  # a step's short result, for the page and the handover
SUMMARY_CHARS = 150
STOP_QUEUE = "DESK-SUPPORT"
STOP_PRIORITY = "P3-Normal"


# ── The lookups, as the model sees them ──────────────────────────────────────────
class Query(BaseModel):
    query: str = Field(description="What to search for, in a few words.")


class Nothing(BaseModel):
    pass


class Check(BaseModel):
    step: str = Field(
        description="The playbook step id, as written in backticks in the playbook."
    )


ARGUMENTS: dict[str, type[BaseModel]] = {
    "search_kb": Query,
    "lookup_requester": Nothing,
    "find_similar_incidents": Query,
    "run_check": Check,
}

DESCRIPTIONS = {
    "search_kb": "Search the playbooks and policies again, with your own words.",
    "lookup_requester": (
        "The requester's directory record: department, office, device, groups, "
        "lockouts in the last 24 hours and recent tickets."
    ),
    "find_similar_incidents": (
        "Closed past tickets most like this one, with their cause and how they were "
        "fixed."
    ),
    "run_check": (
        "The recorded result of one playbook check on this ticket: what was checked, "
        "what healthy looks like, what was seen and whether it passed."
    ),
}


def _schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return schema


# ── The decision, as the loop records it ─────────────────────────────────────────
class LoopDecision(Decision):
    """One triage decision after investigating. Fill the fields in order."""

    evidence: list[str] = Field(
        default=[],
        description=(
            "The ids of the steps your decision rests on, such as s1 and s3, as each"
            " lookup's reply names them. Cite only steps that ran."
        ),
    )
    ruled_out: str = Field(
        default="",
        description="ESCALATE only: the causes your lookups ruled out, and how.",
    )
    next_step: str = Field(
        default="",
        description="ESCALATE only: the first thing the receiving team should do.",
    )


LOOP_DECISION_TOOL = {
    "name": DECISION_TOOL_NAME,
    "description": "Record your triage decision.",
    "input_schema": LoopDecision.model_json_schema(),
}


LOOKUP_TOOLS = [
    {"name": name, "description": DESCRIPTIONS[name], "input_schema": _schema(model)}
    for name, model in ARGUMENTS.items()
]


def guide() -> str:
    return GUIDE_FILE.read_text().replace("{max_lookups}", str(config.MAX_LOOKUPS))


# ── One call ─────────────────────────────────────────────────────────────────────
class Refused(Exception):
    """A call the loop won't run. The model is told why, and the run goes on."""


def run_lookup(
    name: str, arguments: dict, ticket_id: str | None, requester_id: str | None
) -> dict | list:
    """Run one lookup the model asked for, with the ticket and requester code holds."""
    if name not in ARGUMENTS:
        raise Refused(f"{name} is not a lookup. Only {', '.join(ARGUMENTS)} run here.")
    model = ARGUMENTS[name]
    extra = sorted(set(arguments) - set(model.model_fields))
    if extra:
        raise Refused(
            f"{name} takes no {', '.join(extra)}. Lookups read the ticket being "
            "worked and its requester only."
        )
    args = model.model_validate(arguments)
    if isinstance(args, Query):
        search = (
            lookups.search_kb if name == "search_kb" else lookups.find_similar_incidents
        )
        return search(args.query)
    if isinstance(args, Check):
        return lookups.run_check(ticket_id, args.step)
    return lookups.lookup_requester(requester_id)


def _clip(text: str, size: int = RESULT_CHARS) -> str:
    return text if len(text) <= size else text[: size - 1] + "…"


def brief(name: str, result: dict | list) -> str:
    """A step's result in one short line."""
    if isinstance(result, list):
        key = "doc" if name == "search_kb" else "id"
        found = ", ".join(str(item[key]) for item in result)
        return _clip(f"Found {found}.") if found else "Nothing matched."
    if not result.get("found"):
        return _clip(result.get("reason", "No result."))
    if name == "run_check":
        return _clip(f"{result['status']}: {result['observed']}")
    device = (result.get("device") or {}).get("id")
    return _clip(
        f"{result.get('department')}, {result.get('office')}; "
        f"{result.get('lockouts_24h', 0)} lockouts in 24 hours; device {device}."
    )


def found_ids(name: str, result: dict | list) -> list[str]:
    """What a lookup found, by id: the playbooks or incidents a search returned, or
    the check that has a recorded result."""
    if isinstance(result, list):
        key = "doc" if name == "search_kb" else "id"
        return [str(item[key]) for item in result]
    if name == "run_check" and result.get("found"):
        return [str(result["step"])]
    return []


class Step(TypedDict):
    """One call the model made. The model turn that asked for it, its time, tokens
    and cost, is counted on the first step of that turn, so the steps add up.
    `found` names what it found, by id, for the handover and the scores."""

    id: str
    turn: int
    tool: str
    input: dict
    result: str
    ok: bool
    found: list[str]
    time_sec: float
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


class Outcome(TypedDict):
    """One call's outcome: whether it worked, its short result, what it found by id,
    and what the model reads back."""

    ok: bool
    result: str
    found: list[str]
    reply: str


def _failed(short: str, reply: str) -> Outcome:
    return {"ok": False, "result": short, "found": [], "reply": reply}


def run_call(call: dict, ticket_id: str | None, requester_id: str | None) -> Outcome:
    """Run one call. A failure is that step's, never the run's."""
    try:
        result = run_lookup(
            call["name"], call.get("args") or {}, ticket_id, requester_id
        )
    except Refused as exc:
        return _failed(_clip(f"Refused: {exc}"), f"Refused: {exc}")
    except ValidationError as exc:
        reason = f"Unreadable arguments for {call['name']}: {exc.error_count()} errors."
        return _failed(reason, reason)
    except Exception as exc:  # a lookup that breaks fails its step, not the run
        reason = f"{call['name']} failed: {type(exc).__name__}."
        return _failed(reason, reason)
    return {
        "ok": True,
        "result": brief(call["name"], result),
        "found": found_ids(call["name"], result),
        "reply": json.dumps(result, ensure_ascii=False),
    }


def cite(evidence: list[str], steps: list[Step]) -> dict:
    """The model's citations, checked: a step id is kept if that lookup ran, and
    dropped otherwise, so a decision never rests on a step that didn't happen."""
    ran = {step["id"] for step in steps if is_lookup(step) and step["ok"]}
    cited = list(dict.fromkeys(str(e).strip() for e in evidence))
    return {
        "kept": [e for e in cited if e in ran],
        "dropped": [e for e in cited if e not in ran],
    }


def is_lookup(step: Step) -> bool:
    return step["tool"] != DECISION_TOOL_NAME


def lookups_used(steps: list[Step]) -> int:
    """Calls that count against the limit: all but the decision, failed or not."""
    return sum(1 for step in steps if is_lookup(step))


def cost_chf(steps: list[Step]) -> float:
    return sum(step["cost_usd"] or 0.0 for step in steps) * config.USD_TO_CHF


# ── At a limit ───────────────────────────────────────────────────────────────────
STOP_REASONS = {
    "lookups": f"its limit of {config.MAX_LOOKUPS} lookups",
    "cost": f"its limit of CHF {config.MAX_LOOP_CHF:.2f}",
}


def stop_decision(steps: list[Step], stopped: str) -> dict:
    """An escalation to the service desk with what the loop found, when it stopped
    before deciding. Code writes it, so no model call is needed."""
    found = [step for step in steps if is_lookup(step)]
    reasoning = "\n".join(
        [f"The investigation stopped at {STOP_REASONS[stopped]} before deciding."]
        + [
            f"- {step['tool']}({json.dumps(step['input'])}): {step['result']}"
            for step in found
        ]
    )
    summary = (
        f"Investigation stopped at {STOP_REASONS[stopped]}, after {len(found)} lookups."
    )
    return {
        "path": "ESCALATE",
        "tool_name": ESCALATION_TOOL,
        "tool_input": {
            "queue": STOP_QUEUE,
            "summary": summary[:SUMMARY_CHARS],
            "priority": STOP_PRIORITY,
        },
        "reasoning": reasoning,
        "cause": "Unknown",
    }
