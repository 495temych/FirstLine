"""Imports the closed incidents and splits them: `uv run -m evals.import_tickets`.

What a technician sees when a ticket arrives goes to data/tickets/. Everything found
out later goes to data/evals/, because it holds the answers. Staff records go to
data/records/, with invented details added. See data/tickets/SOURCE.md.
"""

import csv
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from agent import config

SEED = "firstline-splits-1"
UNSEEN_FAMILIES = {"AIT", "CES"}
KNOWLEDGE_BASE_SHARE = 0.6
DEVELOPMENT_SHARE = 0.2
CSV_FIELD_LIMIT = 10_000_000
DEPARTMENTS = ("Sales", "Finance", "Engineering", "Marketing", "Operations", "Legal")
OFFICES = (
    "Zürich",
    "Charlotte",
    "Portland",
    "Arlington",
    "Frankfurt",
    "Munich",
    "Milan",
)
DEVICE_MODELS = ("Dell Latitude 5440", "ThinkPad T14 Gen 4", "HP EliteBook 840")
REPEAT_LOCKOUT_PERCENT = 2
ONE_LOCKOUT_PERCENT = 6


def family_of(ticket_id: str) -> str:
    """The issue family in an id, so INC-ALP-0001 is ALP."""
    return ticket_id.split("-")[1]


def find_requester(text: str, pii: list[dict], directory: list[dict]) -> str | None:
    """Who raised a ticket: the account named first in its text, if there is one.

    A ticketing system knows this on arrival, but the source has no such column.
    """
    usernames = {u["username"] for u in directory}
    names = {u["display_name"]: u["username"] for u in directory}
    named = {v: v for v in usernames} | names
    values = [p["value"] for p in pii if p["value"] in named]
    arrived = [v for v in values if v in text]
    if arrived:
        return named[min(arrived, key=text.index)]
    return named[values[0]] if values else None


def split_record(row: dict, requester: str | None = None) -> tuple[dict, dict]:
    """Separate a source row into the ticket as it arrived and what came after."""
    submitted = json.loads(row["ticket"])
    ticket = {
        "id": row["record_id"],
        "requester": requester,
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


def _pick(username: str, field: str, size: int) -> int:
    """A fixed number below size for one person and one invented field."""
    digest = hashlib.sha256(f"{SEED}:{username}:{field}".encode()).hexdigest()
    return int(digest, 16) % size


def _lockouts(username: str) -> int:
    roll = _pick(username, "lockouts", 100)
    if roll < REPEAT_LOCKOUT_PERCENT:
        return 2
    return 1 if roll < REPEAT_LOCKOUT_PERCENT + ONE_LOCKOUT_PERCENT else 0


def _lockout_history(count: int) -> list[str]:
    return [
        f"Account lockout, {n} of {count} in the last 24 hours"
        for n in range(1, count + 1)
    ]


def invent_record(person: dict, department: str | None) -> dict:
    """A directory account, plus invented details that stay the same on every run."""
    username = person["username"]
    lockouts = _lockouts(username)
    team = department or DEPARTMENTS[_pick(username, "department", len(DEPARTMENTS))]
    return {
        "id": username,
        "name": person["display_name"],
        "email": person["email"],
        "department": team,
        "office": OFFICES[_pick(username, "office", len(OFFICES))],
        "floor": 3 + _pick(username, "floor", 5),
        "lockouts_24h": lockouts,
        "device": {
            "id": f"LT-{username.replace('.', '').upper()}",
            "model": DEVICE_MODELS[_pick(username, "model", len(DEVICE_MODELS))],
            "image": "2026-06",
            "age_years": _pick(username, "age", 5),
            "battery_health": 60 + _pick(username, "battery", 40),
            "dock": "WD22TB4",
        },
        "groups": [f"CORPLABS\\{team}-Users"],
        "recent_tickets": _lockout_history(lockouts),
    }


def build_records(
    directory: list[dict], tickets: list[dict], rules_users: list[dict]
) -> list[dict]:
    """The directory with invented details, then the rules set's hand-written users.

    The source repeats 88 usernames for different people. A username is unique in a
    real directory, so the first person with each one keeps it.
    """
    people = {}
    for person in directory:
        people.setdefault(person["username"], person)
    seen = defaultdict(Counter)
    for ticket in tickets:
        group = ticket["environment"].get("user_group")
        if ticket["requester"] and group in DEPARTMENTS:
            seen[ticket["requester"]][group] += 1
    records = [
        invent_record(
            person,
            seen[person["username"]].most_common(1)[0][0]
            if seen[person["username"]]
            else None,
        )
        for person in people.values()
    ]
    return records + [{"office": "Zürich", **user} for user in rules_users]


def _read_records(source_dir: Path, directory: list[dict]) -> list[tuple[dict, dict]]:
    pii = {
        p["ticket_id"]: p["pii_instances"]
        for p in json.loads((source_dir / "pii.json").read_text())
    }
    csv.field_size_limit(CSV_FIELD_LIMIT)
    with (source_dir / "itsm_ticket_corpus_flat.csv").open(newline="") as file:
        return [
            split_record(
                row,
                find_requester(
                    json.loads(row["ticket"])["submitted_description"],
                    pii[row["record_id"]],
                    directory,
                ),
            )
            for row in csv.DictReader(file)
        ]


def import_tickets(
    source_dir: Path, tickets_dir: Path, evals_dir: Path, users_file: Path
) -> None:
    """Write the tickets, the incident answers, the splits and the staff records."""
    directory = json.loads((source_dir / "users_directory.json").read_text())["users"]
    records = _read_records(source_dir, directory)
    tickets = [ticket for ticket, _ in records]
    usernames = {u["username"] for u in directory}
    rules_users = [
        u for u in json.loads(users_file.read_text()) if u["id"] not in usernames
    ]
    _write(tickets_dir / "tickets.json", tickets)
    _write(evals_dir / "incidents.json", [incident for _, incident in records])
    _write(tickets_dir / "splits.json", split_ids(t["id"] for t in tickets))
    _write(users_file, build_records(directory, tickets, rules_users))


if __name__ == "__main__":
    import_tickets(
        config.SOURCE_DIR, config.TICKETS_DIR, config.EVALS_DIR, config.USERS_FILE
    )
