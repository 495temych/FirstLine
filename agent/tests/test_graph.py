"""Offline tests: routers and full graph flows with a fake model.

No API calls and no embeddings — `graph.retrieve` and `graph._get_llm` are patched.
"""

from typing import Any, cast

import anthropic
import httpx
import pytest
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END
from langgraph.types import Command
from qdrant_client.http.exceptions import ResponseHandlingException

from agent import actions, tools
from agent import graph as g
from agent.tests.fakes import (
    UNIT,
    FakeLLM,
    escalate,
    fix,
    out_of_scope,
    steps,
    text,
)


def state(fields: dict) -> g.GraphState:
    """A partial state: routers read only one or two fields."""
    return cast(g.GraphState, fields)


# ── routers ─────────────────────────────────────────────────────────────────────
def test_routers():
    assert g.route_start(state({"use_retrieval": True})) == "retrieve"
    assert g.route_start(state({"use_retrieval": False})) == "no_tools"
    for path, dest in [
        ("OUT_OF_SCOPE", "__end__"),
        ("SELF_SERVE", "self_serve_wait"),
        ("AUTO_FIX", "confirm_fix"),
        ("ESCALATE", "confirm_ticket"),
    ]:
        assert g.route_after_triage(state({"path": path})) == dest
    assert (
        g.route_after_confirm_fix(state({"human_decision": {"fix": True}}))
        == "execute_tool"
    )
    assert (
        g.route_after_confirm_fix(state({"human_decision": {"fix": False}}))
        == "draft_ticket"
    )
    assert (
        g.route_after_confirm_ticket(state({"human_decision": {"ticket": True}}))
        == "create_ticket"
    )
    assert (
        g.route_after_confirm_ticket(state({"human_decision": {"ticket": False}}))
        == "__end__"
    )
    assert (
        g.route_after_self_serve(state({"human_decision": {"resolved": True}}))
        == "__end__"
    )
    assert (
        g.route_after_self_serve(state({"human_decision": {"resolved": False}}))
        == "draft_ticket"
    )


# ── graph flows with a fake model ───────────────────────────────────────────────
@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "retrieve", lambda q: [UNIT])
    monkeypatch.setattr(actions, "_installed", [actions.MemoryLedger()])

    class Env:
        graph = g.build_graph(InMemorySaver())
        config: RunnableConfig = {"configurable": {"thread_id": "t1"}}
        llm = None

        def use(self, blocks):
            self.llm = FakeLLM(blocks)
            monkeypatch.setattr(g, "_get_llm", lambda: self.llm)

        def start(self, query="q", use_retrieval=True):
            state = g.initial_state(query, use_retrieval, None, "queue")
            return self.graph.invoke(state, self.config)

        def resume(self, value):
            return self.graph.invoke(Command(resume=value), self.config)

    return Env()


def test_auto_fix_confirm(env):
    env.use(fix("reset_vpn_profile", "Stale cert.", username="current.user"))
    out = env.start()
    assert out["__interrupt__"][0].value["kind"] == "confirm_fix"
    assert out.get("tool_result") is None  # nothing runs before the decision
    out = env.resume(True)
    assert "__interrupt__" not in out
    assert out["tool_result"]["action"] == "reset_vpn_profile"
    assert out["human_decision"] == {"fix": True}
    assert [u["doc"] for u in out["retrieved"]] == ["vpn"]


def test_an_approved_fix_asked_for_again_returns_its_first_outcome(env, monkeypatch):
    env.use(fix("reset_vpn_profile", "Stale cert.", username="current.user"))
    ran = []
    dispatch = tools.dispatch
    monkeypatch.setattr(tools, "dispatch", lambda t, i: ran.append(t) or dispatch(t, i))
    env.start()
    first = env.resume(True)["tool_result"]
    values = env.graph.get_state(env.config).values
    again = g.execute_tool(values, env.config)["tool_result"]
    assert again == first
    assert ran == ["reset_vpn_profile"]


def test_auto_fix_decline_then_send_ticket(env):
    env.use(
        fix("reset_vpn_profile", "Stale cert on the laptop.", username="current.user")
    )
    env.start()
    out = env.resume(False)
    payload = out["__interrupt__"][0].value
    assert payload["kind"] == "confirm_ticket"
    assert payload["ticket"]["source"] == "decline"
    assert payload["ticket"]["declined_tool"] == "reset_vpn_profile"
    assert out.get("tool_result") is None  # fix did not run
    out = env.resume(True)
    assert out["tool_result"]["action"] == "create_escalation_ticket"
    assert (out["path"], out["human_decision"]["fix"]) == ("AUTO_FIX", False)


def test_escalate_cancel_creates_no_ticket(env):
    env.use(escalate("SEC-INCIDENT", "Escalating.", "Lockout"))
    out = env.start()
    assert out["__interrupt__"][0].value["ticket"]["queue"] == "SEC-INCIDENT"
    out = env.resume(False)
    assert out.get("tool_result") is None
    assert out["human_decision"] == {"ticket": False}


