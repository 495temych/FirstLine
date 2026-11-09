"""The run_triage entry point."""

from langchain_core.messages import AIMessage

from agent import graph, run_triage
from agent.tests.fakes import UNIT, FakeLLM, fix


def test_run_triage_stops_at_the_first_gate(monkeypatch):
    llm = FakeLLM(fix("reset_vpn_profile", "Reset it.", username="a.b"))
    monkeypatch.setattr(graph, "retrieve", lambda q: [UNIT])
    monkeypatch.setattr(graph, "_get_llm", lambda: llm)

    result = run_triage("VPN down", use_retrieval=True)

    assert result["path"] == "AUTO_FIX"
    assert result["tool_name"] == "reset_vpn_profile"
    assert result["tool_input"] == {"username": "a.b"}
    assert result["retrieved"] == [UNIT]
    assert result["usage"] == {"input_tokens": 0, "output_tokens": 0}


def test_usage_comes_from_the_model_reply():
    msg = AIMessage(
        content="",
        usage_metadata={"input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
    )
    assert graph.usage_of(msg) == {"input_tokens": 12, "output_tokens": 3}
