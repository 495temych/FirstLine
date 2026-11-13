"""The release gate: a change ships only if it does no worse on the samples.

    uv run -m evals.gate                    run the change on the samples, and judge it
    uv run -m evals.gate --keep             and if it passes, make it the baseline
    uv run -m evals.gate --candidate ID ID  judge saved runs, with no model calls

The change runs on the two samples, `dev` and `unseen_dev`, with today's model and
design. A saved run of the same code is used instead of running again. The change is
refused when, on either sample, path accuracy falls by more than the baseline's
margin of error or the mistake bill rises. The baseline's runs are named in
`data/evals/baseline.json`.

With Langfuse set up, both runs of each sample go there as experiments on the same
dataset, and the gate reads their numbers back from Langfuse, so a refused change can
be opened beside its baseline there. Without Langfuse, it reads the saved runs.
"""

import argparse
import json
import sys
import time
from collections.abc import Callable
from typing import TypedDict

from langfuse import Langfuse

from agent import config, tracing
from evals import langfuse_upload, runner, scoring

SAMPLES = ("dev", "unseen_dev")
BASELINE_FILE = runner.EVALS_DIR / "baseline.json"
SAMPLE = {"tiny": False, "sample": True}
LANGFUSE_WAIT_SEC = 60  # how long scores may take to show in Langfuse
LANGFUSE_POLL_SEC = 3


class Measures(TypedDict):
    run: str
    n: int
    path_accuracy: float
    mistake_cost_chf: float
    source: str  # "Langfuse" or "the saved run"


class Check(TypedDict):
    set: str
    baseline: Measures
    candidate: Measures
    fell: float  # how far path accuracy fell, in points of a share
    margin: float  # the baseline's 95% margin of error on path accuracy
    bill_rose: float  # how much the mistake bill rose, in CHF
    passed: bool
    reasons: list[str]


# ── Judging ──────────────────────────────────────────────────────────────────────
def judge(name: str, baseline: Measures, candidate: Measures) -> Check:
    """One sample's verdict: refused if path accuracy falls by more than the
    baseline's margin of error, or the mistake bill rises at all."""
    share = baseline["path_accuracy"]
    margin = scoring.margin(share, baseline["n"])
    fell = share - candidate["path_accuracy"]
    bill_rose = candidate["mistake_cost_chf"] - baseline["mistake_cost_chf"]
    reasons = []
    if fell > margin:
        reasons.append(
            f"path accuracy fell {fell:.0%}, more than the margin of error {margin:.0%}"
        )
    if bill_rose > 0:
        reasons.append(f"the mistake bill rose CHF {bill_rose:,.0f}")
    return {
        "set": name,
        "baseline": baseline,
        "candidate": candidate,
        "fell": fell,
        "margin": margin,
        "bill_rose": bill_rose,
        "passed": not reasons,
        "reasons": reasons,
    }


def from_run(run: dict) -> Measures:
    summary = run["summary"]
    return {
        "run": run["id"],
        "n": summary["n"],
        "path_accuracy": summary["path_accuracy"],
        "mistake_cost_chf": summary["mistake_cost_chf"],
        "source": "the saved run",
    }


# ── Langfuse ─────────────────────────────────────────────────────────────────────
def from_langfuse(lf: Langfuse, run: dict) -> Measures:
    """A run's numbers as its Langfuse experiment holds them, sent first if it isn't
    there. Scores arrive in Langfuse a little after they're sent, so this waits."""
    langfuse_upload.replay(lf, run)
    lf.flush()
    deadline = time.monotonic() + LANGFUSE_WAIT_SEC
    while True:
        found = lf.api.experiments.list(
            from_start_time=langfuse_upload.SINCE, name=run["id"], fields="scores"
        ).data
        scores = {s.name: s.value for s in (found[0].scores or [])} if found else {}
        if "path_accuracy" in scores and "mistake_cost_chf" in scores:
            return {
                "run": run["id"],
                "n": found[0].item_count,
                "path_accuracy": float(scores["path_accuracy"]),
                "mistake_cost_chf": float(scores["mistake_cost_chf"]),
                "source": "Langfuse",
            }
        if time.monotonic() > deadline:
            raise TimeoutError(f"Langfuse has no scores for {run['id']} yet.")
        time.sleep(LANGFUSE_POLL_SEC)


def reader() -> Callable[[dict], Measures]:
    """How the gate reads a run: from Langfuse when it's set up, else the saved run."""
    if not tracing.enabled():
        return from_run
    lf = tracing.client()
    existing = {d.name for d in lf.api.datasets.list(limit=100).data}
    if not all(langfuse_upload.dataset_name(n) in existing for n in SAMPLES):
        langfuse_upload.upload_datasets(lf)

    def read(run: dict) -> Measures:
        try:
            return from_langfuse(lf, run)
        except TimeoutError as exc:
            print(f"{exc} Judged from the saved run instead.")
            return from_run(run)

    return read


# ── The runs ─────────────────────────────────────────────────────────────────────
def read_baseline() -> dict | None:
    if not BASELINE_FILE.exists():
        return None
    return json.loads(BASELINE_FILE.read_text())


def keep(runs: dict[str, dict]) -> None:
    first = next(iter(runs.values()))
    baseline = {
        "model": first["model"],
        "design": runner.design_of(first),
        "runs": {name: run["id"] for name, run in runs.items()},
    }
    BASELINE_FILE.write_text(json.dumps(baseline, indent=2) + "\n")


