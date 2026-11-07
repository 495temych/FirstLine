"""Runs the agent over a labelled set, scores it and saves the result.

`uv run -m evals` runs the rules set. `--set` picks another set, such as `dev` or
`unseen_dev`, and `--tiny` runs only the rules set's five trial tickets. Each run also
scores the two yardsticks, for free. Results go to data/evals/runs/.
`--retrieval` scores retrieval instead, with no model calls.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime

from agent import config, run_triage
from agent.decision import DECISION_TOOL
from agent.tool_schemas import TOOL_POLICY, TOOLS
from evals import retrieval_score, scoring, yardsticks

EVALS_DIR = config.ROOT / "data" / "evals"
RUNS_DIR = EVALS_DIR / "runs"
PREFIXES = {"rules": "rules_", "rules_held_out": "rules_held_out_"}
IMPORTED_SETS = ("dev", "held_out", "unseen_dev", "unseen_held_out")
REVIEW_SPLITS = ("dev", "unseen_dev")  # the imported tickets a person may read


def load_set(name: str, tiny: bool = False) -> list[tuple[dict, dict]]:
    """Return (ticket, answer) pairs. Only this module opens the answers."""
    prefix = PREFIXES[name]
    tickets = json.loads((EVALS_DIR / f"{prefix}tickets.json").read_text())
    answers = json.loads((EVALS_DIR / f"{prefix}answers.json").read_text())
    by_id = {a["id"]: a for a in answers}
    pairs = [(t, by_id[t["id"]]) for t in tickets]
    return [(t, a) for t, a in pairs if a["tiny"]] if tiny else pairs


def load_imported(split: str) -> list[tuple[dict, dict]]:
    """Return (ticket, answer) pairs for a split of the imported tickets."""
    tickets = {t["id"]: t for t in retrieval_score.load_split(split)}
    families = retrieval_score.load_families()
    causes = {c["id"]: c for c in json.loads((EVALS_DIR / "causes.json").read_text())}
    labels = json.loads((EVALS_DIR / "cause_labels.json").read_text())
    incidents = json.loads((EVALS_DIR / "incidents.json").read_text())
    root_causes = {i["id"]: i["root_cause"] for i in incidents}
    pairs = []
    for label in labels:
        ticket = tickets.get(label["id"])
        if ticket is None:
            continue
        family = families[retrieval_score.family_of(ticket["id"])]
        answer = {
            **label,
            "family": family["name"],
            "cause": causes[label["cause"]]["name"],
            "root_cause": root_causes[ticket["id"]],
            "units": [family["doc"]] if family["doc"] else [],
            "difficulty": "routine",
            "tiny": False,
            "note": "Repeat lockouts in the records, so SEC-04 applies."
            if label.get("sec_04")
            else "",
        }
        text = f"{ticket['title']}\n\n{ticket['description']}"
        pairs.append(({**ticket, "text": text}, answer))
    return pairs


def load_any(name: str, tiny: bool = False) -> list[tuple[dict, dict]]:
    """Return (ticket, answer) pairs for any set the agent can be scored on."""
    if name in IMPORTED_SETS:
        return load_imported(name)
    return [
        (ticket, {**answer, "family": "Rules set", "cause": None})
        for ticket, answer in load_set(name, tiny)
    ]


def load_review_tickets() -> list[tuple[dict, dict]]:
    """The tickets a person reviews. Held-out tickets stay out."""
    rules = [(ticket, {**answer, "checks": []}) for ticket, answer in load_any("rules")]
    return rules + [p for split in REVIEW_SPLITS for p in load_imported(split)]


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:8]


def instructions_version() -> str:
    return _hash((config.ROOT / "agent" / "prompt.md").read_bytes())


def tools_version() -> str:
    tools = [DECISION_TOOL, TOOLS, TOOL_POLICY]
    return _hash(json.dumps(tools, sort_keys=True).encode())


def version() -> str:
    """One short hash of what the model is given: the instructions and the tools."""
    return _hash(f"{instructions_version()}{tools_version()}".encode())


def _unit_id(u: dict) -> str:
    return u["doc"] if u["section"] is None else f"{u['doc']}::{u['section']}"


def _attempt(text: str) -> dict:
    """Run one ticket. A failure counts as an escalation and doesn't stop the run."""
    try:
        return {**run_triage(text, use_retrieval=True), "error": None}
    except Exception as exc:  # one bad ticket must never stop an evaluation
        return {
            "path": "ESCALATE",
            "cause": None,
            "retrieved": [],
            "tool_name": None,
            "tool_input": None,
            "usage": None,
            "response_time_sec": 0.0,
            "error": f"{type(exc).__name__}: {exc}",
        }


