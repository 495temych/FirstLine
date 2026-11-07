"""API tests, with a stub model and temporary files."""

import csv
import json
from unittest.mock import patch

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from agent import config, graph, tools
from agent.tests.fakes import UNIT, FakeLLM, escalate, fix, out_of_scope, steps, text
from backend import main, stats
from evals import retrieval_score, runner

AUTO_FIX = fix("reset_vpn_profile", "Reset the profile.", username="a.b")
ESCALATE = escalate("SEC-INCIDENT", "Needs review.")
SELF_SERVE = steps("Reseat the cable.")
OUT_OF_SCOPE = out_of_scope()


@pytest.fixture
def log(tmp_path):
    return tmp_path / "logs.csv"


@pytest.fixture
def client(tmp_path, log, monkeypatch):
    """The API against temporary files, with retrieval stubbed."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "CHECKPOINT_DB", tmp_path / "checkpoints.sqlite")
    monkeypatch.setattr(graph, "LOG_FILE", log)
    monkeypatch.setattr(stats, "LOG_FILE", log)
    monkeypatch.setattr(graph, "retrieve", lambda q: [UNIT])
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(retrieval_score, "RUNS_DIR", tmp_path / "retrieval")
    main._graph.cache_clear()
    yield TestClient(main.app)
    main._graph.cache_clear()


def start(client, monkeypatch, blocks, use_retrieval=True):
    llm = FakeLLM(blocks)
    monkeypatch.setattr(graph, "_get_llm", lambda: llm)
    body = {"text": "My ticket", "use_retrieval": use_retrieval}
    response = client.post("/api/triage", json=body)
    assert response.status_code == 200
    return response.json()


def answer(client, run, gate, approved):
    url = f"/api/runs/{run['id']}/answer"
    return client.post(url, json={"gate": gate, "approved": approved})


def logged_rows(log):
    with open(log, newline="") as f:
        return list(csv.DictReader(f))


def stub_triage(text, use_retrieval):
    return {
        "path": "AUTO_FIX",
        "retrieved": [],
        "tool_name": "clear_teams_cache",
        "tool_input": {"username": "a.b"},
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "response_time_sec": 1.0,
        "cause": "Unknown",
    }


def test_health_reports_the_key(client, monkeypatch):
    assert client.get("/api/health").json() == {"status": "ok", "api_key": True}
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert client.get("/api/health").json()["api_key"] is False


def test_starting_the_api_builds_nothing(client):
    assert main._graph.cache_info().currsize == 0


def test_triage_needs_a_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    body = {"text": "My ticket", "use_retrieval": True}
    response = client.post("/api/triage", json=body)
    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_a_blank_ticket_is_refused(client):
    body = {"text": "   ", "use_retrieval": True}
    assert client.post("/api/triage", json=body).status_code == 422


def test_a_failed_model_call_is_reported(client, monkeypatch):
    def fail():
        raise anthropic.APIConnectionError(request=httpx2.Request("POST", "http://x"))

    monkeypatch.setattr(graph, "_get_llm", fail)
    body = {"text": "My ticket", "use_retrieval": True}
    response = client.post("/api/triage", json=body)
    assert response.status_code == 502
    assert "model call failed" in response.json()["detail"]


def test_an_unknown_run_is_not_found(client):
    assert client.get("/api/runs/nope").status_code == 404
    body = {"gate": "confirm_fix", "approved": True}
    assert client.post("/api/runs/nope/answer", json=body).status_code == 404


def test_auto_fix_waits_at_its_gate_and_the_tool_has_not_run(client, monkeypatch):
    with patch.object(tools, "dispatch") as dispatch:
        run = start(client, monkeypatch, AUTO_FIX)
    assert run["path"] == "AUTO_FIX"
    assert run["pending"]["kind"] == "confirm_fix"
    assert run["retrieved"][0]["doc"] == "vpn"
    assert run["tool_result"] is None
    dispatch.assert_not_called()


def test_a_confirmed_fix_runs_and_is_logged(client, log, monkeypatch):
    run = start(client, monkeypatch, AUTO_FIX)
    done = answer(client, run, "confirm_fix", True).json()
    assert done["pending"] is None
    assert done["human_decision"] == {"fix": True}
    assert done["tool_result"]["simulated"] is True
    row = logged_rows(log)[0]
    assert row["decision_path"] == "AUTO_FIX"
    assert row["confirmed"] == "true"


def test_a_declined_fix_gives_a_pre_filled_ticket(client, monkeypatch):
    run = start(client, monkeypatch, AUTO_FIX)
    monkeypatch.setattr(graph, "_get_llm", lambda: pytest.fail("a new model call"))
    waiting = answer(client, run, "confirm_fix", False).json()
    assert waiting["pending"]["kind"] == "confirm_ticket"
    assert waiting["pending"]["ticket"]["source"] == "decline"
    assert waiting["tool_result"] is None
    done = answer(client, run, "confirm_ticket", True).json()
    assert done["tool_result"]["action"] == "create_escalation_ticket"


def test_escalate_creates_no_ticket_when_declined(client, log, monkeypatch):
    run = start(client, monkeypatch, ESCALATE)
    assert run["pending"]["ticket"]["queue"] == "SEC-INCIDENT"
    done = answer(client, run, "confirm_ticket", False).json()
    assert done["tool_result"] is None
    assert done["human_decision"] == {"ticket": False}
    assert logged_rows(log)[0]["escalation_queue"] == "SEC-INCIDENT"


def test_escalate_creates_a_ticket_when_confirmed(client, monkeypatch):
    run = start(client, monkeypatch, ESCALATE)
    done = answer(client, run, "confirm_ticket", True).json()
    assert done["tool_result"]["queue"] == "SEC-INCIDENT"
    assert done["tool_result"]["ticket_number"].startswith("INC")


def test_self_serve_can_be_marked_resolved(client, monkeypatch):
    run = start(client, monkeypatch, SELF_SERVE)
    assert run["path"] == "SELF_SERVE"
    done = answer(client, run, "self_serve", True).json()
    assert done["pending"] is None
    assert done["human_decision"] == {"resolved": True}


def test_failed_self_serve_goes_to_the_ticket_gate(client, monkeypatch):
    run = start(client, monkeypatch, SELF_SERVE)
    waiting = answer(client, run, "self_serve", False).json()
    assert waiting["pending"]["kind"] == "confirm_ticket"
    assert waiting["pending"]["ticket"]["source"] == "self_serve"


def test_out_of_scope_takes_no_action(client, log, monkeypatch):
    run = start(client, monkeypatch, OUT_OF_SCOPE)
    assert run["path"] == "OUT_OF_SCOPE"
    assert run["pending"] is None
    assert logged_rows(log)[0]["decision_path"] == "OUT_OF_SCOPE"


def test_retrieval_off_gives_no_tools_and_no_path(client, monkeypatch):
    run = start(client, monkeypatch, [text("Try restarting.")], use_retrieval=False)
    assert run["path"] == "NO_TOOLS"
    assert run["pending"] is None
    assert run["retrieved"] == []


def test_a_gate_can_only_be_answered_when_it_is_the_one_waiting(client, monkeypatch):
    run = start(client, monkeypatch, AUTO_FIX)
    assert answer(client, run, "confirm_ticket", True).status_code == 409
    assert answer(client, run, "self_serve", True).status_code == 409
    assert client.get(f"/api/runs/{run['id']}").json()["tool_result"] is None


def test_a_repeated_answer_changes_nothing(client, log, monkeypatch):
    run = start(client, monkeypatch, AUTO_FIX)
    assert answer(client, run, "confirm_fix", True).status_code == 200
    assert answer(client, run, "confirm_fix", True).status_code == 409
    assert len(logged_rows(log)) == 1


def test_a_paused_run_survives_a_restart(client, monkeypatch):
    run = start(client, monkeypatch, AUTO_FIX)
    main._graph.cache_clear()  # what a new process starts with
    read = client.get(f"/api/runs/{run['id']}").json()
    assert read["pending"]["kind"] == "confirm_fix"
    assert answer(client, run, "confirm_fix", True).json()["tool_result"]


def test_evaluations_start_empty_and_name_the_costs(client):
    body = client.get("/api/evaluations").json()
    assert body["runs"] == []
    assert body["costs"] == {"security": 2000, "wrong": 120, "minor": 60}


def test_evaluations_show_a_saved_run(client, monkeypatch):
    monkeypatch.setattr(runner, "run_triage", stub_triage)
    runner.save_run(runner.evaluate("rules", tiny=True))
    runs = client.get("/api/evaluations").json()["runs"]
    assert len(runs) == 1
    assert runs[0]["summary"]["n"] == 5


def test_evaluations_show_saved_retrieval_scores(client):
    assert client.get("/api/evaluations").json()["retrieval"] == []
    run = {"id": "20261107-retrieval-dev", "set": "dev"}
    retrieval_score.save_run(run)
    assert client.get("/api/evaluations").json()["retrieval"] == [run]


def test_tickets_to_review_have_requesters_and_labels(client):
    tickets = client.get("/api/tickets").json()
    assert len(tickets) == 206
    imported = next(t for t in tickets if t["id"].startswith("INC-"))
    assert imported["answer"]["cause"]
    assert imported["answer"]["checks"]
    first = tickets[0]
    assert first["text"] == "My VPN keeps disconnecting"
    assert first["answer"]["tools"] == ["reset_vpn_profile"]
    assert first["requester"]["id"] == "o.lang"
    assert first["latest"] is None


def test_tickets_show_the_latest_result(client, monkeypatch):
    monkeypatch.setattr(runner, "run_triage", stub_triage)
    runner.save_run(runner.evaluate("rules", tiny=True))
    tickets = {t["id"]: t for t in client.get("/api/tickets").json()}
    assert tickets["T-003"]["latest"]["action_correct"] is False
    assert tickets["T-001"]["latest"] is None


def test_held_out_tickets_stay_out_of_the_review(client):
    splits = json.loads((config.TICKETS_DIR / "splits.json").read_text())
    closed = set(splits["held_out"]) | set(splits["unseen_held_out"])
    ids = {t["id"] for t in client.get("/api/tickets").json()}
    assert not ids & closed
    assert not any(i.startswith("H-") for i in ids)


def test_a_held_out_run_shows_its_scores_but_no_tickets(client, monkeypatch):
    run = {"set": "held_out", "summary": {"n": 1}, "tickets": [{"id": "INC-1"}]}
    monkeypatch.setattr(main.runner, "load_runs", lambda: [run])
    assert client.get("/api/evaluations").json()["runs"] == [{**run, "tickets": []}]
    assert all(t["latest"] is None for t in client.get("/api/tickets").json())


def test_latest_results_keeps_the_newest_and_skips_the_held_out_set():
    runs = [
        {"set": "rules_held_out", "tickets": [{"id": "H-001"}]},
        {"set": "rules", "tickets": [{"id": "T-001", "action_correct": True}]},
        {"set": "rules", "tickets": [{"id": "T-001", "action_correct": False}]},
    ]
    assert main.latest_results(runs) == {
        "T-001": {"id": "T-001", "action_correct": True}
    }


def test_stats_count_finished_runs(client, monkeypatch):
    assert client.get("/api/stats").json()["n"] == 0
    start(client, monkeypatch, OUT_OF_SCOPE)
    body = client.get("/api/stats").json()
    assert body["n"] == 1
    assert body["low_sample"] is True
    assert body["paths"][0] == "SELF_SERVE"
