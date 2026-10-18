"""Offline tests: parse_path, routers, and full graph flows with a fake model.

No API calls and no embeddings — `graph.retrieve` and `graph._get_llm` are patched.
"""
import csv

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import graph as g


def text(t):
    return {"type": "text", "text": t}


def tool(name, **inp):
    return {"type": "tool_use", "name": name, "input": inp}


# ── parse_path ──────────────────────────────────────────────────────────────────
def test_text_only_escalate_gets_safety_net_ticket():
    out = g.parse_path([text("Lockout frequency is unknown, so this needs review.\nPath chosen: ESCALATE")])
    assert out["path"] == "ESCALATE"
    assert out["tool_name"] == "create_escalation_ticket"
    assert out["tool_input"] == {
        "queue": "DESKTOP-SUPPORT",
        "summary": "Lockout frequency is unknown, so this needs review.",
        "priority": "P3-Normal",
    }


def test_tool_use_overrides_text_keyword():
    out = g.parse_path([
        text("Looks like SELF_SERVE territory, but a tool is better."),
        tool("reset_vpn_profile", username="current.user"),
    ])
    assert out["path"] == "AUTO_FIX"
    assert out["tool_name"] == "reset_vpn_profile"
    assert out["tool_input"] == {"username": "current.user"}


def test_last_keyword_in_text_wins():
    out = g.parse_path([text("Not ESCALATE material. Path chosen: SELF_SERVE because it is simple.")])
    assert out["path"] == "SELF_SERVE"
    assert out["tool_name"] is None


def test_text_after_tool_use_does_not_change_path():
    out = g.parse_path([
        tool("clear_teams_cache", username="current.user"),
        text("Path chosen: SELF_SERVE"),
    ])
    assert out["path"] == "AUTO_FIX"
    assert out["reasoning"] == "Path chosen: SELF_SERVE"


def test_escalation_ticket_tool_keeps_model_ticket():
    ticket = {"queue": "SEC-INCIDENT", "summary": "Repeated lockouts", "priority": "P2-High"}
    out = g.parse_path([text("Escalating per SEC-04."), tool("create_escalation_ticket", **ticket)])
    assert out["path"] == "ESCALATE"
    assert out["tool_input"] == ticket


def test_out_of_scope_has_no_tool():
    out = g.parse_path([text("OUT_OF_SCOPE: That is not an IT question.")])
    assert out["path"] == "OUT_OF_SCOPE"
    assert out["tool_name"] is None and out["tool_input"] is None


def test_no_keyword_defaults_to_escalate_with_fallback_summary():
    out = g.parse_path([text("hmm")])
    assert out["path"] == "ESCALATE"
    assert out["tool_input"]["summary"] == "Issue escalated — technician review required."


# ── routers ─────────────────────────────────────────────────────────────────────
def test_routers():
    assert g.route_start({"use_retrieval": True}) == "retrieve"
    assert g.route_start({"use_retrieval": False}) == "no_tools"
    for path, dest in [
        ("OUT_OF_SCOPE", "log"),
        ("SELF_SERVE", "self_serve_wait"),
        ("AUTO_FIX", "confirm_fix"),
        ("ESCALATE", "confirm_ticket"),
    ]:
        assert g.route_after_triage({"path": path}) == dest
    assert g.route_after_confirm_fix({"human_decision": {"fix": True}}) == "execute_tool"
    assert g.route_after_confirm_fix({"human_decision": {"fix": False}}) == "draft_ticket"
    assert g.route_after_confirm_ticket({"human_decision": {"ticket": True}}) == "create_ticket"
    assert g.route_after_confirm_ticket({"human_decision": {"ticket": False}}) == "log"
    assert g.route_after_self_serve({"human_decision": {"resolved": True}}) == "log"
    assert g.route_after_self_serve({"human_decision": {"resolved": False}}) == "draft_ticket"


# ── graph flows with a fake model ───────────────────────────────────────────────
class FakeLLM:
    def __init__(self, blocks):
        self.blocks = blocks
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def invoke(self, messages):
        calls = [
            {"name": b["name"], "args": b["input"], "id": "x", "type": "tool_call"}
            for b in self.blocks if b["type"] == "tool_use"
        ]
        return AIMessage(content=self.blocks, tool_calls=calls)


UNIT = {"doc": "vpn", "section": None, "text": "VPN playbook", "score": 0.8, "highlights": []}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "LOG_FILE", tmp_path / "logs.csv")
    monkeypatch.setattr(g, "retrieve", lambda q: [UNIT])

    class Env:
        graph = g.build_graph(InMemorySaver())
        config = {"configurable": {"thread_id": "t1"}}
        llm = None

        def use(self, blocks):
            self.llm = FakeLLM(blocks)
            monkeypatch.setattr(g, "_get_llm", lambda: self.llm)

        def start(self, query="q", use_retrieval=True):
            return self.graph.invoke(g.initial_state(query, use_retrieval), self.config)

        def resume(self, value):
            return self.graph.invoke(Command(resume=value), self.config)

        def rows(self):
            if not g.LOG_FILE.exists():
                return []
            with open(g.LOG_FILE, newline="") as f:
                return list(csv.DictReader(f))

    return Env()


