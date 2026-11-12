"""Builds what the loop's lookups read: `uv run -m evals.build_checks`.

Each imported ticket's diagnostic steps become recorded checks, by playbook step: what
was checked, what healthy looks like, what was seen and whether it passed. They stand
in for live systems, so the agent's `run_check` reads what the technician found then.
The summary, root cause, resolution and correspondence stay in data/evals, because
they hold the answer. Rules-set tickets have no recorded checks.

Similar incidents come from the knowledge base split only, the tickets the playbooks
were written from, with their cause and first resolution step. No other split's
outcome leaves data/evals.
"""

import json

from agent import config

INCIDENTS_FILE = config.EVALS_DIR / "incidents.json"
SPLITS_FILE = config.TICKETS_DIR / "splits.json"
TICKETS_FILE = config.TICKETS_DIR / "tickets.json"


def checks_of(incident: dict) -> list[dict]:
    """One ticket's checks, without the evidence notes or who ran them."""
    return [
        {
            "step": step["playbook_step_id"],
            "action": step["action"],
            "expected": step["expected_result"],
            "observed": step["observed_result"],
            "status": step["result_status"],
        }
        for step in incident["diagnostics"]["steps"]
    ]


def build_checks(incidents: list[dict]) -> dict[str, list[dict]]:
    return {incident["id"]: checks_of(incident) for incident in incidents}


def build_past_incidents(
    incidents: list[dict], tickets: list[dict], knowledge_base: list[str]
) -> list[dict]:
    """The knowledge base split's tickets as they arrived, and how each one ended."""
    allowed = set(knowledge_base)
    ended = {i["id"]: i for i in incidents if i["id"] in allowed}
    return [
        {
            "id": ticket["id"],
            "title": ticket["title"],
            "description": ticket["description"],
            "cause": ended[ticket["id"]]["root_cause"],
            "fixed_by": ended[ticket["id"]]["resolution"]["steps"][0],
        }
        for ticket in tickets
        if ticket["id"] in ended
    ]


def _write(path, content: dict | list) -> None:
    path.write_text(json.dumps(content, indent=1, ensure_ascii=False) + "\n")


def main() -> None:
    incidents = json.loads(INCIDENTS_FILE.read_text())
    checks = build_checks(incidents)
    _write(config.CHECKS_FILE, checks)
    print(f"{len(checks)} tickets, {sum(map(len, checks.values()))} checks")
    tickets = json.loads(TICKETS_FILE.read_text())
    knowledge_base = json.loads(SPLITS_FILE.read_text())["kb"]
    past = build_past_incidents(incidents, tickets, knowledge_base)
    _write(config.PAST_TICKETS_FILE, past)
    print(f"{len(past)} past incidents, from the knowledge base split")


if __name__ == "__main__":
    main()
