"""Business rules in code. The model proposes a decision, and these decide what stands.

Each rule is a pure function of the decision and the facts code holds: the requester's
record, what search found, and the mode. It returns the decision to use instead, with
the override recorded, or None when it has nothing to say. Both modes call `enforce`.
"""

from collections.abc import Callable
from typing import Literal, TypedDict

from agent.tool_schemas import ESCALATION_TOOL, SENSITIVE, TOOL_POLICY

Mode = Literal["assistant", "queue"]

LOCKOUT_LIMIT = 2  # SEC-04 §4.2: two or more lockouts in 24 hours
LOCKOUT_TOOL = "unlock_ad_account"
LOCKOUT_DOCS = {"account-lockout", "sec-04-account-lockout"}
SECURITY_QUEUE = "SEC-INCIDENT"
SECURITY_PRIORITY = "P2-High"
TECHNICIAN_QUEUE = "DESK-SUPPORT"
SUMMARY_CHARS = 150


class Proposal(TypedDict):
    """The parts of a decision a rule can change, as the graph's state holds them."""

    path: str
    tool_name: str | None
    tool_input: dict | None


class Override(TypedDict):
    rule: str
    reason: str
    proposed: Proposal
    code: str  # where the rule lives, for the page to name


def _escalation(queue: str, summary: str, priority: str) -> Proposal:
    return {
        "path": "ESCALATE",
        "tool_name": ESCALATION_TOOL,
        "tool_input": {
            "queue": queue,
            "summary": summary[:SUMMARY_CHARS],
            "priority": priority,
        },
    }


def is_lockout_ticket(decision: Proposal, retrieved: list[dict]) -> bool:
    """A lockout, by what code can see: the proposed unlock, or what search matched.

    The model's own cause isn't trusted here, so naming another cause can't skip SEC-04.
    """
    return decision["tool_name"] == LOCKOUT_TOOL or any(
        unit["doc"] in LOCKOUT_DOCS for unit in retrieved
    )


def sec04(
    decision: Proposal, requester: dict | None, retrieved: list[dict], mode: Mode
) -> tuple[Proposal, str] | None:
    """SEC-04 §4.2: 2+ lockouts in the records on a lockout ticket go to security."""
    lockouts = (requester or {}).get("lockouts_24h", 0)
    if lockouts < LOCKOUT_LIMIT or not is_lockout_ticket(decision, retrieved):
        return None
    queue = (decision["tool_input"] or {}).get("queue")
    if decision["path"] == "ESCALATE" and queue == SECURITY_QUEUE:
        return None
    reason = (
        f"{lockouts} lockouts in 24 hours in the records: a possible compromise under "
        "SEC-04 §4.2, never a routine unlock."
    )
    return _escalation(SECURITY_QUEUE, reason, SECURITY_PRIORITY), reason


def sensitive_fix(
    decision: Proposal, requester: dict | None, retrieved: list[dict], mode: Mode
) -> tuple[Proposal, str] | None:
    """In the Assistant, a sensitive fix needs a technician, so it becomes a ticket."""
    tool = decision["tool_name"]
    if mode != "assistant" or decision["path"] != "AUTO_FIX" or tool is None:
        return None
    if TOOL_POLICY.get(tool, {}).get("tier") != SENSITIVE:
        return None
    reason = f"{tool} is a sensitive fix, so a technician runs it, not the requester."
    summary = f"Proposed fix for a technician to run: {tool}."
    return _escalation(TECHNICIAN_QUEUE, summary, "P3-Normal"), reason


Rule = Callable[[Proposal, dict | None, list[dict], Mode], tuple[Proposal, str] | None]

# In order. The first rule that changes the decision decides it.
RULES: dict[str, Rule] = {"SEC-04": sec04, "Sensitive fix": sensitive_fix}

EXPLANATIONS = {
    "SEC-04": (
        "A requester with two or more lockouts in 24 hours in the records, on a "
        "lockout ticket, goes to SEC-INCIDENT at P2-High, whatever the model "
        "proposed. A lockout ticket is one where the model proposed an unlock or "
        "search matched the lockout playbook or policy. A count written only in the "
        "ticket is still the model's to read."
    ),
    "Sensitive fix": (
        "In the Assistant, a fix with the sensitive risk tier becomes a ticket to "
        "DESK-SUPPORT naming the fix, because the requester can't approve it. In the "
        "Queue a technician confirms every fix, so this rule changes nothing there."
    ),
}


def code_of(name: str) -> str:
    return f"{RULES[name].__name__} in agent/rules.py"


def enforce(
    decision: Proposal, requester: dict | None, retrieved: list[dict], mode: Mode
) -> tuple[Proposal, Override | None]:
    """The decision that stands, and the override if a rule changed it."""
    for name, rule in RULES.items():
        changed = rule(decision, requester, retrieved, mode)
        if changed is not None:
            proposal, reason = changed
            override: Override = {
                "rule": name,
                "reason": reason,
                "proposed": decision,
                "code": code_of(name),
            }
            return proposal, override
    return decision, None
