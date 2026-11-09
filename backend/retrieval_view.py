"""The Retrieval page: how well the knowledge base search finds the right playbook.

It reads the saved retrieval scores, which keep each ticket's ranked playbooks, and
runs a search on any text the reader types. Search embeds the text on this machine
and asks the index, so it calls no model and costs nothing.
"""

import json
from functools import cache
from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, StringConstraints

from agent import config, retrieval
from evals import retrieval_score, runner

SHOWN_SETS = runner.REVIEW_SPLITS  # never the held-out sets, whose tickets stay unread

QUESTIONS = {
    "hit_rate": "When a family has a playbook, is it the one found?",
    "mean_reciprocal_rank": "How high does the right playbook rank?",
    "recall": f"Is the right playbook in the first {retrieval_score.RECALL_AT}?",
    "false_match_rate": "When a family has no playbook, does search stay quiet?",
}
FLOORS = {"hit_rate": retrieval_score.HIT_RATE_FLOOR}  # what `poe check` enforces


@cache
def _titles() -> dict[str, str]:
    tickets = json.loads((config.TICKETS_DIR / "tickets.json").read_text())
    return {t["id"]: t["title"] for t in tickets}


def _latest(runs: list[dict], name: str) -> dict | None:
    """The newest score of a set that kept its tickets, with their titles."""
    run = next((r for r in runs if r["set"] == name and r.get("tickets")), None)
    if run is None:
        return None
    titles = _titles()
    tickets = [{**t, "title": titles[t["id"]]} for t in run["tickets"]]
    return {**run, "tickets": tickets}


def _history(runs: list[dict]) -> list[dict]:
    """Every saved score's headline, oldest first, so a reader sees how it moved."""
    return [
        {
            "id": r["id"],
            "date": r["date"],
            "set": r["set"],
            "kb_version": r["kb_version"],
            "summary": r["summary"],
        }
        for r in reversed(runs)
        if r["set"] in SHOWN_SETS
    ]


def _decision() -> dict:
    """Path accuracy on the development set, with search and without it."""
    runs = [r for r in runner.default_runs() if r["set"] == "dev"]

    def newest(searched: bool) -> dict | None:
        run = next((r for r in runs if r.get("use_retrieval", True) is searched), None)
        if run is None:
            return None
        s = run["summary"]
        return {
            "run": run["id"],
            "n": s["n"],
            "path_accuracy": s["path_accuracy"],
            "path_margin": s["path_margin"],
            "cost_per_ticket_chf": s["cost_per_ticket_chf"],
        }

    return {"with_search": newest(True), "without_search": newest(False)}


router = APIRouter()


@router.get("/api/retrieval", operation_id="read_retrieval")
def read_retrieval() -> dict:
    """The latest retrieval scores, how they moved, and the rules a match follows."""
    runs = retrieval_score.load_runs()
    return {
        "sets": {name: _latest(runs, name) for name in SHOWN_SETS},
        "history": _history(runs),
        "questions": QUESTIONS,
        "floors": FLOORS,
        "rule": {
            "sure": retrieval.PLAYBOOK_SURE,
            "threshold": retrieval.PLAYBOOK_THRESHOLD,
            "margin": retrieval.PLAYBOOK_MARGIN,
            "support": retrieval.SUPPORT_THRESHOLD,
            "top_k": retrieval.TOP_K,
        },
        "embedding_model": retrieval.EMBEDDING_MODEL,
        "kb_version": retrieval.kb_version(),
        "decision": _decision(),
    }


class Search(BaseModel):
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]


@router.post("/api/retrieval/search", operation_id="search_knowledge_base")
def search(body: Search) -> dict:
    """Rank the knowledge base for any text, and say what the agent would be given."""
    ranked = retrieval.rank_playbooks(body.text)
    given = retrieval.retrieve(body.text)
    best = ranked[0]["score"] if ranked else None
    runner_up = ranked[1]["score"] if len(ranked) > 1 else -1.0
    return {
        "ranked": ranked,
        "why": None if best is None else retrieval.why_matched(best, runner_up),
        "given": [
            {
                "doc": r["doc"],
                "kind": r["kind"],
                "section": r["section"],
                "score": r["score"],
                "highlights": r["highlights"],
            }
            for r in given
        ],
    }
