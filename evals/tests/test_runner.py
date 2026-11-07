"""The runner, with a stub run_triage."""

import json
import runpy

import pytest

from evals import runner


def result(path, tool=None, tool_input=None):
    return {
        "path": path,
        "retrieved": [{"doc": "vpn", "section": None}],
        "tool_name": tool,
        "tool_input": tool_input,
        "usage": {"input_tokens": 1000, "output_tokens": 200},
        "response_time_sec": 1.5,
    }


def always_escalate(text, use_retrieval):
    queue = {"queue": "SEC-INCIDENT", "summary": "s", "priority": "P2-High"}
    return result("ESCALATE", "create_escalation_ticket", queue)


@pytest.fixture
def stubbed(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(runner, "run_triage", always_escalate)
    monkeypatch.delenv("MODEL_NAME", raising=False)
    return tmp_path


@pytest.mark.usefixtures("stubbed")
def test_a_run_records_what_was_measured():
    run = runner.evaluate("rules", tiny=True)
    assert run["set"] == "rules"
    assert run["tiny"] is True
    assert run["version"] == runner.version()
    assert len(run["version"]) == 8
    assert run["summary"]["n"] == 5
    first = run["tickets"][0]
    assert first["input_tokens"] == 1000
    assert first["cost_usd"] == pytest.approx(0.002)
    assert first["time_sec"] == 1.5


@pytest.mark.usefixtures("stubbed")
def test_a_failed_ticket_counts_as_an_escalation_and_the_run_goes_on(monkeypatch):
    def fail_once(text, use_retrieval):
        monkeypatch.setattr(runner, "run_triage", always_escalate)
        raise TimeoutError("no answer")

    monkeypatch.setattr(runner, "run_triage", fail_once)
    run = runner.evaluate("rules", tiny=True)
    assert run["summary"]["n"] == 5
    assert run["summary"]["failed"] == 1
    first = run["tickets"][0]
    assert first["path"] == "ESCALATE"
    assert first["error"] == "TimeoutError: no answer"
    assert first["cost_usd"] == 0


@pytest.mark.usefixtures("stubbed")
def test_an_unknown_model_has_an_unknown_cost(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "a-model-with-no-price")
    run = runner.evaluate("rules", tiny=True)
    assert run["summary"]["cost_per_ticket_usd"] is None


def test_runs_load_newest_first(stubbed):
    stubbed.joinpath("20260101T000000-dev.json").write_text(json.dumps({"id": "old"}))
    runner.save_run({"id": "20270101T000000-dev"})
    assert [r["id"] for r in runner.load_runs()] == ["20270101T000000-dev", "old"]


def test_the_command_saves_and_reports(stubbed, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["evals", "--set", "rules_held_out", "--tiny"])
    runpy.run_module("evals", run_name="__main__")
    out = capsys.readouterr().out
    assert "-rules_held_out-tiny" in out
    assert "cost per ticket $0.0020" in out
    assert "CHF" in out
    assert len(list(stubbed.glob("*.json"))) == 1