def candidates(saved: list[dict]) -> tuple[dict[str, dict], list[str]]:
    """Today's saved run of each sample, if the same code has one, and the samples
    still to run."""
    model = config.model_name()
    found = {}
    for name in SAMPLES:
        run = runner.repeat_of(name, SAMPLE, model, saved)
        if run is not None:
            found[name] = run
    return found, [name for name in SAMPLES if name not in found]


def estimate_chf(names: list[str], saved: list[dict]) -> float | None:
    model, design = config.model_name(), config.design()
    total = 0.0
    for name in names:
        tickets = len(runner.select(name, sampled=True))
        cost = runner.estimate_chf(model, tickets, saved, design)
        if cost is None:
            return None
        total += cost
    return total


def run_samples(names: list[str]) -> dict[str, dict]:
    runs = {}
    for name in names:
        run = runner.evaluate(name, sampled=True)
        runner.save_run(run)
        runs[name] = run
    return runs


def mismatch(baseline: dict, runs: dict[str, dict], saved: dict[str, dict]) -> str:
    """Why these runs can't be judged against the baseline, or "" if they can."""
    model, design = config.model_name(), config.design()
    if (baseline["model"], baseline["design"]) != (model, design):
        return (
            f"The baseline ran {baseline['model']} with {baseline['design']}, and "
            f"today's setting is {model} with {design}. Keep a baseline for it first."
        )
    for name, run in runs.items():
        base = saved[baseline["runs"][name]]
        if {t["id"] for t in base["tickets"]} != {t["id"] for t in run["tickets"]}:
            return f"The {name} sample's tickets changed since the baseline."
        if base["labels_version"] != run["labels_version"]:
            return (
                f"The labels changed since the baseline. Re-score {base['id']} with"
                " `uv run -m evals --rescore` and keep that."
            )
    return ""


# ── The report ───────────────────────────────────────────────────────────────────
def report(checks: list[Check]) -> str:
    lines = []
    for c in checks:
        b, n = c["baseline"], c["candidate"]
        verdict = "passes" if c["passed"] else "refused: " + "; ".join(c["reasons"])
        lines.append(
            f"{c['set']}: path {b['path_accuracy']:.0%} → {n['path_accuracy']:.0%}"
            f" (margin ±{c['margin']:.0%}), mistakes CHF {b['mistake_cost_chf']:,.0f}"
            f" → {n['mistake_cost_chf']:,.0f}, {verdict}"
        )
        lines.append(f"    {b['run']} → {n['run']}, read from {n['source']}")
    if any(c["candidate"]["source"] == "Langfuse" for c in checks):
        names = ", ".join(langfuse_upload.dataset_name(c["set"]) for c in checks)
        lines.append(f"Compare the experiments in Langfuse, in the datasets {names}.")
    return "\n".join(lines)


def gate(
    runs: dict[str, dict],
    baseline: dict,
    saved: dict[str, dict],
    read: Callable[[dict], Measures] = from_run,
) -> list[Check]:
    """Each sample's verdict, the baseline's run beside the change's."""
    return [
        judge(name, read(saved[baseline["runs"][name]]), read(run))
        for name, run in runs.items()
    ]


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="evals.gate", description=__doc__)
    parser.add_argument(
        "--candidate", nargs=len(SAMPLES), metavar="ID", help="saved runs to judge"
    )
    parser.add_argument(
        "--keep", action="store_true", help="keep the change as the baseline"
    )
    parser.add_argument(
        "--max-chf", type=float, default=runner.SPENDING_CAP_CHF, help="spending cap"
    )
    return parser.parse_args(argv)


def _gather(args: argparse.Namespace, saved: list[dict]) -> dict[str, dict]:
    """The change's run of each sample: named, saved for the same code, or run now."""
    if args.candidate:
        by_id = {run["id"]: run for run in saved}
        missing = [i for i in args.candidate if i not in by_id]
        if missing:
            raise SystemExit(f"No saved run {', '.join(missing)}.")
        runs = {by_id[i]["set"]: by_id[i] for i in args.candidate}
        if sorted(runs) != sorted(SAMPLES) or not all(
            r["sample"] for r in runs.values()
        ):
            raise SystemExit("Name one sample run of dev and one of unseen_dev.")
        return runs
    runs, missing = candidates(saved)
    if missing:
        cost = estimate_chf(missing, saved)
        if cost is None or cost > args.max_chf:
            stated = "an unknown cost" if cost is None else f"about CHF {cost:.2f}"
            raise SystemExit(
                f"Running {', '.join(missing)} is {stated}, over the CHF"
                f" {args.max_chf:.2f} cap. Pass --max-chf to allow it."
            )
        print(f"Running the {', '.join(missing)} sample: about CHF {cost:.2f}.")
        runs |= run_samples(missing)
    return {name: runs[name] for name in SAMPLES}


def main(argv: list[str] | None = None) -> int:
    """Judge the change against the baseline. 0 when it passes, 1 when refused."""
    args = _parse(argv)
    saved = runner.load_runs()
    runs = _gather(args, saved)
    baseline = read_baseline()
    if baseline is None:
        if not args.keep:
            raise SystemExit("There's no baseline yet. Pass --keep to make this one.")
        keep(runs)
        print("Kept as the baseline: " + ", ".join(r["id"] for r in runs.values()))
        return 0
    by_id = {run["id"]: run for run in [*saved, *runs.values()]}
    problem = mismatch(baseline, runs, by_id)
    if problem:
        raise SystemExit(problem)
    checks = gate(runs, baseline, by_id, reader())
    print(report(checks))
    passed = all(c["passed"] for c in checks)
    if passed and args.keep:
        keep(runs)
        print("Kept as the new baseline.")
    print("The change passes the gate." if passed else "The change is refused.")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
