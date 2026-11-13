"""The loop design, attacked with a stub model that tries what it shouldn't."""

import json

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent import config, lookups, loop, records, tools
from agent import graph as g
from agent.decision import DECISION_TOOL_NAME
from agent.tests.fakes import UNIT, ScriptedLLM, call, decision, escalate, fix, text

TICKET = "INC-ALP-0001"  # an imported ticket, with recorded checks
OTHER = "INC-PDQ-0001"
LOCKOUT = {**UNIT, "doc": "account-lockout", "text": "Lockout playbook"}
LOOKUPS = {"search_kb", "lookup_requester", "find_similar_incidents", "run_check"}
USAGE = {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100}


def user(lockouts: int = 0) -> dict:
    return {"id": "a.hussain", "lockouts_24h": lockouts, "device": {"id": "LT-X"}}


@pytest.fixture
def run(monkeypatch):
    """Run the loop design with a scripted stub, and count every tool that runs."""
    ran: list[str] = []
    real_dispatch = tools.dispatch

    def dispatch(name, inp):
        ran.append(name)
        return real_dispatch(name, inp)

    monkeypatch.setattr(g.tools, "dispatch", dispatch)
    monkeypatch.setattr(lookups, "retrieve", lambda q: [UNIT])
    monkeypatch.setenv("DESIGN", "loop")

    def start(llm, retrieved=(), requester=None, ticket_id=TICKET):
        monkeypatch.setattr(g, "retrieve", lambda q: list(retrieved))
        monkeypatch.setattr(g, "_get_llm", lambda: llm)
        graph = g.build_graph(InMemorySaver())
        config_: RunnableConfig = {"configurable": {"thread_id": "t"}}
        state = g.initial_state("locked out", True, requester, "queue", ticket_id)
        return graph, config_, graph.invoke(state, config_), ran

    return start


def lookups_of(out: dict) -> list[dict]:
    return [step for step in out["steps"] if step["tool"] != DECISION_TOOL_NAME]


# ── What it can call ────────────────────────────────────────────────────────────
def test_the_loop_offers_the_lookups_and_the_decision_and_nothing_else(run):
    llm = ScriptedLLM(escalate("DESK-SUPPORT"))
    run(llm)
    assert set(llm.bound[0]) == {*LOOKUPS, DECISION_TOOL_NAME}
    assert llm.choices[0] == "any"


def test_one_call_design_never_starts_the_loop(run, monkeypatch):
    monkeypatch.setenv("DESIGN", "one call")
    llm = ScriptedLLM(escalate("DESK-SUPPORT"))
    _, _, out, _ = run(llm)
    assert llm.bound == [[DECISION_TOOL_NAME]]
    assert out["steps"] == []
    assert out["design"] == "one call"


def test_a_fix_tool_called_directly_is_refused_and_never_runs(run):
    llm = ScriptedLLM(
        [call("unlock_ad_account", username="a.hussain")],
        escalate("DESK-SUPPORT"),
    )
    graph, config_, out, ran = run(llm, requester=user())
    refused = out["steps"][0]
    assert refused["tool"] == "unlock_ad_account"
    assert not refused["ok"]
    assert refused["result"].startswith("Refused")
    graph.invoke(Command(resume=True), config_)
    assert ran == ["create_escalation_ticket"]


def test_a_fix_the_loop_decides_still_waits_at_the_gate(run):
    llm = ScriptedLLM(
        [call("lookup_requester")],
        fix("clear_credential_manager", username="a.hussain"),
    )
    _, _, out, ran = run(llm, requester=user())
    gate = out["__interrupt__"][0].value
    assert gate["kind"] == "confirm_fix"
    assert ran == []


def test_sec04_still_overrules_the_loops_decision(run):
    llm = ScriptedLLM(
        [call("lookup_requester")], fix("unlock_ad_account", username="a.hussain")
    )
    _, _, out, ran = run(llm, retrieved=[LOCKOUT], requester=user(2))
    assert out["rule"]["rule"] == "SEC-04"
    assert out["tool_input"]["queue"] == "SEC-INCIDENT"
    assert out["__interrupt__"][0].value["kind"] == "confirm_ticket"
    assert ran == []


# ── What it can read ────────────────────────────────────────────────────────────
def test_a_check_reads_the_ticket_being_worked(run):
    llm = ScriptedLLM(
        [call("run_check", step="account-lockout-source-check")],
        escalate("DESK-SUPPORT"),
    )
    _, _, out, _ = run(llm)
    step = out["steps"][0]
    assert step["ok"]
    assert step["result"].startswith("fail: ")
    reply = llm.seen[1][-1]
    assert isinstance(reply, ToolMessage)
    prefix, _, body = str(reply.content).partition(" {")
    assert prefix == "Step s1."  # the model reads the id it can cite
    assert json.loads("{" + body)["step"] == "account-lockout-source-check"


def test_a_check_on_another_ticket_is_refused(run):
    llm = ScriptedLLM(
        [call("run_check", step="print-spooler-check", ticket=OTHER)],
        escalate("DESK-SUPPORT"),
    )
    _, _, out, _ = run(llm)
    step = out["steps"][0]
    assert not step["ok"]
    assert "ticket being worked" in step["result"]
    assert "spooler" not in str(llm.seen[1][-1].content).replace(
        "print-spooler-check", ""
    )


