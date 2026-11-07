"""Imports the closed incidents and splits them: `uv run -m evals.import_tickets`.

What a technician sees when a ticket arrives goes to data/tickets/. Everything found
out later goes to data/evals/, because it holds the answers. See data/tickets/SOURCE.md.
"""

import csv
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from agent import config

SEED = "firstline-splits-1"
UNSEEN_FAMILIES = {"AIT", "CES"}
KNOWLEDGE_BASE_SHARE = 0.6
DEVELOPMENT_SHARE = 0.2
CSV_FIELD_LIMIT = 10_000_000


def family_of(ticket_id: str) -> str:
    """The issue family in an id, so INC-ALP-0001 is ALP."""
    return ticket_id.split("-")[1]


def split_record(row: dict) -> tuple[dict, dict]:
    """Separate a source row into the ticket as it arrived and what came after."""
    submitted = json.loads(row["ticket"])
    ticket = {
        "id": row["record_id"],
        "submitted_at": submitted["submitted_at"],
        "title": submitted["submitted_title"],
        "description": submitted["submitted_description"],
        "priority": submitted["priority"],
        "sla_plan": submitted["sla_plan"],
        "environment": submitted["environment"],
        "applications": submitted["applications"],
    }
    incident = {
        "id": row["record_id"],
        "correspondence": json.loads(row["correspondence"]),
        "diagnostics": json.loads(row["diagnostics"]),
        "root_cause": row["root_cause"],
        "resolution": json.loads(row["resolution"]),
    }
    return ticket, incident


def _shuffled(ids: Iterable[str]) -> list[str]:
    """A fixed order that doesn't depend on Python's random number generator."""
    return sorted(ids, key=lambda i: hashlib.sha256(f"{SEED}:{i}".encode()).hexdigest())


def split_ids(ids: Iterable[str]) -> dict[str, list[str]]:
    """Split each family evenly, keeping unseen families out of the knowledge base.

    Unseen families are halved too, so tuning on one half leaves the other as the exam.
    """
    families = defaultdict(list)
    for ticket_id in ids:
        families[family_of(ticket_id)].append(ticket_id)

    sets = defaultdict(list)
    for family, members in families.items():
        ordered = _shuffled(members)
        size = len(ordered)
        if family in UNSEEN_FAMILIES:
            sets["unseen_dev"] += ordered[: size // 2]
            sets["unseen_held_out"] += ordered[size // 2 :]
            continue
        knowledge_base = round(size * KNOWLEDGE_BASE_SHARE)
        development = knowledge_base + round(size * DEVELOPMENT_SHARE)
        sets["kb"] += ordered[:knowledge_base]
        sets["dev"] += ordered[knowledge_base:development]
        sets["held_out"] += ordered[development:]
    return {name: sorted(members) for name, members in sorted(sets.items())}


def _write(path: Path, content: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n")


def import_tickets(source: Path, tickets_dir: Path, evals_dir: Path) -> None:
    """Write the tickets, the incident answers and the splits."""
    csv.field_size_limit(CSV_FIELD_LIMIT)
    with source.open(newline="") as file:
        records = [split_record(row) for row in csv.DictReader(file)]
    tickets = [ticket for ticket, _ in records]
    _write(tickets_dir / "tickets.json", tickets)
    _write(evals_dir / "incidents.json", [incident for _, incident in records])
    _write(tickets_dir / "splits.json", split_ids(t["id"] for t in tickets))


if __name__ == "__main__":
    import_tickets(config.TICKET_SOURCE, config.TICKETS_DIR, config.EVALS_DIR)
