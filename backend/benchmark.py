"""Which model to run on: every evaluated model, ranked by what it saves.

Each model's newest full run of a set is scored by net saving per ticket, from
`backend/economics.py`, so a security mistake weighs what it costs. A model with only
a sample run shows that, marked. The two yardsticks sit beside the models at no model
cost, as the bar to clear, and stay off the front. A model is on the Pareto front when
no other model saves at least as much for no more money (or time), and beats it on one.

    uv run -m backend.benchmark          the development set
    uv run -m backend.benchmark --set unseen_dev
"""

import argparse

from fastapi import APIRouter

from agent import config
from agent.models import label
from backend import economics
from evals import runner, scoring

SETS = ("dev", "unseen_dev", "rules")
SET_NAMES = {"dev": "development", "unseen_dev": "unseen", "rules": "rules"}
MAIN_SET = "dev"  # where money is counted, on the real mix of requests
YARDSTICKS = {
    "most_common": "Always the most common answer",
    "classifier": "Classifier",
}
RULE = (
    "The cheapest model on the cost front whose net saving on the development set is"
    " within the margin of the best, with no security mistake on the rules set."
)


def newest_runs(name: str, runs: list[dict]) -> dict[str, dict]:
    """Each model's newest full run of a set, or its newest sample if it has no full
    run. Tiny runs are left out.
    """
    full: dict[str, dict] = {}
    sampled: dict[str, dict] = {}
    for run in runs:
        if run["set"] != name or run["tiny"]:
            continue
        (sampled if run.get("sample") else full).setdefault(run["model"], run)
    return {**{m: r for m, r in sampled.items() if m not in full}, **full}


def _security(run: dict) -> int:
    return sum(t["mistake_cost_chf"] == scoring.COST_SECURITY for t in run["tickets"])


def _entry(run: dict) -> dict:
    s = run["summary"]
    layer = economics.from_summary(s)
    return {
        "model": run["model"],
        "label": label(run["model"]),
        "kind": "model",
        "source": run["id"],
        "sample": bool(run.get("sample")),
        "serving": run.get("serving") or runner.serving(run["model"]),
        "n": s["n"],
        "net_chf": layer["net_chf"],
        "net_low": layer["net_low"],
        "net_high": layer["net_high"],
        "cost_chf": s["cost_per_ticket_chf"],
        "time_p50_sec": s.get("time_p50_sec"),
        "time_p90_sec": s.get("time_p90_sec"),
        "path_accuracy": s["path_accuracy"],
        "path_margin": s["path_margin"],
        "action_accuracy": s["action_accuracy"],
        "balanced_accuracy": s.get("balanced_accuracy"),
        "mistake_cost_chf": s["mistake_cost_chf"],
        "security_mistakes": _security(run),
        "invalid": s.get("invalid", s["failed"]),
    }


def _yardstick(key: str, run: dict) -> dict:
    y = run["yardsticks"][key]
    layer = economics.from_summary(y)
    return {
        "model": key,
        "label": YARDSTICKS[key],
        "kind": "yardstick",
        "source": run["id"],
        "sample": False,
        "serving": None,
        "n": y["n"],
        "net_chf": layer["net_chf"],
        "net_low": layer["net_low"],
        "net_high": layer["net_high"],
        "cost_chf": 0.0,
        "time_p50_sec": None,
        "time_p90_sec": None,
        "path_accuracy": y["path_accuracy"],
        "path_margin": y["path_margin"],
        "action_accuracy": y["action_accuracy"],
        "balanced_accuracy": None,
        "mistake_cost_chf": y["mistake_cost_chf"],
        "security_mistakes": None,
        "invalid": 0,
    }


def front(entries: list[dict], axis: str) -> set[str]:
    """The models no other beats: at least as much saved for no more of `axis`, and
    better on one. Entries with no value on the axis can't be placed.
    """
    placed = [e for e in entries if e[axis] is not None]

    def beaten(e: dict) -> bool:
        return any(
            o[axis] <= e[axis]
            and o["net_chf"] >= e["net_chf"]
            and (o[axis] < e[axis] or o["net_chf"] > e["net_chf"])
            for o in placed
        )

    return {e["model"] for e in placed if not beaten(e)}


