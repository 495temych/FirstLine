"""Runs the agent over a labelled set, scores it and saves the result.

`uv run -m evals` runs the rules set. `--set` picks another set, such as `dev` or
`unseen_dev`. `--tiny` runs only the rules set's five trial tickets, and `--sample` a
few tickets from each family of an imported practice set. `--design loop` runs the
loop of lookups instead of one call. Each run also scores the two yardsticks, for
free. Results go to data/evals/runs/.

A run states its estimated cost first. It stops above the spending cap unless
`--max-chf` allows more, and it won't repeat a saved run unless `--again` is passed.
`--rescore` marks saved runs against the current labels, and `--retrieval` scores
retrieval. Neither calls a model.
"""

import argparse
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from agent import config, run_triage, tracing
from agent.decision import DECISION_TOOL, UNREADABLE
from agent.models import MODELS
from agent.tool_schemas import TOOL_POLICY, TOOLS
from evals import retrieval_score, scoring, yardsticks

EVALS_DIR = config.ROOT / "data" / "evals"
RUNS_DIR = EVALS_DIR / "runs"
PREFIXES = {"rules": "rules_", "rules_held_out": "rules_held_out_"}
IMPORTED_SETS = ("dev", "held_out", "unseen_dev", "unseen_held_out")
REVIEW_SPLITS = ("dev", "unseen_dev")  # the imported tickets a person may read
SAMPLE_PER_FAMILY = 3
WORKERS = 4  # tickets in flight at once. Each call is still timed on its own
SPENDING_CAP_CHF = 1.00  # the most a run may cost without --max-chf
TYPICAL_TOKENS = (6000, 600)  # input and output, when no saved run gives a cost
VERSION_KEYS = ("version", "instructions_version", "tools_version", "kb_version")
DECISION_KEYS = (
    "path",
    "tool",
    "queue",
    "cause",
    "retrieved",
    "input_tokens",
    "output_tokens",
    "time_sec",
    "error",
    "cost_usd",
    "invalid",
    "rule",
    "steps",
    "stopped",
)
LOOP_FILES = ("investigate.md", "loop.py", "lookups.py")
LABEL_FILES = (
    "rules_answers.json",
    "rules_held_out_answers.json",
    "causes.json",
    "cause_labels.json",
)


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


def sample(pairs: list[tuple[dict, dict]]) -> list[tuple[dict, dict]]:
    """A few tickets from each family, spread evenly by id and the same every time."""
    families: dict[str, list[tuple[dict, dict]]] = {}
    for pair in sorted(pairs, key=lambda p: p[0]["id"]):
        families.setdefault(pair[1]["family"], []).append(pair)
    picked = []
    for group in families.values():
        if len(group) <= SAMPLE_PER_FAMILY:
            picked += group
            continue
        step = len(group) / SAMPLE_PER_FAMILY
        picked += [group[int(i * step)] for i in range(SAMPLE_PER_FAMILY)]
    return picked


def select(name: str, tiny: bool = False, sampled: bool = False) -> list[tuple]:
    """The (ticket, answer) pairs a run would cover."""
    pairs = load_any(name, tiny)
    return sample(pairs) if sampled else pairs


def load_review_tickets() -> list[tuple[dict, dict]]:
    """The tickets a person reviews. Held-out tickets stay out."""
    rules = [(ticket, {**answer, "checks": []}) for ticket, answer in load_any("rules")]
    return rules + [p for split in REVIEW_SPLITS for p in load_imported(split)]


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:8]


def instructions_version() -> str:
    return _hash((config.ROOT / "agent" / "prompt.md").read_bytes())


def tools_version() -> str:
    """The tools, their risk tiers and the rules in code that act on the decision."""
    tools = [DECISION_TOOL, TOOLS, TOOL_POLICY]
    rules_code = (config.ROOT / "agent" / "rules.py").read_bytes()
    return _hash(json.dumps(tools, sort_keys=True).encode() + rules_code)


def loop_version() -> str:
    """The loop's own parts: its guide, its lookups and its limits."""
    parts = [(config.ROOT / "agent" / name).read_bytes() for name in LOOP_FILES]
    limits = f"{config.MAX_LOOKUPS}:{config.MAX_LOOP_CHF}".encode()
    return _hash(b"".join(parts) + limits)


def version() -> str:
    """One short hash of what the model is given: the instructions and the tools, and
    with the loop design, the loop too. One call's hash is as it always was."""
    given = f"{instructions_version()}{tools_version()}"
    if config.design() == "loop":
        given += f"loop{loop_version()}"
    return _hash(given.encode())


