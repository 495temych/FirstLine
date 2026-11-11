"""Scores evaluated tickets against their answers. Plain code, no model."""

from collections import Counter
from math import sqrt

SECURITY_QUEUE = "SEC-INCIDENT"
AUTOMATED = {"AUTO_FIX", "SELF_SERVE"}

# Assumptions in CHF: 2 hours at CHF 60 for a technician, half that for a reroute.
COST_SECURITY = 2000
COST_WRONG = 120
COST_MINOR = 60
USD_TO_CHF = 0.80  # an assumption, for showing model cost in francs
Z_95 = 1.96  # for a 95% margin of error
PATHS = ("SELF_SERVE", "AUTO_FIX", "ESCALATE", "OUT_OF_SCOPE")


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


def sec04_failure(answer: dict, path: str) -> bool:
    """A routine fix or steps where SEC-04 says security must look. Must be zero."""
    return SECURITY_QUEUE in answer["queues"] and path in AUTOMATED


def retrieval_correct(answer: dict, retrieved: list[str]) -> bool:
    """The top unit is an expected one. With none expected, nothing should match."""
    top = retrieved[0] if retrieved else None
    return top in answer["units"] if answer["units"] else top is None


def team_correct(answer: dict, path: str, queue: str | None) -> bool | None:
    """Did it reach the right team? None if the answer names no team."""
    if not answer["queues"]:
        return None
    return path == "ESCALATE" and queue in answer["queues"]


def cause_correct(answer: dict, cause: str | None) -> bool | None:
    """Did it name the labelled cause? None if the ticket has no labelled cause."""
    expected = answer.get("cause")
    if expected is None:
        return None
    return (cause or "").strip().casefold() == expected.casefold()


def expected_path(answer: dict, path: str) -> str:
    """The one expected path: the agent's, if accepted, or else the first accepted."""
    return path if path in answer["paths"] else answer["paths"][0]


def score_decision(
    answer: dict, path: str, tool: str | None, queue: str | None
) -> dict:
    """The measures any decision-maker gets, whether the agent or a yardstick."""
    return {
        "family": answer["family"],
        "expected_path": expected_path(answer, path),
        "path": path,
        "path_correct": path in answer["paths"],
        "action_correct": action_correct(answer, path, tool, queue),
        "team_correct": team_correct(answer, path, queue),
        "mistake_cost_chf": mistake_cost(answer, path, tool, queue),
        "sec04_failure": sec04_failure(answer, path),
    }


def margin(share: float, n: int) -> float:
    """The 95% margin of error on a share of n tickets, by the Wilson interval."""
    if n == 0:
        return 0.0
    spread = share * (1 - share) / n + Z_95**2 / (4 * n**2)
    return Z_95 * sqrt(spread) / (1 + Z_95**2 / n)


def _share(rows: list[dict], key: str) -> float:
    return sum(r[key] for r in rows) / len(rows)


def _share_or_none(rows: list[dict], key: str) -> float | None:
    """The share among tickets where this measure applies."""
    scored = [r for r in rows if r.get(key) is not None]
    return _share(scored, key) if scored else None


def _average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def confusion(rows: list[dict]) -> dict[str, dict[str, int]]:
    """How many tickets of each expected path got each chosen path."""
    pairs = Counter((r["expected_path"], r["path"]) for r in rows)
    return {
        expected: {chosen: pairs[(expected, chosen)] for chosen in PATHS}
        for expected in PATHS
    }


def per_path(rows: list[dict]) -> dict[str, dict]:
    """Precision and recall for each path. None where there's nothing to divide by."""
    measures = {}
    for path in PATHS:
        right = sum(r["path"] == path == r["expected_path"] for r in rows)
        chosen = sum(r["path"] == path for r in rows)
        actual = sum(r["expected_path"] == path for r in rows)
        measures[path] = {
            "precision": right / chosen if chosen else None,
            "recall": right / actual if actual else None,
            "n": actual,
        }
    return measures


def balanced_accuracy(rows: list[dict]) -> float | None:
    """Path accuracy averaged over the expected paths, so a model that escalates
    everything can't hide behind a set that's mostly escalations.
    """
    shares = [
        _share(group, "path_correct")
        for path in PATHS
        if (group := [r for r in rows if r["expected_path"] == path])
    ]
    return _average(shares)


def percentile(values: list[float], q: float) -> float | None:
    """The value below which a share q of them fall, by the nearest rank."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(int(q * len(ordered)), len(ordered) - 1)]


def cohens_kappa(rows: list[dict]) -> float | None:
    """Agreement beyond chance. A constant answer scores 0."""
    n = len(rows)
    if not n:
        return None
    observed = sum(r["path"] == r["expected_path"] for r in rows) / n
    chance = sum(
        sum(r["path"] == path for r in rows)
        * sum(r["expected_path"] == path for r in rows)
        for path in PATHS
    ) / (n * n)
    return (observed - chance) / (1 - chance) if chance < 1 else 0.0


def decisions(rows: list[dict]) -> dict:
    """The measures shared by the agent and the yardsticks."""
    n = len(rows)
    path, action = _share(rows, "path_correct"), _share(rows, "action_correct")
    team_rows = [r for r in rows if r["team_correct"] is not None]
    team = _share_or_none(rows, "team_correct")
    return {
        "n": n,
        "path_accuracy": path,
        "path_margin": margin(path, n),
        "action_accuracy": action,
        "action_margin": margin(action, n),
        "team_accuracy": team,
        "team_margin": None if team is None else margin(team, len(team_rows)),
        "mistake_cost_chf": sum(r["mistake_cost_chf"] for r in rows),
        "sec04_failures": sum(r.get("sec04_failure", False) for r in rows),
        "kappa": cohens_kappa(rows),
    }


def summarize(rows: list[dict]) -> dict:
    """The Scoreboard's measures for a list of scored tickets."""
    in_scope = [r for r in rows if r["path"] != "OUT_OF_SCOPE"]
    automated = [r for r in in_scope if r["path"] in AUTOMATED]
    costs = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]
    usd = _average(costs) if len(costs) == len(rows) else None
    return {
        **decisions(rows),
        "cause_accuracy": _share_or_none(rows, "cause_correct"),
        "retrieval_accuracy": _share(rows, "retrieval_correct"),
        "automation_rate": len(automated) / len(in_scope) if in_scope else 0.0,
        "cost_per_ticket_usd": usd,
        "cost_per_ticket_chf": None if usd is None else usd * USD_TO_CHF,
        "time_per_ticket_sec": _average([r["time_sec"] for r in rows]),
        "time_p50_sec": percentile([r["time_sec"] for r in rows], 0.5),
        "time_p90_sec": percentile([r["time_sec"] for r in rows], 0.9),
        "balanced_accuracy": balanced_accuracy(rows),
        "failed": sum(r["error"] is not None for r in rows),
        "invalid": sum(r["error"] is not None or r.get("invalid", False) for r in rows),
    }


def by_family(rows: list[dict]) -> dict:
    """The same measures for each family."""
    return {
        family: summarize([r for r in rows if r["family"] == family])
        for family in sorted({r["family"] for r in rows})
    }


def by_difficulty(rows: list[dict]) -> dict:
    """Accuracy and mistake cost for each difficulty."""
    levels = sorted({r["difficulty"] for r in rows})
    return {
        level: summarize([r for r in rows if r["difficulty"] == level])
        for level in levels
    }