def test_self_serve_not_resolved_becomes_ticket(env):
    env.use(steps("Reseat the cable."))
    out = env.start("monitor dead")
    assert out["__interrupt__"][0].value == {"kind": "self_serve"}
    out = env.resume(False)
    ticket = out["__interrupt__"][0].value["ticket"]
    assert ticket["source"] == "self_serve"
    assert "monitor dead" in ticket["summary"]
    out = env.resume(True)
    assert out["tool_result"]["queue"] == "DESK-SUPPORT"
    assert (out["path"], out["tool_name"]) == ("SELF_SERVE", None)


def test_self_serve_resolved_ends_without_ticket(env):
    env.use(steps("Reseat the cable."))
    env.start()
    out = env.resume(True)
    assert out.get("tool_result") is None
    assert "__interrupt__" not in out


def test_out_of_scope_ends_immediately(env):
    env.use(out_of_scope())
    out = env.start("weather?")
    assert "__interrupt__" not in out
    assert out["path"] == "OUT_OF_SCOPE"


def test_rag_off_has_no_tools(env):
    env.use([text("Generic advice.")])
    out = env.start(use_retrieval=False)
    assert env.llm.bound_tools is None
    assert (out["path"], out["retrieved"], out["tool_name"]) == ("NO_TOOLS", [], None)
    assert out["reasoning"] == "Generic advice."


def test_new_run_on_same_thread_does_not_inherit_old_decisions(env):
    env.use(fix("reset_vpn_profile", username="current.user"))
    env.start()
    env.resume(False)  # leaves human_decision={"fix": False} and a ticket draft behind
    env.resume(False)
    out = env.start("second query")
    assert out["__interrupt__"][0].value["kind"] == "confirm_fix"
    assert out["human_decision"] == {}
    assert out["ticket_draft"] is None


def test_new_query_while_interrupt_pending_starts_fresh_run(env):
    env.use(steps("Reseat the cable."))
    first = env.start("first")
    assert first["__interrupt__"][0].value == {"kind": "self_serve"}
    env.start("second")  # previous run was still paused; abandoned, not resumed
    out = env.resume(True)
    assert out["query"] == "second"


def test_a_search_that_cannot_reach_the_index_is_retried():
    assert g._is_search_error(ResponseHandlingException(OSError("timed out")))
    assert not g._is_search_error(ValueError("bad input"))


def test_done_is_langgraphs_end():
    assert g.DONE == END


# ── retries ─────────────────────────────────────────────────────────────────────
def _dropped():
    request = cast(Any, httpx.Request("POST", "https://x"))
    return anthropic.APIConnectionError(request=request)


class Flaky(FakeLLM):
    """A model whose connection drops `drops` times before it answers."""

    def __init__(self, blocks, drops):
        super().__init__(blocks)
        self.drops = drops
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        if self.calls <= self.drops:
            raise _dropped()
        return super().invoke(messages)


@pytest.fixture
def no_wait(monkeypatch):
    monkeypatch.setattr(g, "RETRY_WAIT_SEC", 0.0)


def test_a_model_call_that_drops_is_tried_again_up_to_the_limit(env, no_wait):
    flaky = Flaky(out_of_scope(), drops=g.MODEL_ATTEMPTS - 1)
    env.use(flaky.blocks)
    env.llm = flaky
    out = env.start()
    assert out["path"] == "OUT_OF_SCOPE"
    assert flaky.calls == g.MODEL_ATTEMPTS


def test_a_model_call_stops_at_the_limit(no_wait):
    flaky = Flaky(out_of_scope(), drops=g.MODEL_ATTEMPTS)
    with pytest.raises(anthropic.APIConnectionError):
        g._ask(cast(Runnable, flaky), [])
    assert flaky.calls == g.MODEL_ATTEMPTS


def test_an_error_the_model_did_not_cause_to_pass_is_not_retried(no_wait):
    class Refused(FakeLLM):
        calls = 0

        def invoke(self, messages):
            self.calls += 1
            raise ValueError("bad request")

    refused = Refused([])
    with pytest.raises(ValueError, match="bad request"):
        g._ask(cast(Runnable, refused), [])
    assert refused.calls == 1


def test_a_failure_after_the_model_answered_never_asks_it_again(
    env, no_wait, monkeypatch
):
    env.use(out_of_scope())
    asked = []
    answer = env.llm.invoke
    monkeypatch.setattr(env.llm, "invoke", lambda m: asked.append(1) or answer(m))

    def broken(*_args, **_kwargs):
        raise _dropped()

    monkeypatch.setattr(g, "read_decision", broken)
    with pytest.raises(anthropic.APIConnectionError):
        env.start()
    assert len(asked) == 1
