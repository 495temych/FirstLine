"""Golden-set evaluation for retrieval + path classification.

Calls retrieve() and run_triage() directly — no UI, no mocking. Runnable
standalone: `uv run -m evals`. Also imported by the app to surface the same
results in a collapsed expander (cached at startup, not re-run per query).

The golden set mirrors the "Demo queries" table in README.md — same
queries, same expected paths — plus a hand-labeled expected_units set per
query: the KB unit(s) (doc name, or "doc::section" for a company-profile.md
section) that the top-ranked retrieval result should be one of, for the
query to be considered grounded correctly. Most rows have a single expected
unit; the "Locked out twice already today" row has two, since either the
account-access playbook or company-profile's SEC-04 policy section would
correctly ground the top-1 result (it's the deliberate cross-document case).
"""

import json

from agent import run_triage
from agent.config import ROOT

GOLDEN_FILE = ROOT / "data" / "evals" / "golden.json"


def load_golden() -> list[dict]:
    """Load the golden set. JSON has no sets, so the labels become sets here."""
    return [
        {
            "query": case["query"],
            "expected_units": set(case["expected_units"]),
            "expected_path": set(case["expected_path"]),
        }
        for case in json.loads(GOLDEN_FILE.read_text())
    ]


def _unit_id(u: dict) -> str:
    return u["doc"] if u["section"] is None else f"{u['doc']}::{u['section']}"


def _top1_correct(expected: set, retrieved_ids: list) -> bool:
    top1 = retrieved_ids[0] if retrieved_ids else None
    if not expected:
        # Nothing should have matched — correct iff retrieval also found nothing.
        return top1 is None
    return top1 in expected


def run_eval() -> list[dict]:
    """Run every golden-set case through the real pipeline and score it."""
    rows = []
    for case in load_golden():
        result = run_triage(case["query"], use_retrieval=True)
        retrieved_ids = [_unit_id(u) for u in result["retrieved"]]
        rows.append(
            {
                "query": case["query"],
                "expected_units": case["expected_units"],
                "retrieved_units": retrieved_ids,
                "top1_correct": _top1_correct(case["expected_units"], retrieved_ids),
                "expected_path": case["expected_path"],
                "actual_path": result["path"],
                "path_correct": result["path"] in case["expected_path"],
            }
        )
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "n": n,
        "retrieval_accuracy": sum(r["top1_correct"] for r in rows) / n,
        "path_accuracy": sum(r["path_correct"] for r in rows) / n,
    }


def _fmt_units(ids) -> str:
    return ", ".join(sorted(ids)) if ids else "(none)"


def _mark(ok: bool) -> str:
    return "✓" if ok else "✗"


def print_report(rows: list[dict], summary: dict) -> None:
    print(f"Golden-set evaluation — {summary['n']} queries\n")

    for r in rows:
        print(
            f"{_mark(r['top1_correct'])} retrieval | {_mark(r['path_correct'])} path  "
            f'"{r["query"]}"'
        )
        print(f"    expected units:  {_fmt_units(r['expected_units'])}")
        print(f"    retrieved units: {_fmt_units(r['retrieved_units'])}")
        print(
            f"    expected path:   {'/'.join(sorted(r['expected_path']))}   "
            f"actual: {r['actual_path']}"
        )
        print()

    print(
        f"SUMMARY  retrieval_accuracy={summary['retrieval_accuracy']:.0%}  "
        f"path_accuracy={summary['path_accuracy']:.0%}"
    )


def main() -> None:
    """Run the evaluation and print the report."""
    rows = run_eval()
    print_report(rows, summarize(rows))