def score_ticket(ticket: dict, answer: dict, result: dict, model: str) -> dict:
    """Combine a ticket, its answer and the agent's result into one row."""
    path, tool = result["path"], result["tool_name"]
    queue = (result["tool_input"] or {}).get("queue")
    usage = result["usage"] or {"input_tokens": 0, "output_tokens": 0}
    retrieved = [_unit_id(u) for u in result["retrieved"]]
    return {
        "id": ticket["id"],
        "text": ticket["text"],
        "requester": ticket["requester"],
        "difficulty": answer["difficulty"],
        "cause": result["cause"],
        "expected_cause": answer["cause"],
        "expected_paths": answer["paths"],
        "expected_tools": answer["tools"],
        "expected_queues": answer["queues"],
        "expected_units": answer["units"],
        **scoring.score_decision(answer, path, tool, queue),
        "tool": tool,
        "queue": queue,
        "retrieved": retrieved,
        "cause_correct": scoring.cause_correct(answer, result["cause"]),
        "retrieval_correct": scoring.retrieval_correct(answer, retrieved),
        **usage,
        "cost_usd": config.cost_usd(
            model, usage["input_tokens"], usage["output_tokens"]
        ),
        "time_sec": result["response_time_sec"],
        "error": result["error"],
    }


def evaluate(name: str, tiny: bool = False) -> dict:
    """Run a set through the agent and return the evaluation."""
    model = config.model_name()
    pairs = load_any(name, tiny)
    rows = [
        score_ticket(ticket, answer, _attempt(ticket["text"]), model)
        for ticket, answer in pairs
    ]
    now = datetime.now(UTC)
    return {
        "id": f"{now:%Y%m%dT%H%M%S}-{name}{'-tiny' if tiny else ''}",
        "date": now.isoformat(timespec="seconds"),
        "set": name,
        "tiny": tiny,
        "model": model,
        "version": version(),
        "instructions_version": instructions_version(),
        "tools_version": tools_version(),
        "kb_version": retrieval_score.kb_version(),
        "summary": scoring.summarize(rows),
        "yardsticks": yardsticks.score(pairs, load_imported(yardsticks.TRAINING_SPLIT)),
        "confusion": scoring.confusion(rows),
        "per_path": scoring.per_path(rows),
        "by_difficulty": scoring.by_difficulty(rows),
        "by_family": scoring.by_family(rows),
        "tickets": rows,
    }


def save_run(run: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(run, indent=2, ensure_ascii=False)
    (RUNS_DIR / f"{run['id']}.json").write_text(text + "\n")


def load_runs() -> list[dict]:
    """Saved evaluations, newest first. Runs from before the yardsticks are left out."""
    paths = sorted(RUNS_DIR.glob("*.json"), reverse=True)
    runs = [json.loads(p.read_text()) for p in paths]
    return [run for run in runs if "yardsticks" in run]


def _percent(share: float | None) -> str:
    return "n/a" if share is None else f"{share:.0%}"


def _with_margin(summary: dict, measure: str) -> str:
    share = summary[f"{measure}_accuracy"]
    if share is None:
        return "n/a"
    return f"{share:.0%} ±{summary[f'{measure}_margin']:.0%}"


def print_report(run: dict) -> None:
    s = run["summary"]
    cost = s["cost_per_ticket_chf"]
    print(f"{run['id']}  {run['model']}  version {run['version']}\n")
    print(
        f"path {_with_margin(s, 'path')}  action {_with_margin(s, 'action')}  "
        f"team {_with_margin(s, 'team')}  cause {_percent(s['cause_accuracy'])}  "
        f"retrieval {s['retrieval_accuracy']:.0%}  "
        f"automation {s['automation_rate']:.0%}  kappa {s['kappa']:.2f}"
    )
    print(
        f"mistakes CHF {s['mistake_cost_chf']:,}  "
        f"cost per ticket {'unknown' if cost is None else f'CHF {cost:.4f}'}  "
        f"time per ticket {s['time_per_ticket_sec']:.1f}s  failed {s['failed']}\n"
    )
    for name, y in run["yardsticks"].items():
        print(
            f"{name}: path {_with_margin(y, 'path')}  "
            f"action {_with_margin(y, 'action')}  team {_with_margin(y, 'team')}  "
            f"kappa {y['kappa']:.2f}  mistakes CHF {y['mistake_cost_chf']:,}"
        )
    print()
    for t in run["tickets"]:
        if t["mistake_cost_chf"]:
            expected = "/".join(t["expected_paths"])
            print(f"CHF {t['mistake_cost_chf']:>5,}  {t['id']}  {t['text'][:60]}")
            print(f"           expected {expected}, got {t['path']}")


def main() -> None:
    """Run the evaluation, save it and print the report."""
    parser = argparse.ArgumentParser(prog="evals", description=__doc__)
    sets = sorted([*PREFIXES, *IMPORTED_SETS])
    parser.add_argument("--set", choices=sets, default="rules", dest="name")
    parser.add_argument("--tiny", action="store_true", help="five trial tickets")
    parser.add_argument(
        "--retrieval", action="store_true", help="score retrieval, with no model calls"
    )
    parser.add_argument(
        "--split",
        action="append",
        choices=retrieval_score.SPLITS,
        help="a set to score retrieval on, instead of the development sets",
    )
    parser.add_argument("--save", action="store_true", help="keep the retrieval score")
    args = parser.parse_args()
    if args.retrieval:
        retrieval_score.main(args.split, args.save)
        return
    if args.tiny and args.name in IMPORTED_SETS:
        parser.error("--tiny only applies to the rules sets")
    run = evaluate(args.name, args.tiny)
    save_run(run)
    print_report(run)
