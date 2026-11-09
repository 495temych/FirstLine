"""Usage statistics over the Assistant's real runs, read from the record: not synthetic
data and not an evaluation. Standalone: `uv run -m backend.stats`. Also served by the
API to the dashboard, next to (but clearly distinct from) the Scoreboard's evaluations.
"""

from backend import store
from backend.store import Run

PATHS = ["SELF_SERVE", "AUTO_FIX", "ESCALATE", "OUT_OF_SCOPE"]
MIN_ROWS_FOR_STABLE_RATE = 5


def automated(run: Run) -> bool:
    """Whether this run counts towards the automation rate.

    A run has its proposed `path`, and `answers`: what the person said at each gate,
    in order, as {"gate": "confirm_fix" | "confirm_ticket" | "self_serve",
    "approved": bool}. A run still paused at its first gate has no answers yet.
    """
    # The outcome counts, not the proposal: a declined fix or self-serve steps that
    # didn't help end with a technician. A run still waiting counts as not yet.
    first = run["answers"][0] if run["answers"] else None
    return (
        first is not None
        and first["approved"]
        and first["gate"] in ("confirm_fix", "self_serve")
    )


def summary_stats(runs: list[Run]) -> dict:
    """Count by path, automation rate and average response time by path. n is 0 and
    rates are None when there are no runs yet.
    """
    n = len(runs)
    by_path = {p: [r for r in runs if r["path"] == p] for p in PATHS}
    counts = {p: len(by_path[p]) for p in PATHS}
    pct = {p: (counts[p] / n * 100) if n else 0.0 for p in PATHS}

    in_scope = n - counts["OUT_OF_SCOPE"]
    automation_rate = (
        sum(automated(r) for r in runs) / in_scope * 100 if in_scope > 0 else None
    )

    avg_response_time_sec = {}
    for p in PATHS:
        times = [r["latency_ms"] / 1000 for r in by_path[p] if r["latency_ms"]]
        avg_response_time_sec[p] = (sum(times) / len(times)) if times else None

    return {
        "n": n,
        "counts": counts,
        "pct": pct,
        "automation_rate": automation_rate,
        "avg_response_time_sec": avg_response_time_sec,
        "low_sample": n < MIN_ROWS_FOR_STABLE_RATE,
    }


def print_summary(stats: dict) -> None:
    print(
        f"Live session stats — {stats['n']} Assistant runs from the record. "
        f"This is NOT an evaluation.\n"
    )

    if stats["n"] == 0:
        print("No runs yet. Triage some tickets in the Assistant first.")
        return

    if stats["low_sample"]:
        print(
            f"Sample size too small for a stable rate (< {MIN_ROWS_FOR_STABLE_RATE} "
            f"runs) — numbers below are illustrative only, not a reliable rate.\n"
        )

    print("Count and % by decision path:")
    for p in PATHS:
        print(f"  {p:12s} {stats['counts'][p]:3d}  ({stats['pct'][p]:.0f}%)")

    if stats["automation_rate"] is not None:
        print(f"\nAutomation rate, over runs in scope: {stats['automation_rate']:.0f}%")
    else:
        print("\nAutomation rate: n/a (no runs in scope yet)")

    print(
        "\nAgent response time (proxy for MTTR — measures decision latency, not full "
        "ticket resolution), avg by path:"
    )
    for p in PATHS:
        t = stats["avg_response_time_sec"][p]
        print(f"  {p:12s} {f'{t:.2f}s' if t is not None else 'n/a'}")


if __name__ == "__main__":
    print_summary(summary_stats(store.shared().runs()))