def test_another_tickets_step_on_this_ticket_has_no_result(run):
    llm = ScriptedLLM(
        [call("run_check", step="print-spooler-check")], escalate("DESK-SUPPORT")
    )
    _, _, out, _ = run(llm)
    assert out["steps"][0]["ok"]
    assert out["steps"][0]["result"].startswith("No recorded result")


def test_a_ticket_with_no_id_has_no_checks(run):
    llm = ScriptedLLM(
        [call("run_check", step="account-lockout-source-check")],
        escalate("DESK-SUPPORT"),
    )
    _, _, out, _ = run(llm, ticket_id=None)
    assert out["steps"][0]["result"].startswith("No recorded result")


# ── Limits and failures ─────────────────────────────────────────────────────────
def test_a_model_that_never_decides_stops_at_the_limit(run):
    llm = ScriptedLLM([call("search_kb", query="lockout")])
    graph, config_, out, ran = run(llm, requester=user())
    ran_ok = [step for step in lookups_of(out) if step["ok"]]
    assert len(ran_ok) == config.MAX_LOOKUPS
    assert llm.bound[-1] == [DECISION_TOOL_NAME]  # its last turn could only decide
    assert len(llm.seen) == config.MAX_LOOKUPS + 1
    assert out["stopped"] == "lookups"
    gate = out["__interrupt__"][0].value
    assert gate["kind"] == "confirm_ticket"
    assert gate["ticket"]["queue"] == "DESK-SUPPORT"
    assert "limit of 6 lookups" in gate["ticket"]["summary"]
    assert "search_kb" in out["reasoning"]
    graph.invoke(Command(resume=True), config_)
    assert ran == ["create_escalation_ticket"]


def test_lookups_past_the_limit_in_one_turn_dont_run(run):
    many = [call("search_kb", query=f"q{n}") for n in range(config.MAX_LOOKUPS + 2)]
    llm = ScriptedLLM(many, escalate("DESK-SUPPORT"))
    _, _, out, _ = run(llm)
    steps = lookups_of(out)
    assert sum(step["ok"] for step in steps) == config.MAX_LOOKUPS
    assert steps[-1]["result"] == "Over the limit of 6 lookups."
    assert llm.bound[1] == [DECISION_TOOL_NAME]
    assert out["path"] == "ESCALATE"


def test_the_loop_stops_when_it_has_spent_its_limit(run, monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "claude-sonnet-5-5")  # dear enough to stop
    expensive = {"input_tokens": 5000, "output_tokens": 500, "total_tokens": 5500}
    llm = ScriptedLLM([call("lookup_requester")], usage=expensive)
    _, _, out, _ = run(llm, requester=user())
    assert out["stopped"] == "cost"
    assert len(llm.seen) == 1
    assert "CHF 0.01" in out["tool_input"]["summary"]


def test_an_unreadable_call_fails_its_step_not_the_run(run):
    llm = ScriptedLLM(
        [call("run_check", step=5)], escalate("DESK-SUPPORT"), broken=["search_kb"]
    )
    _, _, out, _ = run(llm)
    failed = lookups_of(out)
    assert [step["ok"] for step in failed] == [False, False]
    assert failed[0]["result"].startswith("Unreadable arguments")
    assert out["path"] == "ESCALATE"
    replies = [m for m in llm.seen[1] if isinstance(m, ToolMessage)]
    assert len(replies) == 2  # the model hears back about both


def test_a_lookup_that_breaks_fails_its_step_not_the_run(run, monkeypatch):
    def broken(query):
        raise RuntimeError("index down")

    monkeypatch.setattr(lookups, "retrieve", broken)
    llm = ScriptedLLM([call("search_kb", query="vpn")], escalate("DESK-SUPPORT"))
    _, _, out, _ = run(llm)
    assert out["steps"][0]["result"] == "search_kb failed: RuntimeError."
    assert out["path"] == "ESCALATE"


def test_a_turn_with_no_call_goes_to_a_person(run):
    llm = ScriptedLLM([text("I think it's the VPN.")])
    _, _, out, _ = run(llm)
    assert out["path"] == "ESCALATE"
    assert out["tool_input"]["queue"] == "DESK-SUPPORT"
    assert out["steps"][-1]["tool"] == DECISION_TOOL_NAME
    assert not out["steps"][-1]["ok"]  # no readable decision


def test_a_decision_beside_lookups_ends_the_loop(run):
    llm = ScriptedLLM([call("lookup_requester"), *escalate("NET-VPN")])
    _, _, out, _ = run(llm)
    assert [step["tool"] for step in out["steps"]] == [DECISION_TOOL_NAME]
    assert out["tool_input"]["queue"] == "NET-VPN"


