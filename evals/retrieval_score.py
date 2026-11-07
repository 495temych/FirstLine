"""Scores retrieval on the imported tickets. It calls no chat model, so it's free.

A family with a playbook should find it. A family without one should find nothing.
"""

import hashlib
import json
from datetime import UTC, datetime

from agent import config, retrieval
from evals.import_tickets import family_of

RUNS_DIR = config.EVALS_DIR / "retrieval"
DEFAULT_SPLITS = ("dev", "unseen_dev")
SPLITS = ("kb", "dev", "held_out", "unseen_dev", "unseen_held_out")


def load_split(name: str) -> list[dict]:
    """The tickets in a set, in id order."""
    tickets = json.loads((config.TICKETS_DIR / "tickets.json").read_text())
    members = set(json.loads((config.TICKETS_DIR / "splits.json").read_text())[name])
    return [t for t in tickets if t["id"] in members]


def load_families() -> dict[str, dict]:
    """Each family's name, and the document that should answer it, if any."""
    return json.loads((config.EVALS_DIR / "families.json").read_text())


def score_ticket(ticket: dict, expected_doc: str | None, retrieved: list[dict]) -> dict:
    """Score the top match against the document the family should find."""
    top = retrieved[0] if retrieved else None
    doc = top["doc"] if top else None
    return {
        "id": ticket["id"],
        "family": family_of(ticket["id"]),
        "expected": expected_doc,
        "top": doc,
        "score": top["score"] if top else None,
        "hit": expected_doc is not None and doc == expected_doc,
        "false_match": expected_doc is None and doc is not None,
    }


def _rate(matched: list[dict], key: str) -> float | None:
    return sum(r[key] for r in matched) / len(matched) if matched else None


def summarize(rows: list[dict]) -> dict:
    """Hit rate on families we cover, and false matches on families we don't."""
    covered = [r for r in rows if r["expected"] is not None]
    uncovered = [r for r in rows if r["expected"] is None]
    return {
        "n": len(rows),
        "covered": len(covered),
        "uncovered": len(uncovered),
        "hit_rate": _rate(covered, "hit"),
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
    digest = hashlib.sha256()
    for path in sorted(config.KB_DIR.rglob("*.md")):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:8]


def evaluate(name: str) -> dict:
    """Score one set."""
    families = load_families()
    rows = [
        score_ticket(
            ticket,
            families[family_of(ticket["id"])]["doc"],
            retrieval.retrieve(f"{ticket['title']}\n\n{ticket['description']}"),
        )
        for ticket in load_split(name)
    ]
    now = datetime.now(UTC)
    return {
        "id": f"{now:%Y%m%dT%H%M%S}-retrieval-{name}",
        "date": now.isoformat(timespec="seconds"),
        "set": name,
        "kb_version": kb_version(),
        "threshold": retrieval.SIMILARITY_THRESHOLD,
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
        f"false matches {_percent(s['false_match_rate'])} of {s['uncovered']}"
    )
    for family, f in run["by_family"].items():
        print(
            f"  {family}  {f['name']:<30} "
            f"hit {_percent(f['hit_rate']):>4}  "
            f"false {_percent(f['false_match_rate']):>4}"
        )


def main(names: list[str] | None, save: bool) -> None:
    """Score each set and print it, saving the runs if asked."""
    for name in names or DEFAULT_SPLITS:
        run = evaluate(name)
        print_report(run)
        if save:
            save_run(run)
