"""The rules in code, attacked with a stub model that proposes what it shouldn't."""

from typing import cast

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent import graph as g
from agent import records, rules, tools
from agent.tests.fakes import UNIT, FakeLLM, escalate, fix, steps

LOCKOUT = {**UNIT, "doc": "account-lockout", "text": "Lockout playbook"}
POLICY = {**UNIT, "doc": "sec-04-account-lockout", "text": "SEC-04"}
PRINTING = {**UNIT, "doc": "printing", "text": "Printing playbook"}


def user(lockouts: int) -> dict:
    return {"id": "a.user", "lockouts_24h": lockouts, "device": {"id": "LT-AUSER"}}


def proposal(path="AUTO_FIX", tool=None, **tool_input) -> rules.Proposal:
    return {"path": path, "tool_name": tool, "tool_input": tool_input or None}


@pytest.fixture
def run(monkeypatch):
    """Start a run with a stub model and given search results, and count tool runs."""
    ran: list[str] = []
    real_dispatch = tools.dispatch

    def dispatch(name, inp):
        ran.append(name)
        return real_dispatch(name, inp)

    monkeypatch.setattr(g.tools, "dispatch", dispatch)

    def start(blocks, retrieved, requester, mode: rules.Mode = "queue"):
        monkeypatch.setattr(g, "retrieve", lambda q: retrieved)
        llm = FakeLLM(blocks)
        monkeypatch.setattr(g, "_get_llm", lambda: llm)
        graph = g.build_graph(InMemorySaver())
        config: RunnableConfig = {"configurable": {"thread_id": "t"}}
        out = graph.invoke(g.initial_state("q", True, requester, mode), config)
        return graph, config, out, ran

    return start


# ── SEC-04 ──────────────────────────────────────────────────────────────────────
def test_an_unlock_for_two_lockouts_never_reaches_the_fix_gate(run):
    graph, config, out, ran = run(
        fix("unlock_ad_account", username="a.user"), [LOCKOUT], user(2)
    )
    gate = out["__interrupt__"][0].value
    assert gate["kind"] == "confirm_ticket"
    assert gate["ticket"]["queue"] == "SEC-INCIDENT"
    assert gate["ticket"]["priority"] == "P2-High"
    assert out["rule"]["rule"] == "SEC-04"
    assert out["rule"]["proposed"]["tool_name"] == "unlock_ad_account"
    out = graph.invoke(Command(resume=True), config)
    assert ran == ["create_escalation_ticket"]  # the unlock never ran


def test_an_unlock_is_overridden_even_when_search_found_nothing(run):
    _, _, out, _ = run(fix("unlock_ad_account", username="a.user"), [], user(3))
    assert out["tool_input"]["queue"] == "SEC-INCIDENT"


def test_calling_the_lockout_something_else_doesnt_skip_sec04(run):
    blocks = steps("Wait 15 minutes and sign in again.")
    _, _, out, _ = run(blocks, [POLICY], user(2))
    assert out["path"] == "ESCALATE"
    assert out["tool_input"]["queue"] == "SEC-INCIDENT"
    assert out["rule"]["proposed"]["path"] == "SELF_SERVE"


def test_a_wrong_queue_for_a_repeat_lockout_moves_to_security(run):
    _, _, out, _ = run(escalate("DESK-SUPPORT"), [LOCKOUT], user(2))
    assert out["tool_input"]["queue"] == "SEC-INCIDENT"
    assert out["rule"]["rule"] == "SEC-04"


def test_an_escalation_to_security_is_left_alone(run):
    _, _, out, _ = run(escalate("SEC-INCIDENT"), [LOCKOUT], user(2))
    assert out["rule"] is None


def test_one_lockout_keeps_the_routine_unlock(run):
    _, _, out, _ = run(fix("unlock_ad_account", username="a.user"), [LOCKOUT], user(1))
    assert out["__interrupt__"][0].value["kind"] == "confirm_fix"
    assert out["rule"] is None


def test_two_lockouts_and_a_printer_ticket_is_not_overridden(run):
    _, _, out, _ = run(fix("restart_print_spooler"), [PRINTING], user(2))
    assert out["tool_name"] == "restart_print_spooler"
    assert out["rule"] is None


def test_no_requester_behaves_as_before(run):
    _, _, out, _ = run(fix("unlock_ad_account", username="a.user"), [LOCKOUT], None)
    assert out["path"] == "AUTO_FIX"
    assert out["rule"] is None


# ── Sensitive fixes ─────────────────────────────────────────────────────────────
def test_a_sensitive_fix_in_the_assistant_becomes_a_ticket(run):
    graph, config, out, ran = run(
        fix("restart_print_spooler"), [PRINTING], user(0), mode="assistant"
    )
    gate = out["__interrupt__"][0].value
    assert gate["kind"] == "confirm_ticket"
    assert gate["ticket"]["queue"] == "DESK-SUPPORT"
    assert "restart_print_spooler" in gate["ticket"]["summary"]
    assert out["rule"]["rule"] == "Sensitive fix"
    graph.invoke(Command(resume=True), config)
    assert ran == ["create_escalation_ticket"]


def test_a_routine_fix_in_the_assistant_is_left_alone(run):
    _, _, out, _ = run(fix("clear_teams_cache"), [UNIT], user(0), mode="assistant")
    assert out["__interrupt__"][0].value["kind"] == "confirm_fix"
    assert out["rule"] is None


def test_a_sensitive_fix_in_the_queue_waits_for_the_technician(run):
    _, _, out, _ = run(fix("restart_print_spooler"), [PRINTING], user(0))
    assert out["__interrupt__"][0].value["kind"] == "confirm_fix"
    assert out["rule"] is None


def test_sec04_wins_over_the_sensitive_fix_rule():
    decision, override = rules.enforce(
        proposal(tool="unlock_ad_account"), user(2), [LOCKOUT], "assistant"
    )
    assert override is not None
    assert override["rule"] == "SEC-04"
    assert cast(dict, decision["tool_input"])["queue"] == "SEC-INCIDENT"


def test_every_rule_is_explained():
    assert rules.EXPLANATIONS.keys() == rules.RULES.keys()


# ── What the model sees ─────────────────────────────────────────────────────────
def test_the_model_sees_the_record_but_not_the_name_or_email():
    record = records.requester("s.keller")
    assert record is not None
    message = g.build_user_message("Locked out", [UNIT], True, record)
    assert "lockout" not in message  # code reads the count, the model doesn't
    assert f"device id: {record['device']['id']}" in message
    assert record["name"] not in message
    other = records.requester("a.hussain")
    assert other is not None
    message = g.build_user_message("Locked out", [UNIT], True, other)
    assert other["name"] not in message
    assert other["email"] not in message


def test_without_a_requester_the_message_is_unchanged():
    assert g.build_user_message("q", [UNIT], True, None) == g.build_user_message(
        "q", [UNIT], True
    )
    assert not g.build_user_message("q", [UNIT], True).startswith("Requester")


def test_an_unknown_requester_is_refused():
    with pytest.raises(KeyError):
        records.requester("nobody.here")