# ── What each step keeps ────────────────────────────────────────────────────────
def test_each_step_keeps_its_tool_input_result_time_tokens_and_cost(run):
    llm = ScriptedLLM(
        [call("lookup_requester"), call("find_similar_incidents", query="lockout")],
        escalate("DESK-SUPPORT"),
        usage=USAGE,
    )
    _, _, out, _ = run(llm, requester=records.requester("s.keller"))
    first, second, decided = out["steps"]
    assert [s["id"] for s in out["steps"]] == ["s1", "s2", "s3"]
    assert first["tool"] == "lookup_requester"
    assert first["result"] == (
        "Client Services, Zürich; 2 lockouts in 24 hours; device LT-SKELLER."
    )
    assert second["input"] == {"query": "lockout"}
    assert (first["turn"], second["turn"], decided["turn"]) == (1, 1, 2)
    assert first["input_tokens"] == 1000
    assert second["input_tokens"] == 0  # a turn is counted once, on its first step
    assert first["cost_usd"] == pytest.approx(
        config.cost_usd(config.model_name(), 1000, 100)
    )
    assert out["usage"]["input_tokens"] == 2000
    assert decided["result"] == "ESCALATE"
    assert all(step["time_sec"] >= 0 for step in out["steps"])


def test_the_model_reads_the_loop_guide_with_its_limit():
    guide = loop.guide()
    assert f"at most {config.MAX_LOOKUPS} lookups" in guide
    assert "{max_lookups}" not in guide


def test_a_stop_decision_lists_what_was_found():
    step: loop.Step = {
        "id": "s1",
        "turn": 1,
        "tool": "run_check",
        "input": {"step": "vpn-client-check"},
        "result": "fail: old client",
        "found": ["vpn-client-check"],
        "ok": True,
        "time_sec": 0.1,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
    }
    made = loop.stop_decision([step], "cost")
    assert made["tool_input"]["queue"] == "DESK-SUPPORT"
    assert "1 lookups" in made["tool_input"]["summary"]
    assert "fail: old client" in made["reasoning"]


def test_decision_records_tolerate_no_usage():
    assert (
        g._total(None, {"input_tokens": 1, "output_tokens": 2, "cost_usd": None})[
            "cost_usd"
        ]
        is None
    )


# ── Citations and the handover ──────────────────────────────────────────────────
def test_a_citation_of_a_step_that_never_ran_is_dropped(run):
    llm = ScriptedLLM(
        [call("run_check", step="account-lockout-source-check")],
        decision(
            "ESCALATE",
            queue="IAM-ACCESS",
            evidence=["s1", "s7", "s1"],
            ruled_out="A wrong password: the source check failed.",
            next_step="Find the device that keeps the old password.",
        ),
    )
    _, _, out, _ = run(llm, requester=user())
    assert out["citations"] == {"kept": ["s1"], "dropped": ["s7"]}


def test_a_failed_step_cant_be_cited(run):
    llm = ScriptedLLM(
        [call("run_check", step="x", ticket=OTHER)],
        decision("ESCALATE", queue="IAM-ACCESS", evidence=["s1"]),
    )
    _, _, out, _ = run(llm)
    assert out["citations"] == {"kept": [], "dropped": ["s1"]}


def test_an_escalation_carries_a_handover_code_fills_in(run):
    llm = ScriptedLLM(
        [
            call("run_check", step="account-lockout-source-check"),
            call("run_check", step="not-a-check"),
            call("find_similar_incidents", query="locked after reset"),
        ],
        decision(
            "ESCALATE",
            cause="Stale credentials on a phone",
            queue="IAM-ACCESS",
            priority="P2-High",
            evidence=["s1"],
            ruled_out="A wrong password.",
            next_step="Find the device that keeps the old password.",
        ),
    )
    _, _, out, _ = run(llm, requester=user())
    h = out["handover"]
    assert h["requester"]["id"] == "a.hussain"
    assert h["device"]["id"] == "LT-X"
    assert (h["queue"], h["priority"], h["sla"]) == (
        "IAM-ACCESS",
        "P2-High",
        "4 business hours",
    )
    # Tuesday 18 November 2025, 09:00 in Zürich, plus 4 business hours.
    assert h["submitted_at"].startswith("2025-11-18T08:00")
    assert h["deadline"].startswith("2025-11-18T12:00")
    assert h["applications"] == ["Password Reset Portal", "SSO Portal"]
    assert [c["step"] for c in h["checks"]] == ["account-lockout-source-check"]
    assert h["similar"]  # the incidents the search found, by id
    assert any("not-a-check" in u for u in h["unknown"])
    assert h["cause"] == "Stale credentials on a phone"
    assert h["next_step"] == "Find the device that keeps the old password."


def test_a_loop_that_stops_at_its_limit_still_hands_over(run):
    llm = ScriptedLLM([call("lookup_requester")])
    _, _, out, _ = run(llm, requester=user())
    assert out["stopped"] == "lookups"
    assert out["handover"]["queue"] == "DESK-SUPPORT"
    assert any("cause" in u for u in out["handover"]["unknown"])


def test_a_fix_has_no_handover(run):
    llm = ScriptedLLM(fix("clear_credential_manager", username="a.hussain"))
    _, _, out, _ = run(llm, requester=user())
    assert out["handover"] is None
