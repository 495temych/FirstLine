"""Scores retrieval on the imported tickets. It calls no chat model, so it's free.

A family with a playbook should find it. A family without one should find nothing.
"""

import json
from datetime import UTC, datetime

from agent import config, retrieval
from evals.import_tickets import family_of

RUNS_DIR = config.EVALS_DIR / "retrieval"
DEFAULT_SPLITS = ("dev", "unseen_dev")
SPLITS = ("kb", "dev", "held_out", "unseen_dev", "unseen_held_out")
RECALL_AT = 2
HIT_RATE_FLOOR = 0.95


def load_split(name: str) -> list[dict]:
    """The tickets in a set, in id order."""
    tickets = json.loads((config.TICKETS_DIR / "tickets.json").read_text())
    members = set(json.loads((config.TICKETS_DIR / "splits.json").read_text())[name])
    return [t for t in tickets if t["id"] in members]


def load_families() -> dict[str, dict]:
    """Each family's name, and the document that should answer it, if any."""
    return json.loads((config.EVALS_DIR / "families.json").read_text())


def _rank_of(expected_doc: str | None, ranked: list[dict]) -> int | None:
    docs = [r["doc"] for r in ranked]
    return docs.index(expected_doc) + 1 if expected_doc in docs else None


def score_ticket(
    ticket: dict, expected_doc: str | None, retrieved: list[dict], ranked: list[dict]
) -> dict:
    """Score the playbook returned against the one the family should find."""
    top = next((r for r in retrieved if r["kind"] == "playbook"), None)
    doc = top["doc"] if top else None
    return {
        "id": ticket["id"],
        "family": family_of(ticket["id"]),
        "expected": expected_doc,
        "top": doc,
        "score": top["score"] if top else None,
        "hit": expected_doc is not None and doc == expected_doc,
        "false_match": expected_doc is None and doc is not None,
        "rank": _rank_of(expected_doc, ranked),
    }


def _rate(matched: list[dict], key: str) -> float | None:
    return sum(r[key] for r in matched) / len(matched) if matched else None


def _reciprocal_rank(rows: list[dict]) -> float | None:
    """How high the right playbook ranks: 1 is first, 0.5 is second, and so on."""
    if not rows:
        return None
    return sum(1 / r["rank"] for r in rows if r["rank"]) / len(rows)


def _recall(rows: list[dict]) -> float | None:
    """How often the right playbook is in the first RECALL_AT."""
    if not rows:
        return None
    return sum(bool(r["rank"]) and r["rank"] <= RECALL_AT for r in rows) / len(rows)


def summarize(rows: list[dict]) -> dict:
    """Hit rate on families we cover, and false matches on families we don't."""
    covered = [r for r in rows if r["expected"] is not None]
    uncovered = [r for r in rows if r["expected"] is None]
    return {
        "n": len(rows),
        "covered": len(covered),
        "uncovered": len(uncovered),
        "hit_rate": _rate(covered, "hit"),
        "mean_reciprocal_rank": _reciprocal_rank(covered),
        "recall": _recall(covered),
        "false_match_rate": _rate(uncovered, "false_match"),
    }


def by_family(rows: list[dict], families: dict[str, dict]) -> dict[str, dict]:
    """The same measures for each family, with its name and expected document."""
    present = sorted({r["family"] for r in rows})
    return {
        family: {
            **summarize([r for r in rows if r["family"] == family]),
            **families[family],
        }
        for family in present
    }


def kb_version() -> str:
    """A short hash of the knowledge base, so runs can be compared."""
    return retrieval.kb_version()


def evaluate(name: str) -> dict:
    """Score one set."""
    families = load_families()
    rows = []
    for ticket in load_split(name):
        query = f"{ticket['title']}\n\n{ticket['description']}"
        expected = families[family_of(ticket["id"])]["doc"]
        rows.append(
            score_ticket(
                ticket,
                expected,
                retrieval.retrieve(query),
                retrieval.rank_playbooks(query),
            )
        )
    now = datetime.now(UTC)
    return {
        "id": f"{now:%Y%m%dT%H%M%S}-retrieval-{name}",
        "date": now.isoformat(timespec="seconds"),
        "set": name,
        "kb_version": kb_version(),
        "sure": retrieval.PLAYBOOK_SURE,
        "threshold": retrieval.PLAYBOOK_THRESHOLD,
        "margin": retrieval.PLAYBOOK_MARGIN,
        "top_k": retrieval.TOP_K,
        "summary": summarize(rows),
        "by_family": by_family(rows, families),
    }


def save_run(run: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(run, indent=2, ensure_ascii=False)
    (RUNS_DIR / f"{run['id']}.json").write_text(text + "\n")


def load_runs() -> list[dict]:
    """Saved retrieval scores, newest first."""
    paths = sorted(RUNS_DIR.glob("*.json"), reverse=True)
    return [json.loads(p.read_text()) for p in paths]


def _percent(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate:.0%}"


def print_report(run: dict) -> None:
    s = run["summary"]
    print(
        f"{run['set']}: {s['n']} tickets, knowledge base {run['kb_version']}, "
        f"hit rate {_percent(s['hit_rate'])} of {s['covered']}, "
        f"MRR {_percent(s['mean_reciprocal_rank'])}, recall {_percent(s['recall'])}, "
        f"false matches {_percent(s['false_match_rate'])} of {s['uncovered']}"
    )
    for family, f in run["by_family"].items():
        print(
            f"  {family}  {f['name']:<30} "
            f"hit {_percent(f['hit_rate']):>4}  "
            f"false {_percent(f['false_match_rate']):>4}"
        )


def main(names: list[str] | None, save: bool) -> None:
    """Score each set and print it, saving the runs if asked.

    It fails if a set's hit rate is under the floor, so `poe check` catches a drop.
    """
    too_low = []
    for name in names or DEFAULT_SPLITS:
        run = evaluate(name)
        print_report(run)
        if save:
            save_run(run)
        hit_rate = run["summary"]["hit_rate"]
        if hit_rate is not None and hit_rate < HIT_RATE_FLOOR:
            too_low.append(name)
    if too_low:
        raise SystemExit(f"Hit rate is under {HIT_RATE_FLOOR:.0%} on {too_low}")
