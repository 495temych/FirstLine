"""Smoke tests of the Streamlit app, with a stub model and temporary files."""

import csv
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from agent import config, graph
from agent.tests.fakes import UNIT, FakeLLM, text, tool
from app import explorer, stats
from evals import runner

MAIN = str(Path(__file__).parent.parent / "main.py")
AUTO_FIX = [text("Reset the profile."), tool("reset_vpn_profile", username="a.b")]
ESCALATE = [
    text("Needs review."),
    tool(
        "create_escalation_ticket",
        queue="SEC-INCIDENT",
        summary="Repeat lockout",
        priority="P2-High",
    ),
]
SELF_SERVE = [text("1. Reseat the cable.\nPath chosen: SELF_SERVE")]
OUT_OF_SCOPE = [text("OUT_OF_SCOPE: not an IT question.")]


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Start the app against temporary files, with every model stubbed."""
    log = tmp_path / "logs.csv"
    with open(log, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=graph.LOG_FIELDS)
        writer.writeheader()
        writer.writerow({"decision_path": "AUTO_FIX", "response_time_sec": "1.5"})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "CHECKPOINT_DB", tmp_path / "checkpoints.sqlite")
    monkeypatch.setattr(graph, "LOG_FILE", log)
    monkeypatch.setattr(stats, "LOG_FILE", log)
    monkeypatch.setattr(graph, "retrieve", lambda q: [UNIT])
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path / "runs")
    st.cache_resource.clear()
    st.cache_data.clear()
    yield AppTest.from_file(MAIN, default_timeout=30)
    st.cache_resource.clear()
    st.cache_data.clear()


def stub_triage(text, use_retrieval):
    return {
        "path": "AUTO_FIX",
        "retrieved": [],
        "tool_name": "clear_teams_cache",
        "tool_input": {"username": "a.b"},
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "response_time_sec": 1.0,
    }


def analyze(at, monkeypatch, blocks):
    """Submit one ticket that the stub model answers with these blocks."""
    llm = FakeLLM(blocks)
    monkeypatch.setattr(graph, "_get_llm", lambda: llm)
    at.run()
    at.text_area[0].set_value("My ticket")
    press(at, "Analyze")
    return at


def press(at, label):
    next(b for b in at.button if label in b.label).click()
    at.run()


def page_text(at):
    parts = [m.value for m in at.markdown]
    parts += [m.value for m in at.success]
    parts += [m.value for m in at.info]
    parts += [m.value for m in at.warning]
    return "\n".join(parts)


def test_the_app_loads_and_reads_the_log(app):
    app.run()
    assert not app.exception
    assert app.title[0].value == "L1 Support Agent"
    assert [t.label for t in app.tabs] == ["Triage", "Scoreboard", "Tickets"]
    assert any("Total logged queries" in m.label for m in app.metric)


def test_the_scoreboard_says_when_there_are_no_runs(app):
    app.run()
    assert "No evaluations yet" in app.tabs[1].info[0].value


def test_the_scoreboard_shows_a_saved_run(app, monkeypatch):
    monkeypatch.setattr(runner, "run_triage", stub_triage)
    runner.save_run(runner.evaluate("dev", tiny=True))
    app.run()
    assert not app.exception
    assert len(app.tabs[1].dataframe) == 3
    assert "assumptions" in app.tabs[1].caption[0].value


def test_tickets_shows_the_development_set_and_the_first_ticket(app):
    app.run()
    tab = app.tabs[2]
    table = tab.dataframe[0].value
    assert len(table) == 25
    assert table["Ticket"].str.startswith("T-").all()
    assert (table["Latest run"] == "not run").all()
    assert tab.subheader[0].value == "My VPN keeps disconnecting"
    assert "Check this label" in tab.warning[0].title
    assert "reset_vpn_profile" in "".join(m.value for m in tab.markdown)


def test_tickets_can_be_filtered(app):
    app.run()
    app.button_group(key="tickets_difficulty").set_value("records").run()
    assert len(app.tabs[2].dataframe[0].value) == 5
    app.button_group(key="tickets_path").set_value("OUT_OF_SCOPE").run()
    assert "No tickets match" in app.tabs[2].info[0].value


def test_tickets_can_show_only_the_labels_to_check(app):
    app.run()
    app.toggle(key="tickets_to_check").set_value(True).run()
    table = app.tabs[2].dataframe[0].value
    assert list(table["Ticket"]) == ["T-001", "T-006", "T-017", "T-018"]


def test_tickets_shows_the_latest_result(app, monkeypatch):
    monkeypatch.setattr(runner, "run_triage", stub_triage)
    runner.save_run(runner.evaluate("dev", tiny=True))
    app.run()
    table = app.tabs[2].dataframe[0].value.set_index("Ticket")
    assert table.loc["T-003", "Latest run"] == "✗"
    assert table.loc["T-001", "Latest run"] == "not run"


def test_latest_results_keeps_the_newest_and_skips_the_held_out_set():
    runs = [
        {"set": "held_out", "tickets": [{"id": "H-001"}]},
        {"set": "dev", "tickets": [{"id": "T-001", "action_correct": True}]},
        {"set": "dev", "tickets": [{"id": "T-001", "action_correct": False}]},
    ]
    assert explorer.latest_results(runs) == {
        "T-001": {"id": "T-001", "action_correct": True}
    }


def test_a_missing_key_stops_the_app_with_a_message(app, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    app.run()
    assert "ANTHROPIC_API_KEY not set" in app.error[0].value


def test_auto_fix_runs_only_after_confirmation(app, monkeypatch):
    at = analyze(app, monkeypatch, AUTO_FIX)
    assert not at.exception
    assert "AUTO_FIX" in page_text(at)
    assert "Action taken" not in page_text(at)
    press(at, "Confirm")
    assert "Action taken (simulated)" in page_text(at)


def test_a_declined_fix_gives_a_pre_filled_ticket(app, monkeypatch):
    at = analyze(app, monkeypatch, AUTO_FIX)
    press(at, "Cancel")
    assert not at.exception
    assert "pre-filled ticket" in page_text(at)


def test_escalate_asks_before_creating_a_ticket(app, monkeypatch):
    at = analyze(app, monkeypatch, ESCALATE)
    assert not at.exception
    assert "ESCALATE" in page_text(at)
    press(at, "Cancel")
    assert "No ticket created" in page_text(at)


def test_self_serve_can_be_marked_resolved(app, monkeypatch):
    at = analyze(app, monkeypatch, SELF_SERVE)
    assert not at.exception
    assert "SELF_SERVE" in page_text(at)
    press(at, "This resolved it")
    assert "Marked as resolved" in page_text(at)


def test_out_of_scope_takes_no_action(app, monkeypatch):
    at = analyze(app, monkeypatch, OUT_OF_SCOPE)
    assert not at.exception
    assert "no action taken" in page_text(at)