def table(name: str = MAIN_SET, runs: list[dict] | None = None) -> dict:
    """Every model's newest run of a set, the yardsticks, and both fronts."""
    newest = newest_runs(name, runner.load_runs() if runs is None else runs)
    entries = [_entry(run) for run in newest.values()]
    if newest:
        full = [r for r in newest.values() if not r.get("sample")]
        latest = max(full or newest.values(), key=lambda r: r["id"])
        entries += [_yardstick(key, latest) for key in YARDSTICKS]
    models = [e for e in entries if e["kind"] == "model"]
    by_cost, by_time = front(models, "cost_chf"), front(models, "time_p50_sec")
    for e in entries:
        e["front_cost"] = e["model"] in by_cost
        e["front_time"] = e["model"] in by_time
    entries.sort(key=lambda e: e["net_chf"], reverse=True)
    return {"set": name, "entries": entries}


def _models(t: dict) -> list[dict]:
    return [e for e in t["entries"] if e["kind"] == "model"]


def choose(sets: dict[str, dict]) -> dict | None:
    """The model the rule picks, with the best one it was measured against."""
    dev = [e for e in _models(sets[MAIN_SET]) if not e["sample"]]
    if not dev:
        return None
    best = max(dev, key=lambda e: e["net_chf"])
    rules = {e["model"]: e for e in _models(sets["rules"])}
    safe = [
        e
        for e in dev
        if e["front_cost"]
        and e["net_chf"] >= best["net_low"]
        and e["model"] in rules
        and rules[e["model"]]["security_mistakes"] == 0
    ]
    if not safe:
        return {"model": None, "label": None, "best": best["model"]}
    pick = min(safe, key=lambda e: e["cost_chf"] or 0.0)
    return {"model": pick["model"], "label": pick["label"], "best": best["model"]}


def _francs(amount: float) -> str:
    return f"CHF {amount:,.2f}".replace(",", "'")


def _times(a: float, b: float) -> str:
    return f"{a / b:.0f} times" if b else "infinitely"


