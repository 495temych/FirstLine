"""Gives each ticket one named cause: `uv run -m evals.label_tickets`.

data/evals/causes.json lists each family's causes, with what a good first pass does
for each one. The rules there were written on the knowledge base split. A ticket
takes the cause its `root_cause` names first, because the records usually lead with
the main cause. SEC-04 then overrides lockout tickets, from the requester's record.
"""

import json
import re

from agent import config
from evals.import_tickets import family_of

CAUSES_FILE = config.EVALS_DIR / "causes.json"
LABELS_FILE = config.EVALS_DIR / "cause_labels.json"
ANY_FAMILY = "*"
LOCKOUT_FAMILY = "ALP"
REPEAT_LOCKOUTS = 2
SEC_04_QUEUE = "SEC-INCIDENT"


def load_causes() -> list[dict]:
    return json.loads(CAUSES_FILE.read_text())


def _first_position(patterns: list[str], text: str) -> int | None:
    """Where any of these patterns first appears in the text, or None."""
    found = [re.search(p, text, re.IGNORECASE) for p in patterns]
    positions = [m.start() for m in found if m]
    return min(positions) if positions else None


def _named_first(causes: list[dict], key: str, text: str) -> dict | None:
    """The cause these patterns name earliest. Ties go to the first listed."""
    named = [
        (position, index, cause)
        for index, cause in enumerate(causes)
        if (position := _first_position(cause[key], text)) is not None
    ]
    return min(named, key=lambda n: n[:2])[2] if named else None


def name_cause(family: str, root_cause: str, causes: list[dict]) -> dict | None:
    """The family's cause named first, with vaguer wording only as a last resort."""
    everywhere = [c for c in causes if c["family"] == ANY_FAMILY]
    own = [c for c in causes if c["family"] == family]
    return (
        _named_first(everywhere, "match", root_cause)
        or _named_first(own, "match", root_cause)
        or _named_first(own, "otherwise", root_cause)
    )


def label(ticket_id: str, cause: dict, lockouts: int) -> dict:
    """What a good first pass does for this ticket."""
    answer = {
        "id": ticket_id,
        "cause": cause["id"],
        "paths": cause["paths"],
        "tools": cause["tools"],
        "queues": cause["queues"],
        "checks": cause["checks"],
    }
    if family_of(ticket_id) == LOCKOUT_FAMILY and lockouts >= REPEAT_LOCKOUTS:
        return {
            **answer,
            "paths": ["ESCALATE"],
            "tools": [],
            "queues": [SEC_04_QUEUE],
            "sec_04": True,
        }
    return answer


def build_labels(
    incidents: list[dict], tickets: list[dict], users: list[dict], causes: list[dict]
) -> tuple[list[dict], list[str]]:
    """Label every ticket, and return the ids no rule could name."""
    lockouts = {u["id"]: u["lockouts_24h"] for u in users}
    requesters = {t["id"]: t["requester"] for t in tickets}
    labels, unnamed = [], []
    for incident in incidents:
        ticket_id = incident["id"]
        cause = name_cause(family_of(ticket_id), incident["root_cause"], causes)
        if cause is None:
            unnamed.append(ticket_id)
            continue
        labels.append(label(ticket_id, cause, lockouts[requesters[ticket_id]]))
    return labels, unnamed


def main() -> None:
    incidents = json.loads((config.EVALS_DIR / "incidents.json").read_text())
    tickets = json.loads((config.TICKETS_DIR / "tickets.json").read_text())
    users = json.loads(config.USERS_FILE.read_text())
    labels, unnamed = build_labels(incidents, tickets, users, load_causes())
    text = json.dumps(labels, indent=1, ensure_ascii=False)
    LABELS_FILE.write_text(text + "\n")
    print(f"{len(labels)} tickets labelled, {len(unnamed)} unnamed")


if __name__ == "__main__":
    main()
