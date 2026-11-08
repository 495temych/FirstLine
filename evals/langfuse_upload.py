"""Copies what's saved locally to Langfuse, with no model calls.

`uv run -m evals.langfuse_upload` makes one Langfuse dataset per practice set, replays
the newest full run of each as an experiment scored with our own measures, and sends the
Assistant's usage log as traces. Held-out tickets never leave this machine. Anything
already uploaded is skipped, so it's safe to run again.
"""

import csv
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from langfuse import Evaluation, Langfuse, propagate_attributes

from agent import config, tracing
from evals import runner

PREFIX = "firstline-"
UPLOADED_SETS = ("rules", *runner.REVIEW_SPLITS)
CHECKS = (
    "path_correct",
    "action_correct",
    "team_correct",
    "cause_correct",
    "retrieval_correct",
)
SUMMARY = (
    "path_accuracy",
    "action_accuracy",
    "team_accuracy",
    "kappa",
    "mistake_cost_chf",
    "cost_per_ticket_chf",
)
DECISION = ("path", "tool", "queue", "cause", "retrieved", "error")
SINCE = datetime(2026, 1, 1, tzinfo=UTC)  # how far back to look for an earlier upload


def dataset_name(set_name: str) -> str:
    return f"{PREFIX}{set_name}"


def dataset_item(ticket: dict, answer: dict) -> dict:
    """A ticket as a Langfuse dataset item: what the agent sees, and its answer.

    Items skip the client's trace mask, so the text is redacted here.
    """
    return {
        "id": ticket["id"],
        "input": {
            "id": ticket["id"],
            "text": tracing.redact(ticket["text"]),
            "requester": ticket["requester"],
        },
        "expected_output": {
            "paths": answer["paths"],
            "tools": answer["tools"],
            "queues": answer["queues"],
            "cause": answer["cause"],
        },
        "metadata": {"family": answer["family"], "difficulty": answer["difficulty"]},
    }


def upload_datasets(lf: Langfuse) -> int:
    """One dataset per practice set. Items are keyed by ticket, so this updates."""
    count = 0
    for name in UPLOADED_SETS:
        lf.create_dataset(
            name=dataset_name(name),
            description=f"FirstLine's {name} tickets and their answers",
            metadata={"labels_version": runner.labels_version()},
        )
        for ticket, answer in runner.load_any(name):
            lf.create_dataset_item(
                dataset_name=dataset_name(name), **dataset_item(ticket, answer)
            )
            count += 1
    return count


def item_scores(rows: dict[str, dict]) -> Callable[..., list[Evaluation]]:
    """Each ticket's scores, as our own scoring code marked them."""

    def score(**kwargs: Any) -> list[Evaluation]:
        row = rows[kwargs["input"]["id"]]
        checks = [
            Evaluation(
                name=check.removesuffix("_correct"),
                value=1.0 if row[check] else 0.0,
                data_type="BOOLEAN",
            )
            for check in CHECKS
            if row.get(check) is not None
        ]
        cost = Evaluation(
            name="mistake_chf", value=row["mistake_cost_chf"], data_type="NUMERIC"
        )
        return [*checks, cost]

    return score


def run_scores(summary: dict) -> Callable[..., list[Evaluation]]:
    """The run's own summary, so Langfuse shows the same numbers as the Scoreboard."""

    def score(**_: Any) -> list[Evaluation]:
        return [
            Evaluation(name=measure, value=summary[measure], data_type="NUMERIC")
            for measure in SUMMARY
            if summary.get(measure) is not None
        ]

    return score


def already_replayed(lf: Langfuse, run_id: str) -> bool:
    found = lf.api.experiments.list(from_start_time=SINCE, name=run_id, limit=1)
    return bool(found.data)


def replay(lf: Langfuse, run: dict) -> bool:
    """A saved run as a Langfuse experiment. Its task returns the saved decision."""
    if already_replayed(lf, run["id"]):
        return False
    rows = {row["id"]: row for row in run["tickets"]}
    items = [i for i in lf.get_dataset(dataset_name(run["set"])).items if i.id in rows]

    def task(*, item: Any, **_: Any) -> dict:
        return {key: rows[item.id][key] for key in DECISION}

    lf.run_experiment(
        name=run["id"],
        run_name=run["id"],
        description=f"{run['set']} with {run['model']}, replayed from a saved run",
        data=items,
        task=task,
        evaluators=[item_scores(rows)],
        run_evaluators=[run_scores(run["summary"])],
        metadata={
            "model": run["model"],
            "version": run["version"],
            "kb_version": run["kb_version"],
            "ran_at": run["date"],
            "rescored_from": run.get("rescored_from") or "",
        },
    )
    return True


def runs_to_replay() -> list[dict]:
    """The newest full run of each practice set. Held-out runs stay here."""
    newest = runner.to_rescore([], runner.load_runs())
    return [run for run in newest if run["set"] in UPLOADED_SETS]


def usage_rows() -> list[dict]:
    if not config.LOG_FILE.exists():
        return []
    with open(config.LOG_FILE, newline="") as f:
        return list(csv.DictReader(f))


def upload_usage(lf: Langfuse) -> int:
    """Each logged Assistant run as one trace, keyed by its time so it's sent once."""
    sent = 0
    for row in usage_rows():
        trace_id = lf.create_trace_id(seed=f"logs.csv {row['timestamp']}")
        if lf.api.observations.get_many(trace_id=trace_id, limit=1).data:
            continue
        output = {
            "path": row["decision_path"],
            "tool": row["tool_called"] or None,
            "queue": row["escalation_queue"] or None,
            "priority": row["priority"] or None,
            "confirmed": row["confirmed"] or None,
            "summary": row["diagnostic_summary"] or None,
        }
        metadata = {
            "logged_at": row["timestamp"],
            "retrieved": row["retrieved_units"],
            "response_time_sec": row["response_time_sec"],
        }
        with (
            propagate_attributes(
                trace_name="assistant", tags=["assistant", "from logs.csv"]
            ),
            lf.start_as_current_observation(
                trace_context={"trace_id": trace_id},
                name="assistant run",
                input={"query": row["query"]},
                output=output,
                metadata=metadata,
            ),
        ):
            sent += 1
    return sent


def main() -> None:
    """Upload the datasets, the saved runs and the usage log, then report."""
    if not tracing.enabled():
        raise SystemExit("Add LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to .env.")
    lf = tracing.client()
    items = upload_datasets(lf)
    replayed = [run["id"] for run in runs_to_replay() if replay(lf, run)]
    usage = upload_usage(lf)
    lf.flush()
    print(f"{items} dataset items in {len(UPLOADED_SETS)} datasets")
    names = ", ".join(replayed) or "none new"
    print(f"{len(replayed)} runs replayed as experiments: {names}")
    print(f"{usage} usage traces from logs.csv")


if __name__ == "__main__":
    main()
