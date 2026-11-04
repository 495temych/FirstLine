"""The Scoreboard tab: saved evaluations, read from disk. No model calls."""

import streamlit as st

from evals import runner, scoring


def _money(value: float | None) -> str:
    return "unknown" if value is None else f"${value:.4f}"


def _row(run: dict) -> dict:
    s = run["summary"]
    return {
        "Date": run["date"],
        "Set": f"{run['set']} (tiny)" if run["tiny"] else run["set"],
        "Model": run["model"],
        "Version": run["version"],
        "Tickets": s["n"],
        "Path": f"{s['path_accuracy']:.0%}",
        "Action": f"{s['action_accuracy']:.0%}",
        "Retrieval": f"{s['retrieval_accuracy']:.0%}",
        "Automation": f"{s['automation_rate']:.0%}",
        "Mistakes (CHF)": f"{s['mistake_cost_chf']:,}",
        "Cost per ticket": _money(s["cost_per_ticket_usd"]),
        "Time per ticket": f"{s['time_per_ticket_sec']:.1f}s",
    }


def _ticket_row(t: dict) -> dict:
    return {
        "": "✓" if t["action_correct"] else "✗",
        "Ticket": t["id"],
        "Text": t["text"],
        "Difficulty": t["difficulty"],
        "Expected": "/".join(t["expected_paths"]),
        "Agent": t["path"],
        "Expected tool or queue": ", ".join(t["expected_tools"] + t["expected_queues"]),
        "Agent's tool or queue": t["queue"] or t["tool"] or "",
        "Mistake (CHF)": t["mistake_cost_chf"],
        "Error": t["error"] or "",
    }


def _difficulty_row(level: str, s: dict) -> dict:
    return {
        "Difficulty": level,
        "Tickets": s["n"],
        "Path": f"{s['path_accuracy']:.0%}",
        "Action": f"{s['action_accuracy']:.0%}",
        "Mistakes (CHF)": f"{s['mistake_cost_chf']:,}",
    }


def render() -> None:
    """Draw the tab."""
    runs = runner.load_runs()
    if not runs:
        st.info("No evaluations yet. Run `uv run -m evals --tiny` to create one.")
        return

    st.dataframe([_row(r) for r in runs], width="stretch", hide_index=True)
    st.caption(
        f"Mistake costs are assumptions: CHF {scoring.COST_SECURITY:,} for a routine "
        f"fix on a possible compromise, CHF {scoring.COST_WRONG} for a wrong fix, "
        f"needless escalation or declined request, and CHF {scoring.COST_MINOR} for "
        "the wrong tool or queue."
    )

    chosen = st.selectbox("Open an evaluation", [r["id"] for r in runs])
    run = next(r for r in runs if r["id"] == chosen)
    st.dataframe(
        [_difficulty_row(k, v) for k, v in run["by_difficulty"].items()],
        width="stretch",
        hide_index=True,
    )
    st.dataframe(
        [_ticket_row(t) for t in run["tickets"]], width="stretch", hide_index=True
    )
