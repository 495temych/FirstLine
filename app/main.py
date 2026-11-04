import os
import secrets
import sqlite3
from uuid import uuid4

import streamlit as st
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agent import config
from agent.graph import build_graph, initial_state
from app import explorer, scoreboard
from app import stats as _analyze_mod

st.set_page_config(
    page_title="L1 Support Agent — Limmatica AG",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Guard: API key ──────────────────────────────────────────────────────────────
if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error(
        "**ANTHROPIC_API_KEY not set.** Add it to `.env` or your shell environment."
    )
    st.stop()

# ── Graph + session state ───────────────────────────────────────────────────────


@st.cache_resource
def _get_graph():
    # check_same_thread=False: Streamlit runs each session on its own script thread and
    # SqliteSaver serializes access with an internal lock.
    return build_graph(
        SqliteSaver(sqlite3.connect(config.CHECKPOINT_DB, check_same_thread=False))
    )


GRAPH = _get_graph()

for key, default in [
    ("thread_id", uuid4().hex),  # one LangGraph thread per Streamlit session
    ("query_text", ""),
    ("use_retrieval", True),
    ("preview_ticket_id", "INC0000000"),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def _config() -> RunnableConfig:
    return {"configurable": {"thread_id": st.session_state.thread_id}}


# ── Callbacks ───────────────────────────────────────────────────────────────────
def _resume(answer: bool):
    """Answer the pending interrupt (confirm_fix / confirm_ticket / self_serve_wait)."""
    GRAPH.invoke(Command(resume=answer), _config())


def _set_preset(q: str):
    """Populate the text field with the preset query; user still clicks Analyze."""
    st.session_state.query_text = q


# ── Helpers ─────────────────────────────────────────────────────────────────────
_PATH_COLORS = {
    "SELF_SERVE": ("#1a7f37", "#dafbe1"),
    "AUTO_FIX": ("#0550ae", "#dbeafe"),
    "ESCALATE": ("#9a3412", "#fef3c7"),
    "OUT_OF_SCOPE": ("#555555", "#f0f0f0"),
    "NO_TOOLS": ("#6d28d9", "#ede9fe"),
}

_PATH_LABELS = {
    "NO_TOOLS": "NO TOOLS (RAG OFF)",
}


def _badge(path: str) -> str:
    fg, bg = _PATH_COLORS.get(path, ("#555", "#eee"))
    label = _PATH_LABELS.get(path, path)
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {fg}33;'
        f"padding:4px 12px;border-radius:5px;font-weight:700;"
        f'font-size:0.95em;letter-spacing:0.03em">{label}</span>'
    )


def _pending_callout(label: str) -> None:
    """Renders the 'awaiting confirmation' banner above Confirm/Cancel buttons."""
    st.markdown(
        f'<div style="background:#fffbeb;border:1px solid #f59e0b;border-radius:6px;'
        f'padding:10px 14px;margin:10px 0 8px 0;color:#78350f;">'
        f'<strong style="color:#78350f">&#9888;&#65039; Human-in-the-loop — awaiting '
        f"your decision</strong><br/>"
        f'<span style="font-size:0.9em;color:#78350f">{label}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _confirm_buttons(confirm_label: str) -> None:
    c1, c2, _ = st.columns([2, 2, 3])
    with c1:
        st.button(
            confirm_label,
            on_click=_resume,
            args=(True,),
            type="primary",
            use_container_width=True,
        )
    with c2:
        st.button("✗ Cancel", on_click=_resume, args=(False,), use_container_width=True)


def _ticket_submitted(tool_result: dict, queue: str) -> None:
    st.success(
        f"**Ticket {st.session_state.preview_ticket_id} submitted (simulated)**\n\n"
        f"Redirecting to ServiceNow... *(simulated)*\n\n"
        f"On-call technician for `{queue}` notified. SLA clock started."
    )
    st.caption(f"Timestamp: {tool_result['timestamp']}")


def _ticket_card(ticket: dict) -> None:
    ticket_id = st.session_state.preview_ticket_id
    with st.container(border=True):
        st.markdown("**Draft ServiceNow incident — pending confirmation**")
        st.markdown("")
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown(f"**Ticket ID**\n\n`{ticket_id}`")
            st.markdown(f"**Assignment group**\n\n`{ticket['queue']}`")
            st.markdown(f"**Priority**\n\n`{ticket['priority']}`")
        with col_r:
            if ticket["source"] == "decline":
                st.markdown(f"**Declined fix**\n\n`{ticket['declined_tool']}`")
                st.markdown(f"**Reason**\n\n{ticket['reason']}")
                st.markdown(f"**Diagnostic summary**\n\n{ticket['diagnostic_summary']}")
            else:
                st.markdown("**Requested by**\n\n`current.user`")
                st.markdown("**Category**\n\nIT Support / Endpoint")
                st.markdown(f"**Short description**\n\n{ticket['summary']}")

    _pending_callout(
        f"Confirm to submit this ticket to <strong>{ticket['queue']}</strong> "
        f"and notify the on-call technician."
    )


# ── Presets ─────────────────────────────────────────────────────────────────────
PRESETS = [
    # AUTO_FIX demos — single source
    "My VPN cert error persists, I've confirmed the gateway is correct and I was "
    "offline for a month",
    "Teams shows me as offline to everyone",
    "Floor 5 print queue is stuck, several people can't print",
    "I need Zoom installed but I don't have admin rights — it's listed in Company "
    "Portal",
    # ESCALATE demos — single source
    "I'm locked out of my account",
    "My external monitor isn't detected when docked",
    # Cross-document retrieval demos — one query pulls units from two different KB
    # documents in the same call (an issue playbook + a company-profile.md section,
    # or two issue playbooks together)
    "I've been locked out of my account twice already today",
    "My OneDrive won't sync one of my report files, I'm in Finance and we use # in "
    "filenames for versions",
    "My mapped network drive for Finance is gone since this morning, VPN is connected "
    "fine",
    "Outlook keeps asking me to sign in again and again today",
    # More single-document coverage
    "Wi-Fi keeps dropping for everyone near the open-plan area on floor 5, seems like "
    "too many devices on one access point",
    "My laptop has been unbearably slow since this weekend, fans running constantly",
    # OUT_OF_SCOPE demo
    "What's the weather like today?",
]


# ── Header ──────────────────────────────────────────────────────────────────────
st.title("L1 Support Agent")
st.caption("Limmatica AG · internal IT triage demo · powered by Claude")
st.divider()

triage_tab, scoreboard_tab, tickets_tab = st.tabs(["Triage", "Scoreboard", "Tickets"])

with scoreboard_tab:
    scoreboard.render()

with tickets_tab:
    explorer.render()

with triage_tab:
    # ── Global RAG toggle ───────────────────────────────────────────────────────────
    st.toggle("Use retrieval (RAG)", key="use_retrieval")
    st.markdown("")

    # ── Preset buttons ──────────────────────────────────────────────────────────────
    st.markdown("**Quick examples**")
    cols = st.columns(3)
    for i, preset in enumerate(PRESETS):
        cols[i % 3].button(
            preset,
            key=f"preset_{i}",
            on_click=_set_preset,
            args=(preset,),
            use_container_width=True,
        )

    st.markdown("---")

    # ── Free-text form ──────────────────────────────────────────────────────────────
    with st.form("query_form", clear_on_submit=False):
        query = st.text_area(
            "Or describe a custom issue:",
            value=st.session_state.query_text,
            placeholder=(
                "e.g.  My VPN keeps disconnecting since the migration last month"
            ),
            height=90,
        )
        submitted = st.form_submit_button("Analyze →", type="primary")

    # ── Execute triage ──────────────────────────────────────────────────────────────
    # A new input on the same thread starts a fresh run (initial_state resets every
    # field); any interrupt left pending by the previous query is abandoned.
    if submitted and query and query.strip():
        st.session_state.preview_ticket_id = (
            f"INC{secrets.randbelow(9000000) + 1000000}"
        )
        with st.spinner("Running triage…"):
            GRAPH.invoke(
                initial_state(query.strip(), st.session_state.use_retrieval), _config()
            )

    # ── Results ─────────────────────────────────────────────────────────────────────
    snapshot = GRAPH.get_state(_config())
    state = snapshot.values
    if state.get("path"):
        pending = snapshot.interrupts[0].value if snapshot.interrupts else None
        path = state["path"]
        decision = state["human_decision"]
        tool_result = state["tool_result"]
        st.divider()

        # 1 · Retrieval
        st.subheader("1 · Retrieval")
        units = state["retrieved"]
        if units:
            doc_names = {u["doc"] for u in units}
            if len(doc_names) > 1:
                st.caption(
                    "🔗 Matched units from **different KB documents** — cross-document "
                    "grounding."
                )

            for u in units:
                label = u["doc"] + (f" § {u['section']}" if u["section"] else "")
                badge = " · *reference section*" if u["section"] else ""
                with st.expander(
                    f"**{label}** — similarity {u['score']:.2f}{badge}", expanded=False
                ):
                    st.markdown(u["text"])

                highlights = u.get("highlights", [])
                if highlights:
                    st.markdown(f"**Why {label} matched — top passages:**")
                for h in highlights:
                    # Strip markdown characters for plain text in the highlight strip
                    clean = (
                        h["text"].replace("**", "").replace("`", "").replace("*", "")
                    )
                    st.markdown(
                        f'<div style="background:#fffbeb;border-left:3px solid #f59e0b;'
                        f"padding:5px 10px;margin:3px "
                        f'0;font-size:0.88em;line-height:1.4;color:#78350f;">'
                        f'<code style="color:#92400e;font-size:0.82em;background:none">'
                        f"{h['score']:.2f}</code>"
                        f"&ensp;{clean}</div>",
                        unsafe_allow_html=True,
                    )
        elif state["use_retrieval"]:
            st.info("No KB article matched above the confidence threshold.")
        else:
            st.info("RAG is off — no retrieval performed.")

        # 2 · Decision
        st.subheader("2 · Decision")
        st.markdown(_badge(path), unsafe_allow_html=True)
        st.markdown("")

        # 3 · Agent reasoning
        st.subheader("3 · Agent reasoning")
        st.markdown(state["reasoning"] or "_No reasoning returned._")

        # 4 · Action
        st.subheader("4 · Action")

        if path == "OUT_OF_SCOPE":
            st.info("Outside IT support scope — no action taken.")

        elif path == "NO_TOOLS":
            st.info(
                "RAG is off, so the agent had no tools and no company-specific "
                "grounding "
                "for this call — it could only respond with generic, ungrounded "
                "advice. "
                "No structured decision or action is available. Turn retrieval back on "
                "to see the grounded, tool-capable agent."
            )

        elif path == "SELF_SERVE":
            if pending and pending["kind"] == "self_serve":
                st.success(
                    "Steps are in the reasoning above — no operator action required."
                )
                c1, c2, _ = st.columns([2, 3, 1])
                with c1:
                    st.button(
                        "✓ This resolved it",
                        on_click=_resume,
                        args=(True,),
                        use_container_width=True,
                    )
                with c2:
                    st.button(
                        "This didn't resolve it — escalate to a technician.",
                        on_click=_resume,
                        args=(False,),
                        use_container_width=True,
                    )
            elif pending:  # confirm_ticket after "didn't resolve"
                _ticket_card(pending["ticket"])
                _confirm_buttons("✓ Confirm — submit ticket")
            elif decision.get("resolved"):
                st.success("Marked as resolved — no further action needed.")
            elif decision.get("ticket"):
                _ticket_submitted(tool_result, state["ticket_draft"]["queue"])
            else:
                st.warning("Escalation skipped by user. No ticket created.")

        elif path == "AUTO_FIX":
            tool_input = state["tool_input"] or {}
            with st.container(border=True):
                st.markdown("**Proposed automated fix**")
                st.markdown(f"Tool: `{state['tool_name'] or 'unknown'}`")
                for k, v in tool_input.items():
                    st.markdown(f"- `{k}`: `{v}`")

            if pending and pending["kind"] == "confirm_fix":
                _pending_callout("This fix will not run until you confirm below.")
                _confirm_buttons("✓ Confirm — run action")
            elif pending:  # confirm_ticket after a declined fix
                st.warning(
                    "**Automated fix declined — here's a pre-filled ticket.** Built "
                    "entirely "
                    "from the diagnosis above — no new model call."
                )
                _ticket_card(pending["ticket"])
                _confirm_buttons("✓ Send to ServiceNow")
            elif decision.get("fix"):
                st.success(f"**Action taken (simulated)**\n\n{tool_result['detail']}")
                st.caption(f"Timestamp: {tool_result['timestamp']}")
            elif decision.get("ticket"):
                _ticket_submitted(tool_result, state["ticket_draft"]["queue"])
            else:
                st.warning(
                    "Escalation skipped by operator. No fix applied, no ticket created."
                )

        elif path == "ESCALATE":
            if pending:
                _ticket_card(pending["ticket"])
                _confirm_buttons("✓ Confirm — submit ticket")
            elif decision.get("ticket"):
                _ticket_submitted(tool_result, state["tool_input"]["queue"])
            else:
                st.warning("Escalation skipped by user. No ticket created.")

    # ── Stats: live session usage ──────────────────────────────────────────────
    st.divider()

    with st.expander(
        "📊 Live session stats — from logs.csv (real queries run through this app)",
        expanded=False,
    ):
        live = _analyze_mod.summary_stats()
        st.caption(
            "Real usage logged by this app during testing/demo — not an evaluation. "
            "logs.csv starts empty; every row here came from an actual query "
            "submitted above. Run standalone: `uv run -m app.stats`."
        )

        if live["n"] == 0:
            st.info("No queries logged yet — run a query above to populate logs.csv.")
        else:
            if live["low_sample"]:
                st.warning(
                    f"Only {live['n']} quer{'y' if live['n'] == 1 else 'ies'} logged — "
                    f"sample size too small for a stable rate. Numbers below are "
                    f"illustrative "
                    f"only, not a reliable rate."
                )

            c1, c2 = st.columns(2)
            c1.metric("Total logged queries", live["n"])
            c2.metric(
                "Automation rate (SELF_SERVE+AUTO_FIX / non-OUT_OF_SCOPE)",
                f"{live['automation_rate']:.0f}%"
                if live["automation_rate"] is not None
                else "n/a",
            )

            st.markdown("**Count and % by decision path**")
            st.dataframe(
                [
                    {
                        "Path": p,
                        "Count": live["counts"][p],
                        "%": f"{live['pct'][p]:.0f}%",
                    }
                    for p in _analyze_mod.PATHS
                ],
                width="stretch",
                hide_index=True,
            )

            st.markdown(
                "**Agent response time** (proxy for MTTR — measures decision latency, "
                "not full ticket resolution), avg by path"
            )
            st.dataframe(
                [
                    {
                        "Path": p,
                        "Avg response time (s)": (
                            f"{live['avg_response_time_sec'][p]:.2f}"
                            if live["avg_response_time_sec"][p] is not None
                            else "n/a"
                        ),
                    }
                    for p in _analyze_mod.PATHS
                ],
                width="stretch",
                hide_index=True,
            )
