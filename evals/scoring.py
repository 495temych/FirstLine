"""Scores one evaluated ticket against its answer. Plain code, no model."""

SECURITY_QUEUE = "SEC-INCIDENT"
AUTOMATED = {"AUTO_FIX", "SELF_SERVE"}

# Assumptions in CHF: 2 hours at CHF 60 for a technician, half that for a reroute.
COST_SECURITY = 2000
COST_WRONG = 120
COST_MINOR = 60


def action_correct(
    answer: dict, path: str, tool: str | None, queue: str | None
) -> bool:
    """The path is accepted, and so is its tool or queue, if the answer names one."""
    if path not in answer["paths"]:
        return False
    if path == "AUTO_FIX" and answer["tools"]:
        return tool in answer["tools"]
    if path == "ESCALATE" and answer["queues"]:
        return queue in answer["queues"]
    return True


def mistake_cost(answer: dict, path: str, tool: str | None, queue: str | None) -> int:
    """What this decision would have cost, in CHF."""
    if path in answer["paths"]:
        return 0 if action_correct(answer, path, tool, queue) else COST_MINOR
    if path in AUTOMATED and "ESCALATE" in answer["paths"]:
        return COST_SECURITY if SECURITY_QUEUE in answer["queues"] else COST_WRONG
    if path in {"ESCALATE", "OUT_OF_SCOPE"}:
        return COST_WRONG
    return COST_MINOR


def retrieval_correct(answer: dict, retrieved: list[str]) -> bool:
    """The top unit is an expected one. With none expected, nothing should match."""
    top = retrieved[0] if retrieved else None
    return top in answer["units"] if answer["units"] else top is None


def _share(rows: list[dict], key: str) -> float:
    return sum(r[key] for r in rows) / len(rows)


def _average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize(rows: list[dict]) -> dict:
    """The Scoreboard's measures for a list of scored tickets."""
    in_scope = [r for r in rows if r["path"] != "OUT_OF_SCOPE"]
    automated = [r for r in in_scope if r["path"] in AUTOMATED]
    costs = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]
    return {
        "n": len(rows),
        "path_accuracy": _share(rows, "path_correct"),
        "action_accuracy": _share(rows, "action_correct"),
        "retrieval_accuracy": _share(rows, "retrieval_correct"),
        "automation_rate": len(automated) / len(in_scope) if in_scope else 0.0,
        "mistake_cost_chf": sum(r["mistake_cost_chf"] for r in rows),
        "cost_per_ticket_usd": _average(costs) if len(costs) == len(rows) else None,
        "time_per_ticket_sec": _average([r["time_sec"] for r in rows]),
        "failed": sum(r["error"] is not None for r in rows),
    }


def by_difficulty(rows: list[dict]) -> dict:
    """Accuracy and mistake cost for each difficulty."""
    levels = sorted({r["difficulty"] for r in rows})
    return {
        level: summarize([r for r in rows if r["difficulty"] == level])
        for level in levels
    }