def insights(sets: dict[str, dict]) -> list[dict]:
    """What the runs show, as questions and one-sentence answers built from them."""
    dev = [e for e in _models(sets[MAIN_SET]) if not e["sample"]]
    if not dev:
        return []
    out = []
    best = max(dev, key=lambda e: e["net_chf"])
    out.append(
        {
            "question": "Which model saves the most?",
            "answer": f"{best['label']}, {_francs(best['net_chf'])} a ticket"
            f" (from {_francs(best['net_low'])} to {_francs(best['net_high'])}),"
            f" on {best['n']} development tickets.",
        }
    )
    priced = [e for e in dev if e["cost_chf"]]
    if len(priced) > 1:
        dear = max(priced, key=lambda e: e["cost_chf"])
        cheap = min(priced, key=lambda e: e["cost_chf"])
        gap = dear["net_chf"] - cheap["net_chf"]
        ratio = _times(dear["cost_chf"], cheap["cost_chf"])
        out.append(
            {
                "question": "Does paying more buy more?",
                "answer": f"{dear['label']} costs {ratio}"
                f" as much as {cheap['label']} per ticket, and saves"
                f" {_francs(abs(gap))} {'more' if gap >= 0 else 'less'}.",
            }
        )
    classifier = next(
        (e for e in sets[MAIN_SET]["entries"] if e["model"] == "classifier"), None
    )
    if classifier:
        beat = [e["label"] for e in dev if e["net_chf"] > classifier["net_chf"]]
        out.append(
            {
                "question": "Does any model beat the free classifier?",
                "answer": (
                    f"On development tickets, {', '.join(beat)}."
                    if beat
                    else "Not on the development tickets, where the classifier saves"
                    f" {_francs(classifier['net_chf'])}. They're templated, which suits"
                    " it, so the rules and unseen sets below matter more."
                ),
            }
        )
    unseen = _models(sets["unseen_dev"])
    if len(unseen) > 1:
        top = max(unseen, key=lambda e: e["path_accuracy"])
        low = min(unseen, key=lambda e: e["path_accuracy"])
        out.append(
            {
                "question": "Which admits what it doesn't know?",
                "answer": f"On families with no playbook, {top['label']} escalates"
                f" {top['path_accuracy']:.0%} as it should, and {low['label']}"
                f" {low['path_accuracy']:.0%}.",
            }
        )
    labels = {e["model"]: e["label"] for n in SETS for e in _models(sets[n])}
    risky = []
    for model, name in labels.items():
        where = [
            f"{e['security_mistakes']} on {SET_NAMES[n]}"
            for n in SETS
            for e in _models(sets[n])
            if e["model"] == model and e["security_mistakes"]
        ]
        if where:
            risky.append(f"{name} ({', '.join(where)})")
    price = f"CHF {scoring.COST_SECURITY:,}".replace(",", "'")
    out.append(
        {
            "question": "Which ones risk a security mistake?",
            "answer": (
                "These applied a routine fix where a security escalation was"
                f" needed, at {price} each: {'; '.join(risky)}."
                if risky
                else "None, on any set."
            ),
        }
    )
    timed = [e for e in dev if e["time_p50_sec"] is not None]
    if len(timed) > 1:
        fast = min(timed, key=lambda e: e["time_p50_sec"])
        slow = max(timed, key=lambda e: e["time_p50_sec"])
        out.append(
            {
                "question": "How long does a ticket take?",
                "answer": f"From {fast['time_p50_sec']:.1f} s for {fast['label']} to"
                f" {slow['time_p50_sec']:.1f} s for {slow['label']}, at the median.",
            }
        )
    return out


def view(runs: list[dict] | None = None) -> dict:
    loaded = runner.load_runs() if runs is None else runs
    sets = {name: table(name, loaded) for name in SETS}
    return {
        "sets": sets,
        "rule": RULE,
        "chosen": choose(sets),
        "default": {"model": config.model_name(), "label": label(config.model_name())},
        "insights": insights(sets),
        "catch_rate": economics.CATCH_RATE,
    }


router = APIRouter()


@router.get("/api/benchmark", operation_id="read_benchmark")
def read_benchmark() -> dict:
    """Every evaluated model by net saving per ticket, with the Pareto front, the
    model the rule picks, and what the runs show.
    """
    return view()


def _cell(value: float | None, form: str) -> str:
    return "n/a" if value is None else format(value, form)


def main() -> None:
    parser = argparse.ArgumentParser(prog="backend.benchmark", description=__doc__)
    parser.add_argument("--set", choices=SETS, default=MAIN_SET, dest="name")
    args = parser.parse_args()
    result = view()
    print(f"{args.name}: net saving per ticket, best first. * on the cost front\n")
    for e in result["sets"][args.name]["entries"]:
        mark = "*" if e["front_cost"] else " "
        print(
            f"{mark} {e['label'][:30]:30} net CHF {e['net_chf']:6.2f} "
            f"({e['net_low']:.2f} to {e['net_high']:.2f})  "
            f"cost {_cell(e['cost_chf'], '.4f')}  "
            f"p50 {_cell(e['time_p50_sec'], '.1f')} s  "
            f"action {e['action_accuracy']:.0%}  "
            f"balanced {_cell(e['balanced_accuracy'], '.0%')}  "
            f"mistakes CHF {e['mistake_cost_chf']:,}  invalid {e['invalid']}"
        )
    chosen = result["chosen"]
    print(f"\n{RULE}\nPicked: {chosen and chosen['label']}\n")
    for i in result["insights"]:
        print(f"{i['question']} {i['answer']}")


if __name__ == "__main__":
    main()
