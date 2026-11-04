"""The run_triage entry point."""

from agent import graph, run_triage
from agent.tests.fakes import UNIT, FakeLLM, text, tool


def test_run_triage_stops_at_the_first_gate_and_logs_nothing(tmp_path, monkeypatch):
    log = tmp_path / "logs.csv"
    llm = FakeLLM([text("Reset it."), tool("reset_vpn_profile", username="a.b")])
    monkeypatch.setattr(graph, "LOG_FILE", log)
    monkeypatch.setattr(graph, "retrieve", lambda q: [UNIT])
    monkeypatch.setattr(graph, "_get_llm", lambda: llm)

    result = run_triage("VPN down", use_retrieval=True)

    assert result["path"] == "AUTO_FIX"
    assert result["tool_name"] == "reset_vpn_profile"
    assert result["tool_input"] == {"username": "a.b"}
    assert result["retrieved"] == [UNIT]
    assert not log.exists()
