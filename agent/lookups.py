"""Four read-only lookups the loop may call. Each is a plain function, so they can be
served over MCP later unchanged.

Code, not the model, decides what each may read. The model never names a ticket or a
person: the graph passes the ticket being worked and its requester. A check reads that
ticket's recorded checks only, and similar incidents come from the knowledge base split
only, the tickets the playbooks were written from, as data/tickets/past_tickets.json
holds them. None of them changes anything.
"""

import json
import re
from functools import cache

from agent import config, records
from agent.retrieval import retrieve

SIMILAR_LIMIT = 3
SUMMARY_CHARS = 300
MIN_WORD = 4  # shorter words say little about what a ticket is about
# Common words that say nothing about what a ticket is about.
COMMON_WORDS = (
    "this that with from have been were when after before into what which their "
    "there they them about would could should also only still again cannot unable "
    "please corplabs"
)
STOPWORDS = frozenset(COMMON_WORDS.split())
PRIVATE_FIELDS = ("name", "email")


# ── Sources, read once ───────────────────────────────────────────────────────────
@cache
def _checks() -> dict[str, list[dict]]:
    return json.loads(config.CHECKS_FILE.read_text())


@cache
def _past() -> dict[str, dict]:
    """The knowledge base split's tickets and how they ended, and no others."""
    past = json.loads(config.PAST_TICKETS_FILE.read_text())
    return {incident["id"]: incident for incident in past}


def _words(text: str) -> frozenset[str]:
    found = re.findall(r"[a-z0-9][a-z0-9.\-]+", text.lower())
    return frozenset(w for w in found if len(w) >= MIN_WORD and w not in STOPWORDS)


@cache
def _incident_words() -> dict[str, frozenset[str]]:
    return {
        ticket_id: _words(f"{incident['title']} {incident['description']}")
        for ticket_id, incident in sorted(_past().items())
    }


def _clip(text: str) -> str:
    return text if len(text) <= SUMMARY_CHARS else text[: SUMMARY_CHARS - 1] + "…"


# ── The lookups ──────────────────────────────────────────────────────────────────
def search_kb(query: str) -> list[dict]:
    """The playbook sections and policies closest to the query, as triage sees them."""
    return [
        {
            "doc": unit["doc"],
            "section": unit["section"],
            "score": round(unit["score"], 2),
            "text": unit["text"],
        }
        for unit in retrieve(query)
    ]


def lookup_requester(user_id: str | None) -> dict:
    """The requester's record, with their lockouts and recent tickets, but no name or
    email. An unknown or missing requester is said so, not guessed."""
    if user_id is None:
        return {"found": False, "reason": "No requester is named on this ticket."}
    record = records.users().get(user_id)
    if record is None:
        return {"found": False, "reason": f"No staff record for {user_id}."}
    return {"found": True} | {
        key: value for key, value in record.items() if key not in PRIVATE_FIELDS
    }


def find_similar_incidents(query: str, limit: int = SIMILAR_LIMIT) -> list[dict]:
    """Closed knowledge base split tickets that share the most words with the query,
    with how each one ended. A plain local search, until Qdrant holds incidents."""
    wanted = _words(query)
    scored = []
    for ticket_id, words in _incident_words().items():
        shared = len(wanted & words)
        if shared:
            scored.append((shared / len(wanted | words), ticket_id))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    past = _past()
    return [
        {
            "id": ticket_id,
            "title": past[ticket_id]["title"],
            "similarity": round(score, 2),
            "cause": _clip(past[ticket_id]["cause"]),
            "fixed_by": _clip(past[ticket_id]["fixed_by"]),
        }
        for score, ticket_id in scored[:limit]
    ]


def run_check(ticket_id: str | None, step: str) -> dict:
    """One recorded check on the ticket being worked, by its playbook step id. A step
    the ticket has no record of returns no result."""
    for check in _checks().get(ticket_id or "", []):
        if check["step"] == step:
            return {"found": True} | check
    return {"found": False, "reason": f"No recorded result for {step} on this ticket."}
