"""The Tickets tab: the development tickets and their labels, read from disk.

No model calls. The held-out set stays out of the app, because it's the exam.
"""

import json

import streamlit as st

from agent import config
from app import stats
from evals import runner

DIFFICULTIES = ["routine", "hard", "records"]
TABLE_HEIGHT = 300  # keeps the selected ticket on screen, just below the table
LOCKOUT_LIMIT = 2  # SEC-04: this many lockouts in 24 hours is a possible compromise


def latest_results(runs: list[dict]) -> dict[str, dict]:
    """Each ticket's newest result. `runs` is newest first."""
    latest: dict[str, dict] = {}
    for run in runs:
        if run["set"] == "dev":
            for ticket in run["tickets"]:
                latest.setdefault(ticket["id"], ticket)
    return latest


def _matches(
    answer: dict, path: str | None, difficulty: str | None, to_check: bool
) -> bool:
    return (
        (path is None or path in answer["paths"])
        and (difficulty is None or answer["difficulty"] == difficulty)
        and (not to_check or bool(answer.get("review")))
    )


def _mark(result: dict | None) -> str:
    if result is None:
        return "not run"
    return "✓" if result["action_correct"] else "✗"


def _target(answer: dict) -> str:
    return ", ".join(answer["tools"] + answer["queues"]) or "any"


def _row(ticket: dict, answer: dict, result: dict | None) -> dict:
    return {
        "Ticket": ticket["id"],
        "Check": "⚠" if answer.get("review") else "",
        "Latest run": _mark(result),
        "Text": ticket["text"],
        "Expected": " or ".join(answer["paths"]),
        "Tool or queue": _target(answer),
        "Difficulty": answer["difficulty"],
    }


def _facts(title: str, facts: dict[str, str]) -> None:
    st.markdown(f"**{title}**")
    st.markdown("\n".join(f"- {name}: {value}" for name, value in facts.items()))


def _expected(answer: dict) -> dict[str, str]:
    facts = {
        "Path": " or ".join(answer["paths"]),
        "Tool or queue": _target(answer),
        "KB units": ", ".join(answer["units"]) or "none",
    }
    return facts | ({"Note": answer["note"]} if answer["note"] else {})


def _requester(user: dict) -> dict[str, str]:
    device = user["device"]
    lockouts = user["lockouts_24h"]
    return {
        "Name": f"{user['name']} ({user['id']})",
        "Team": f"{user['department']}, floor {user['floor']}",
        "Device": (
            f"{device['id']}, {device['model']}, image {device['image']}, "
            f"age {device['age_years']}, battery {device['battery_health']}%"
        ),
        "Lockouts in 24 hours": (
            f":red[**{lockouts}**]" if lockouts >= LOCKOUT_LIMIT else str(lockouts)
        ),
        "Groups": ", ".join(user["groups"]) or "none",
        "Recent tickets": "; ".join(user["recent_tickets"]) or "none",
    }


def _agent(result: dict | None) -> str:
    if result is None:
        return "Latest run: this ticket isn't in a saved evaluation yet."
    if result["error"]:
        return f"Latest run: ✗ failed with {result['error']}"
    action = result["queue"] or result["tool"]
    chose = f"{result['path']}, {action}" if action else result["path"]
    return f"Latest run: {_mark(result)} the agent chose {chose}."


def _show_ticket(ticket: dict, answer: dict, user: dict, result: dict | None) -> None:
    with st.container(border=True):
        st.subheader(ticket["text"], anchor=False)
        st.caption(f"{ticket['id']} · {answer['difficulty']}")
        if answer.get("review"):
            st.warning(answer["review"], title="Check this label")
        expected, requester = st.columns(2)
        with expected:
            _facts("Expected", _expected(answer))
        with requester:
            _facts("Requester", _requester(user))
            st.caption("The agent can't see these records yet.")
        st.markdown(_agent(result))


@st.fragment
def render() -> None:
    """Draw the tab. It reruns alone, so browsing never touches Triage."""
    pairs = runner.load_set("dev")
    latest = latest_results(runner.load_runs())
    users = {u["id"]: u for u in json.loads(config.USERS_FILE.read_text())}

    filters = st.container(horizontal=True, vertical_alignment="bottom")
    with filters:
        path = st.pills("Path", stats.PATHS, key="tickets_path")
        difficulty = st.pills("Difficulty", DIFFICULTIES, key="tickets_difficulty")
        to_check = st.toggle("Only labels to check", key="tickets_to_check")

    shown = [
        (ticket, answer)
        for ticket, answer in pairs
        if _matches(answer, path, difficulty, to_check)
    ]
    st.caption(f"{len(shown)} of {len(pairs)} development tickets. Select a row.")
    if not shown:
        st.info("No tickets match these filters.")
        return

    event = st.dataframe(
        [_row(t, a, latest.get(t["id"])) for t, a in shown],
        height=TABLE_HEIGHT,
        hide_index=True,
        column_config={"Text": st.column_config.TextColumn(width="medium")},
        on_select="rerun",
        selection_mode="single-row",
        key=f"tickets_{path}_{difficulty}_{to_check}",
        alt="Development tickets with their expected path and latest result",
    )
    rows = event.selection.rows
    ticket, answer = shown[rows[0] if rows else 0]
    _show_ticket(ticket, answer, users[ticket["requester"]], latest.get(ticket["id"]))
