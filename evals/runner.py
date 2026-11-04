"""Runs the agent over a labelled set, scores it and saves the result.

`uv run -m evals` runs the development set. `--set held_out` runs the held-out set,
and `--tiny` runs only its five trial tickets. Results go to data/evals/runs/.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime

from agent import config, run_triage
from agent.tool_schemas import TOOLS
from evals import scoring

EVALS_DIR = config.ROOT / "data" / "evals"
RUNS_DIR = EVALS_DIR / "runs"
PREFIXES = {"dev": "", "held_out": "held_out_"}


def load_set(name: str, tiny: bool = False) -> list[tuple[dict, dict]]:
    """Return (ticket, answer) pairs. Only this module opens the answers."""
    prefix = PREFIXES[name]
    tickets = json.loads((EVALS_DIR / f"{prefix}tickets.json").read_text())
    answers = json.loads((EVALS_DIR / f"{prefix}answers.json").read_text())
    by_id = {a["id"]: a for a in answers}
    pairs = [(t, by_id[t["id"]]) for t in tickets]
    return [(t, a) for t, a in pairs if a["tiny"]] if tiny else pairs


def version() -> str:
    """A short hash of what the model is given: the instructions and the tools."""
    prompt = (config.ROOT / "agent" / "prompt.md").read_bytes()
    tools = json.dumps(TOOLS, sort_keys=True).encode()
    return hashlib.sha256(prompt + tools).hexdigest()[:8]


def _unit_id(u: dict) -> str:
    return u["doc"] if u["section"] is None else f"{u['doc']}::{u['section']}"


def _attempt(text: str) -> dict:
    """Run one ticket. A failure counts as an escalation and doesn't stop the run."""
    try:
        return {**run_triage(text, use_retrieval=True), "error": None}
    except Exception as exc:  # one bad ticket must never stop an evaluation
        return {
            "path": "ESCALATE",
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
        "expected_paths": answer["paths"],
        "expected_tools": answer["tools"],
        "expected_queues": answer["queues"],
        "expected_units": answer["units"],
        "path": path,
        "tool": tool,
        "queue": queue,
        "retrieved": retrieved,
        "path_correct": path in answer["paths"],
        "action_correct": scoring.action_correct(answer, path, tool, queue),
        "retrieval_correct": scoring.retrieval_correct(answer, retrieved),
        "mistake_cost_chf": scoring.mistake_cost(answer, path, tool, queue),
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
    rows = [
        score_ticket(ticket, answer, _attempt(ticket["text"]), model)
        for ticket, answer in load_set(name, tiny)
    ]
    now = datetime.now(UTC)
    return {
        "id": f"{now:%Y%m%dT%H%M%S}-{name}{'-tiny' if tiny else ''}",
        "date": now.isoformat(timespec="seconds"),
        "set": name,
        "tiny": tiny,
        "model": model,
        "version": version(),
        "summary": scoring.summarize(rows),
        "by_difficulty": scoring.by_difficulty(rows),
        "tickets": rows,
    }


def save_run(run: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(run, indent=2, ensure_ascii=False)
    (RUNS_DIR / f"{run['id']}.json").write_text(text + "\n")


def load_runs() -> list[dict]:
    """Saved evaluations, newest first."""
    paths = sorted(RUNS_DIR.glob("*.json"), reverse=True)
    return [json.loads(p.read_text()) for p in paths]


def print_report(run: dict) -> None:
    s = run["summary"]
    cost = s["cost_per_ticket_usd"]
    print(f"{run['id']}  {run['model']}  version {run['version']}\n")
    print(
        f"path {s['path_accuracy']:.0%}  action {s['action_accuracy']:.0%}  "
        f"retrieval {s['retrieval_accuracy']:.0%}  "
        f"automation {s['automation_rate']:.0%}"
    )
    print(
        f"mistakes CHF {s['mistake_cost_chf']:,}  "
        f"cost per ticket {'unknown' if cost is None else f'${cost:.4f}'}  "
        f"time per ticket {s['time_per_ticket_sec']:.1f}s  failed {s['failed']}\n"
    )
    for t in run["tickets"]:
        if t["mistake_cost_chf"]:
            expected = "/".join(t["expected_paths"])
            print(f"CHF {t['mistake_cost_chf']:>5,}  {t['id']}  {t['text'][:60]}")
            print(f"           expected {expected}, got {t['path']}")


def main() -> None:
    """Run the evaluation, save it and print the report."""
    parser = argparse.ArgumentParser(prog="evals", description=__doc__)
    parser.add_argument("--set", choices=sorted(PREFIXES), default="dev", dest="name")
    parser.add_argument("--tiny", action="store_true", help="five trial tickets")
    args = parser.parse_args()
    run = evaluate(args.name, args.tiny)
    save_run(run)
    print_report(run)
