"""What each group of the dashboard shows, in two or three findings, for its opening.

The dashboard has three groups: Try it, Is it worth it? and How it works. Each opens
with its question and findings built here from what the other views already compute:
the graph's gates, the Queue's reviews, the business case, the benchmark, the saved
retrieval scores and the labels. Nothing calls a model, and nothing is typed in that
the code or a saved run doesn't hold.
"""

from fastapi import APIRouter

from agent import config
from agent.models import label
from backend import benchmark, economics, overview, queue_board
from evals import retrieval_score, runner, yardsticks

QUESTIONS = {
    "try": "What does it do?",
    "worth": "Does it pay, and on which model?",
    "how": "Why does it decide that, and how do we know?",
}


def _francs(amount: float) -> str:
    sign = "-" if amount < 0 else ""
    return f"{sign}CHF {abs(amount):,.2f}".replace(",", "'")


def _saves(amount: float) -> str:
    return f"saves {_francs(amount)}" if amount >= 0 else f"loses {_francs(-amount)}"


def _finding(text: str, source: str, view: str, n: int | None = None) -> dict:
    """One claim, the evidence behind it, and the view that shows it in full."""
    return {"text": text, "n": n, "source": source, "view": view}


def _try_it() -> list[dict]:
    gates = sum(bool(s.get("gate")) for s in overview.STATIONS.values())
    out = [
        _finding(
            "The model proposes and a person decides: nothing runs until one of"
            f" {gates} human gates says yes.",
            "agent/graph.py",
            "queue",
        )
    ]
    seen = economics.observed(queue_board.board.view()["tickets"])
    if seen is None:
        out.append(
            _finding(
                "No Queue reviews yet. Load a batch and review it to measure how"
                " long a technician takes.",
                "the Queue's reviews",
                "queue",
            )
        )
    else:
        out.append(
            _finding(
                f"Technicians approved {seen['share']:.0%} of {seen['n']} reviewed"
                f" decisions unchanged, in {seen['review_minutes']:.1f} minutes each"
                " on average.",
                "the Queue's reviews",
                "queue",
                seen["n"],
            )
        )
    return out


def _worth_it(view: dict) -> list[dict]:
    out = []
    model = label(config.model_name())
    case = economics.projected()
    if case is None:
        out.append(
            _finding(
                f"{model} has no development run yet, so nothing is projected.",
                "data/evals/runs/",
                "money",
            )
        )
    else:
        needed = case["catch_needed"]
        pays = f" It pays only above {needed:.0%} caught." if needed else ""
        out.append(
            _finding(
                f"On {model}, the default, each ticket {_saves(case['net_chf'])}"
                f" net if technicians catch {case['catch_rate']:.0%} of wrong"
                f" decisions.{pays}",
                case["source"],
                "money",
                case["n"],
            )
        )
    dev = [
        e
        for e in view["sets"][benchmark.MAIN_SET]["entries"]
        if e["kind"] == "model" and not e["sample"]
    ]
    if dev:
        best = max(dev, key=lambda e: e["net_chf"])
        close = [e for e in dev if e["net_chf"] >= best["net_low"]]
        cheap = min(close, key=lambda e: e["cost_chf"] or 0.0)
        low = min(e["net_chf"] for e in close)
        out.append(
            _finding(
                f"{len(close)} of {len(dev)} models save {_francs(low)} to"
                f" {_francs(best['net_chf'])} a ticket, within one margin of the best."
                f" The cheapest of them is {cheap['label']}.",
                best["source"],
                "models",
                best["n"],
            )
        )
    classifier = {
        name: next(
            (e for e in view["sets"][name]["entries"] if e["model"] == "classifier"),
            None,
        )
        for name in ("dev", "unseen_dev")
    }
    unseen = [e for e in view["sets"]["unseen_dev"]["entries"] if e["kind"] == "model"]
    if classifier["dev"] and classifier["unseen_dev"] and unseen:
        top = max(unseen, key=lambda e: e["net_chf"])
        out.append(
            _finding(
                f"The free classifier {_saves(classifier['dev']['net_chf'])} a ticket"
                " on development, more than any model, but"
                f" {_saves(classifier['unseen_dev']['net_chf'])} on families with no"
                f" playbook, where {top['label']} {_saves(top['net_chf'])}.",
                classifier["unseen_dev"]["source"],
                "models",
                top["n"],
            )
        )
    return out


def _how_it_works() -> list[dict]:
    out = []
    scores = retrieval_score.load_runs()
    dev = next((r for r in scores if r["set"] == "dev"), None)
    unseen = next((r for r in scores if r["set"] == "unseen_dev"), None)
    if dev and unseen:
        hit = dev["summary"]["hit_rate"] or 0.0
        false = unseen["summary"]["false_match_rate"] or 0.0
        out.append(
            _finding(
                f"Search finds the right playbook for {hit:.0%} of"
                f" {dev['summary']['n']} development tickets, and wrongly matches one"
                f" for {false:.0%} of {unseen['summary']['n']} tickets from families"
                " with no playbook.",
                dev["id"],
                "retrieval",
                dev["summary"]["n"],
            )
        )
    run = next((r for r in runner.default_runs() if r["set"] == "dev"), None)
    if run:
        s, y = run["summary"], run["yardsticks"]["classifier"]
        out.append(
            _finding(
                f"{label(run['model'])} chooses the right path for"
                f" {s['path_accuracy']:.0%} ±{s['path_margin']:.0%} of {s['n']}"
                f" development tickets, against {y['path_accuracy']:.0%} for the"
                " classifier.",
                run["id"],
                "evaluations",
                s["n"],
            )
        )
    pairs = runner.load_imported("dev")
    if pairs:
        out.append(
            _finding(
                f"The family alone gives the expected answer for"
                f" {yardsticks.family_decides(pairs)} of {len(pairs)} development"
                " tickets,"
                " because each label comes from its cause. That's why a classifier"
                " trained on the same families does well there.",
                yardsticks.LABELS_SOURCE,
                "tickets",
                len(pairs),
            )
        )
    return out


def groups() -> dict:
    view = benchmark.view()
    findings = {"try": _try_it(), "worth": _worth_it(view), "how": _how_it_works()}
    return {
        key: {"question": QUESTIONS[key], "findings": findings[key]}
        for key in QUESTIONS
    }


router = APIRouter()


@router.get("/api/insights", operation_id="read_insights")
def read_insights() -> dict:
    """What each group of the dashboard shows, as two or three findings with their
    evidence, built from saved runs and the Queue's reviews.
    """
    return groups()
