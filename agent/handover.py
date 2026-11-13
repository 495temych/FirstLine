"""The handover an escalation carries, so the receiving team starts where the agent
stopped. Code fills in every fact: the requester, device, priority, SLA deadline,
applications, the checks with their evidence, similar incidents and what's still
unknown. The model writes only the likely cause, what it ruled out and the next step.
"""

import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Any, TypedDict
from zoneinfo import ZoneInfo

from agent import config
from agent.loop import Step, is_lookup

QUEUES_FILE = config.KB_DIR / "escalation-queues.md"
ZURICH = ZoneInfo("Europe/Zurich")
DAY_START, DAY_END = 8, 17  # business hours in Zürich, Monday to Friday
HOURS_PER_DAY = DAY_END - DAY_START
WEEKEND = 5  # Saturday, as datetime.weekday() counts
TABLE_COLUMNS = 4  # queue, team, owns, typical SLA


class Handover(TypedDict):
    requester: dict | None
    device: dict | None
    queue: str
    priority: str
    sla: str | None
    submitted_at: str | None
    deadline: str | None
    applications: list[str]
    checks: list[dict]
    similar: list[str]
    unknown: list[str]
    cause: str
    ruled_out: str
    next_step: str


# ── The SLA ──────────────────────────────────────────────────────────────────────
@cache
def slas() -> dict[str, str]:
    """Each queue's typical SLA, from the knowledge base's table of queues."""
    found = {}
    for line in QUEUES_FILE.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == TABLE_COLUMNS and cells[0].startswith("`"):
            found[cells[0].strip("`")] = cells[3]
    return found


def sla_hours(sla: str) -> float | None:
    """Business hours an SLA allows: '4 business hours', '1 business day' or
    'Immediate'. None for a wording it doesn't know."""
    if sla.lower() == "immediate":
        return 0.0
    match = re.fullmatch(r"(\d+) business (hours?|days?)", sla.lower())
    if not match:
        return None
    count = int(match.group(1))
    return float(count if match.group(2).startswith("hour") else count * HOURS_PER_DAY)


def _next_open(at: datetime) -> datetime:
    """The first business moment at or after `at`, in Zürich."""
    while True:
        start = at.replace(hour=DAY_START, minute=0, second=0, microsecond=0)
        end = at.replace(hour=DAY_END, minute=0, second=0, microsecond=0)
        if at.weekday() >= WEEKEND or at >= end:
            at = (start + timedelta(days=1)).replace(hour=DAY_START)
        elif at < start:
            return start
        else:
            return at


def add_business_hours(start: datetime, hours: float) -> datetime:
    """`start` plus `hours` of Zürich business time. An immediate SLA is due at once."""
    if hours <= 0:
        return start
    at = _next_open(start.astimezone(ZURICH))
    left = timedelta(hours=hours)
    while True:
        close = at.replace(hour=DAY_END, minute=0, second=0, microsecond=0)
        if at + left <= close:
            return (at + left).astimezone(UTC)
        left -= close - at
        at = _next_open(close)


# ── The ticket ───────────────────────────────────────────────────────────────────
@cache
def _tickets() -> dict[str, dict]:
    tickets = json.loads((config.TICKETS_DIR / "tickets.json").read_text())
    return {ticket["id"]: ticket for ticket in tickets}


def _submitted(ticket: dict | None, now: datetime) -> datetime:
    if ticket and ticket.get("submitted_at"):
        return datetime.fromisoformat(ticket["submitted_at"].replace("Z", "+00:00"))
    return now


def _requester(record: dict | None) -> dict | None:
    if not record:
        return None
    return {key: record.get(key) for key in ("id", "department", "office", "floor")}


def _device(record: dict | None) -> dict | None:
    device = (record or {}).get("device")
    if not device:
        return None
    return {key: device.get(key) for key in ("id", "model", "image", "age_years")}


def _unknown(
    steps: list[Step], record: dict | None, cause: str, deadline: str | None
) -> list[str]:
    """What the receiving team still has to find out, from what didn't come back."""
    out = []
    if not record:
        out.append("Who the requester is: no one is named on the ticket.")
    elif not record.get("device"):
        out.append("The requester's device: none is on record.")
    for step in steps:
        if not is_lookup(step):
            continue
        if not step["ok"]:
            out.append(f"{step['tool']} failed: {step['result']}")
        elif step["tool"] == "run_check" and not step.get("found"):
            out.append(f"{step['input'].get('step')}: no recorded result.")
    if cause in {"", "Unknown"}:
        out.append("The cause: the evidence didn't confirm one.")
    if deadline is None:
        out.append("The SLA deadline: the queue's SLA isn't in the table of queues.")
    return out


def build(
    state: Mapping[str, Any], tool_input: dict, now: datetime | None = None
) -> Handover:
    """The handover for an escalation, from the run's state: what the loop found,
    the requester's record, the ticket being worked, and the model's cause and notes.
    """
    steps: list[Step] = state["steps"]
    requester, cause = state["requester"], state["cause"]
    ticket = _tickets().get(state["ticket_id"] or "")
    queue = tool_input.get("queue", "")
    sla = slas().get(queue)
    hours = sla_hours(sla) if sla else None
    submitted = _submitted(ticket, now or datetime.now(UTC))
    deadline = (
        None if hours is None else add_business_hours(submitted, hours).isoformat()
    )
    lookups = [step for step in steps if is_lookup(step) and step["ok"]]
    notes = state["notes"] or {}
    return {
        "requester": _requester(requester),
        "device": _device(requester),
        "queue": queue,
        "priority": tool_input.get("priority", ""),
        "sla": sla,
        "submitted_at": submitted.isoformat(),
        "deadline": deadline,
        "applications": list((ticket or {}).get("applications") or []),
        "checks": [
            {
                "step": step["input"].get("step"),
                "id": step["id"],
                "result": step["result"],
            }
            for step in lookups
            if step["tool"] == "run_check" and step.get("found")
        ],
        "similar": [
            found
            for step in lookups
            if step["tool"] == "find_similar_incidents"
            for found in step.get("found", [])
        ],
        "unknown": _unknown(steps, requester, cause, deadline),
        "cause": cause,
        "ruled_out": notes.get("ruled_out", ""),
        "next_step": notes.get("next_step", ""),
    }