def labels_version() -> str:
    """One short hash of every answer file, so a re-scored run shows what it used."""
    return _hash(b"".join((EVALS_DIR / name).read_bytes() for name in LABEL_FILES))


def current_versions() -> dict:
    return {
        "version": version(),
        "instructions_version": instructions_version(),
        "tools_version": tools_version(),
        "kb_version": retrieval_score.kb_version(),
    }


def _unit_id(u: dict) -> str:
    return u["doc"] if u["section"] is None else f"{u['doc']}::{u['section']}"


def _attempt(text: str, requester: str, ticket_id: str) -> dict:
    """Run one ticket, in Queue mode. A failure counts as an escalation."""
    try:
        result = run_triage(
            text,
            use_retrieval=True,
            requester=requester,
            mode="queue",
            ticket_id=ticket_id,
        )
        return {**result, "error": None}
    except Exception as exc:  # one bad ticket must never stop an evaluation
        return {
            "path": "ESCALATE",
            "cause": None,
            "retrieved": [],
            "tool_name": None,
            "tool_input": None,
            "usage": None,
            "response_time_sec": 0.0,
            "rule": None,
            "steps": [],
            "stopped": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def decision(result: dict) -> dict:
    """What a run of the agent decided and used, which is all a score needs."""
    usage = result["usage"] or {"input_tokens": 0, "output_tokens": 0}
    return {
        "path": result["path"],
        "tool": result["tool_name"],
        "queue": (result["tool_input"] or {}).get("queue"),
        "cause": result["cause"],
        "retrieved": [_unit_id(u) for u in result["retrieved"]],
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "time_sec": result["response_time_sec"],
        "error": result["error"],
        "cost_usd": usage.get("cost_usd"),
        "invalid": result.get("reasoning") == UNREADABLE,
        "rule": (result.get("rule") or {}).get("rule"),
        "steps": result.get("steps") or [],
        "stopped": result.get("stopped"),
    }


def score_ticket(ticket: dict, answer: dict, made: dict, model: str) -> dict:
    """Combine a ticket, its answer and the agent's decision into one row."""
    path, tool, queue = made["path"], made["tool"], made["queue"]
    retrieved = made["retrieved"]
    return {
        "id": ticket["id"],
        "text": ticket["text"],
        "requester": ticket["requester"],
        "difficulty": answer["difficulty"],
        "cause": made["cause"],
        "expected_cause": answer["cause"],
        "expected_paths": answer["paths"],
        "expected_tools": answer["tools"],
        "expected_queues": answer["queues"],
        "expected_units": answer["units"],
        **scoring.score_decision(answer, path, tool, queue),
        "tool": tool,
        "queue": queue,
        "retrieved": retrieved,
        "cause_correct": scoring.cause_correct(answer, made["cause"]),
        "retrieval_correct": scoring.retrieval_correct(answer, retrieved),
        "input_tokens": made["input_tokens"],
        "output_tokens": made["output_tokens"],
        "cost_usd": cost_of(made, model),
        "time_sec": made["time_sec"],
        "error": made["error"],
        "invalid": bool(made.get("invalid")),
        "rule": made.get("rule"),
        "steps": made.get("steps") or [],
        "stopped": made.get("stopped"),
    }


def cost_of(made: dict, model: str) -> float | None:
    """What the provider says a call cost, or else its tokens at the list price."""
    if made.get("cost_usd") is not None:
        return made["cost_usd"]
    return config.cost_usd(model, made["input_tokens"], made["output_tokens"])


def serving(model: str) -> dict:
    """Who served a run, where, and at what reasoning effort."""
    m = MODELS.get(model)
    if m is None:
        return {"lab": "anthropic", "provider": None, "region": "US", "effort": None}
    return {
        "lab": m.lab,
        "provider": m.provider or m.lab,
        "region": m.region,
        "effort": m.effort,
    }


def _assemble(
    name: str, pairs: list[tuple], rows: list[dict], model: str, versions: dict, **kind
) -> dict:
    """A saved run. `kind` says whether it was tiny, a sample or re-scored."""
    now = datetime.now(UTC)
    design = kind.pop("design", "one call")
    suffix = "-loop" if design == "loop" else ""
    suffix += "".join(f"-{label}" for label, on in kind.items() if on)
    return {
        "id": f"{now:%Y%m%dT%H%M%S}-{name}{suffix}",
        "date": now.isoformat(timespec="seconds"),
        "set": name,
        "design": design,
        "tiny": kind.get("tiny", False),
        "sample": kind.get("sample", False),
        "model": model,
        "serving": serving(model),
        **versions,
        "labels_version": labels_version(),
        "summary": scoring.summarize(rows),
        "yardsticks": yardsticks.score(pairs, load_imported(yardsticks.TRAINING_SPLIT)),
        "confusion": scoring.confusion(rows),
        "per_path": scoring.per_path(rows),
        "by_difficulty": scoring.by_difficulty(rows),
        "by_family": scoring.by_family(rows),
        "tickets": rows,
    }


def _traced_attempt(ticket: dict, name: str, session: str) -> dict:
    """One ticket's run, traced in Langfuse under the evaluation's session."""
    tags = ("evaluation", name)
    with tracing.trace(
        "evaluation",
        session_id=session,
        tags=tags,
        metadata={"ticket": ticket["id"], "version": version()},
    ):
        return _attempt(ticket["text"], ticket["requester"], ticket["id"])


def evaluate(name: str, tiny: bool = False, sampled: bool = False) -> dict:
    """Run a set through the agent and return the evaluation."""
    model = config.model_name()
    pairs = select(name, tiny, sampled)
    session = f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{name}"

    def one(pair: tuple[dict, dict]) -> dict:
        ticket, answer = pair
        made = decision(_traced_attempt(ticket, name, session))
        return score_ticket(ticket, answer, made, model)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        rows = list(pool.map(one, pairs))
    tracing.flush()
    return _assemble(
        name,
        pairs,
        rows,
        model,
        current_versions(),
        design=config.design(),
        tiny=tiny,
        sample=sampled,
    )


def rescore(run: dict) -> dict:
    """Mark a saved run's decisions against the current labels, with no model calls."""
    saved = {row["id"]: row for row in run["tickets"]}
    pairs = [(t, a) for t, a in load_any(run["set"]) if t["id"] in saved]
    rows = [
        score_ticket(
            t, a, {k: saved[t["id"]].get(k) for k in DECISION_KEYS}, run["model"]
        )
        for t, a in pairs
    ]
    versions = {key: run[key] for key in VERSION_KEYS}
    kind = {
        "design": design_of(run),
        "tiny": run["tiny"],
        "sample": run.get("sample", False),
        "rescored": True,
    }
    new = _assemble(run["set"], pairs, rows, run["model"], versions, **kind)
    return {**new, "rescored_from": run.get("rescored_from", run["id"])}


def to_rescore(ids: list[str], runs: list[dict]) -> list[dict]:
    """The saved runs named, or with none named, the newest full run of each set in
    each design."""
    if ids:
        by_id = {run["id"]: run for run in runs}
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise KeyError(f"no saved run {', '.join(missing)}")
        return [by_id[i] for i in ids]
    newest: dict[tuple[str, str], dict] = {}
    for run in runs:
        if not run["tiny"] and not run.get("sample"):
            newest.setdefault((run["set"], design_of(run)), run)
    return list(newest.values())


def _one_call_chf(model: str, runs: list[dict]) -> float | None:
    """One call's cost per ticket: the dearest saved one-call run, or a typical call."""
    rates = [
        run["summary"]["cost_per_ticket_chf"]
        for run in runs
        if run["model"] == model
        and design_of(run) == "one call"
        and run["summary"].get("cost_per_ticket_chf")
    ]
    if rates:
        return max(rates)
    usd = config.cost_usd(model, *TYPICAL_TOKENS)
    return None if usd is None else usd * scoring.USD_TO_CHF


def estimate_chf(
    model: str, tickets: int, runs: list[dict], design: str = "one call"
) -> float | None:
    """What a run should cost. The loop is assumed to use its step limit: a model
    turn for each lookup and one to decide, each at least one call's cost, up to the
    loop's spending limit per ticket."""
    rate = _one_call_chf(model, runs)
    if rate is None:
        return None
    if design == "loop":
        rate = min(rate * (config.MAX_LOOKUPS + 1), config.MAX_LOOP_CHF)
    return rate * tickets


def repeat_of(name: str, kind: dict, model: str, runs: list[dict]) -> dict | None:
    """A saved run of the same tickets with the same model, instructions and tools."""
    versions = current_versions()
    for run in runs:
        same_kind = (
            run["tiny"] == kind["tiny"]
            and run.get("sample", False) == kind["sample"]
            and design_of(run) == config.design()
        )
        if (
            run["set"] == name
            and same_kind
            and run["model"] == model
            and all(run[key] == versions[key] for key in VERSION_KEYS)
        ):
            return run
    return None


def save_run(run: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(run, indent=2, ensure_ascii=False)
    (RUNS_DIR / f"{run['id']}.json").write_text(text + "\n")


def load_runs() -> list[dict]:
    """Saved evaluations, newest first. Runs from before the yardsticks are left out."""
    paths = sorted(RUNS_DIR.glob("*.json"), reverse=True)
    runs = [json.loads(p.read_text()) for p in paths]
    return [run for run in runs if "yardsticks" in run]


def design_of(run: dict) -> str:
    """A run's design. Runs from before the loop were all one call."""
    return run.get("design", "one call")


def default_runs(*, full: bool = True) -> list[dict]:
    """The default model's runs in the current design, newest first: what the product
    runs on. With `full`, samples and tiny runs are left out. Other models' runs belong
    to the benchmark.
    """
    return [
        run
        for run in load_runs()
        if run.get("model") == config.model_name()
        and design_of(run) == config.design()
        and not (full and (run.get("tiny") or run.get("sample")))
    ]


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
    design = design_of(run)
    print(f"{run['id']}  {run['model']}  {design}  version {run['version']}")
    if run.get("rescored_from"):
        print(f"re-scored from {run['rescored_from']}, with no model calls")
    print()
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


def _check_spend(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Stop a run that repeats a saved one or costs more than allowed."""
    model, runs = config.model_name(), load_runs()
    tickets = len(select(args.name, args.tiny, args.sample))
    kind = {"tiny": args.tiny, "sample": args.sample}
    same = repeat_of(args.name, kind, model, runs)
    if same and not args.again:
        parser.error(
            f"{same['id']} already ran these tickets with the same design, model,"
            " instructions, tools and knowledge base. Re-score it with"
            f" --rescore {same['id']}, or pass --again to run it anyway."
        )
    cost = estimate_chf(model, tickets, runs, config.design())
    cap = SPENDING_CAP_CHF if args.max_chf is None else args.max_chf
    if cost is None:
        if args.max_chf is None:
            parser.error(f"{model} has no price. Pass --max-chf to run it anyway.")
        print(f"{tickets} tickets, at an unknown cost.\n")
        return
    if cost > cap:
        parser.error(
            f"This run is about CHF {cost:.2f} for {tickets} tickets, over the"
            f" CHF {cap:.2f} cap. Pass --max-chf {cost * 1.5:.2f} to go ahead."
        )
    print(f"About CHF {cost:.2f} for {tickets} tickets.\n")


def main() -> None:
    """Run the evaluation, save it and print the report."""
    parser = argparse.ArgumentParser(prog="evals", description=__doc__)
    sets = sorted([*PREFIXES, *IMPORTED_SETS])
    parser.add_argument("--set", choices=sets, default="rules", dest="name")
    parser.add_argument("--tiny", action="store_true", help="five trial tickets")
    parser.add_argument(
        "--sample",
        action="store_true",
        help=f"{SAMPLE_PER_FAMILY} tickets from each family of dev or unseen_dev",
    )
    parser.add_argument(
        "--max-chf",
        type=float,
        help=f"the most this run may cost, instead of CHF {SPENDING_CAP_CHF:.2f}",
    )
    parser.add_argument(
        "--again", action="store_true", help="repeat a run that's already saved"
    )
    parser.add_argument(
        "--rescore",
        nargs="*",
        metavar="RUN",
        help="mark saved runs against the current labels, with no model calls."
        " With no run named, the newest full run of each set",
    )
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
    parser.add_argument(
        "--design",
        choices=config.DESIGNS,
        help="how the agent works a ticket, instead of DESIGN or one call",
    )
    parser.add_argument(
        "--model",
        choices=sorted(MODELS),
        help="the model to evaluate, instead of MODEL_NAME or the default",
    )
    args = parser.parse_args()
    if args.model:
        os.environ["MODEL_NAME"] = args.model
    if args.design:
        os.environ["DESIGN"] = args.design
    if args.retrieval:
        retrieval_score.main(args.split, args.save)
        return
    if args.rescore is not None:
        try:
            chosen = to_rescore(args.rescore, load_runs())
        except KeyError as exc:
            parser.error(str(exc.args[0]))
        for old in chosen:
            new = rescore(old)
            save_run(new)
            print_report(new)
        return
    if args.tiny and args.name in IMPORTED_SETS:
        parser.error("--tiny only applies to the rules sets")
    if args.sample and args.name not in REVIEW_SPLITS:
        parser.error("--sample only applies to dev and unseen_dev")
    _check_spend(parser, args)
    run = evaluate(args.name, args.tiny, args.sample)
    save_run(run)
    print_report(run)