def test_auto_fix_confirm(env):
    env.use([text("Stale cert. Path chosen: AUTO_FIX"), tool("reset_vpn_profile", username="current.user")])
    out = env.start()
    assert out["__interrupt__"][0].value["kind"] == "confirm_fix"
    assert env.rows() == []  # nothing logged and nothing executed before the decision
    out = env.resume(True)
    assert "__interrupt__" not in out
    assert out["tool_result"]["action"] == "reset_vpn_profile"
    (row,) = env.rows()
    assert (row["decision_path"], row["tool_called"], row["confirmed"]) == ("AUTO_FIX", "reset_vpn_profile", "true")
    assert row["retrieved_units"] == "vpn"


def test_auto_fix_decline_then_send_ticket(env):
    env.use([text("Stale cert on the laptop.\nPath chosen: AUTO_FIX"), tool("reset_vpn_profile", username="current.user")])
    env.start()
    out = env.resume(False)
    payload = out["__interrupt__"][0].value
    assert payload["kind"] == "confirm_ticket"
    assert payload["ticket"]["source"] == "decline"
    assert payload["ticket"]["declined_tool"] == "reset_vpn_profile"
    assert out.get("tool_result") is None  # fix did not run
    out = env.resume(True)
    assert out["tool_result"]["action"] == "create_escalation_ticket"
    (row,) = env.rows()
    assert (row["decision_path"], row["tool_called"], row["confirmed"]) == ("AUTO_FIX", "reset_vpn_profile", "false")


def test_escalate_cancel_creates_no_ticket(env):
    env.use([text("Escalating."), tool("create_escalation_ticket", queue="SEC-INCIDENT", summary="Lockout", priority="P2-High")])
    out = env.start()
    assert out["__interrupt__"][0].value["ticket"]["queue"] == "SEC-INCIDENT"
    out = env.resume(False)
    assert out.get("tool_result") is None
    (row,) = env.rows()
    assert (row["decision_path"], row["escalation_queue"], row["priority"], row["confirmed"]) == (
        "ESCALATE", "SEC-INCIDENT", "P2-High", "",
    )


def test_self_serve_not_resolved_becomes_ticket(env):
    env.use([text("1. Reseat the cable.\nPath chosen: SELF_SERVE")])
    out = env.start("monitor dead")
    assert out["__interrupt__"][0].value == {"kind": "self_serve"}
    out = env.resume(False)
    ticket = out["__interrupt__"][0].value["ticket"]
    assert ticket["source"] == "self_serve" and "monitor dead" in ticket["summary"]
    out = env.resume(True)
    assert out["tool_result"]["queue"] == "DESKTOP-SUPPORT"
    (row,) = env.rows()
    assert (row["decision_path"], row["tool_called"]) == ("SELF_SERVE", "")


def test_self_serve_resolved_logs_without_ticket(env):
    env.use([text("Path chosen: SELF_SERVE")])
    env.start()
    out = env.resume(True)
    assert out.get("tool_result") is None
    assert len(env.rows()) == 1


def test_out_of_scope_logs_immediately(env):
    env.use([text("OUT_OF_SCOPE: Not an IT question.")])
    out = env.start("weather?")
    assert "__interrupt__" not in out
    (row,) = env.rows()
    assert row["decision_path"] == "OUT_OF_SCOPE"


def test_rag_off_has_no_tools_and_is_not_logged(env):
    env.use([text("Generic advice.")])
    out = env.start(use_retrieval=False)
    assert env.llm.bound_tools is None
    assert (out["path"], out["retrieved"], out["tool_name"]) == ("NO_TOOLS", [], None)
    assert out["reasoning"] == "Generic advice."
    assert env.rows() == []


def test_new_run_on_same_thread_does_not_inherit_old_decisions(env):
    env.use([text("x"), tool("reset_vpn_profile", username="current.user")])
    env.start()
    env.resume(False)  # leaves human_decision={"fix": False} and a ticket draft behind
    env.resume(False)
    out = env.start("second query")
    assert out["__interrupt__"][0].value["kind"] == "confirm_fix"
    assert out["human_decision"] == {} and out["ticket_draft"] is None


def test_new_query_while_interrupt_pending_starts_fresh_run(env):
    env.use([text("Path chosen: SELF_SERVE")])
    first = env.start("first")
    assert first["__interrupt__"][0].value == {"kind": "self_serve"}
    env.start("second")  # previous run was still paused; abandoned, not resumed
    out = env.resume(True)
    assert out["query"] == "second"
    # The abandoned run never reached `log`, so only the completed one is recorded.
    assert [r["query"] for r in env.rows()] == ["second"]


def test_log_runs_false_skips_logging(env):
    env.use([text("OUT_OF_SCOPE: nope")])
    cfg = {"configurable": {"thread_id": "t2", "log_runs": False}}
    env.graph.invoke(g.initial_state("weather?", True), cfg)
    assert env.rows() == []
