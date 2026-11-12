"""API tests, with a stub model and temporary files."""

import json
import threading
from unittest.mock import patch

import anthropic
import httpx2
import psycopg
import pytest
from fastapi.testclient import TestClient

from agent import config, graph, models, records, tools
from agent.tests.fakes import (
    UNIT,
    FakeLLM,
    ScriptedLLM,
    call,
    escalate,
    fix,
    out_of_scope,
    steps,
    text,
)
from backend import main, store
from evals import retrieval_score, runner

AUTO_FIX = fix("reset_vpn_profile", "Reset the profile.", username="a.b")
ESCALATE = escalate("SEC-INCIDENT", "Needs review.")
SELF_SERVE = steps("Reseat the cable.")
OUT_OF_SCOPE = out_of_scope()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The API against temporary files, with retrieval stubbed."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(graph, "retrieve", lambda q: [UNIT])
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(retrieval_score, "RUNS_DIR", tmp_path / "retrieval")
    main._graph.cache_clear()
    yield TestClient(main.app)
    main._graph.cache_clear()


def finished(client, response):
    """The run a triage started, once its background work has finished."""
    assert response.status_code == 200
    run_id = response.json()["id"]
    worker = main.running.get(run_id)
    if worker is not None:
        worker.join(timeout=10)
    return client.get(f"/api/runs/{run_id}").json()


def start(client, monkeypatch, blocks, use_retrieval=True, requester="o.lang", **more):
    llm = FakeLLM(blocks)
    monkeypatch.setattr(graph, "_get_llm", lambda: llm)
    body = {"text": "My ticket", "use_retrieval": use_retrieval, "requester": requester}
    return finished(client, client.post("/api/triage", json=body | more))


def answer(client, run, gate, approved):
    url = f"/api/runs/{run['id']}/answer"
    return client.post(url, json={"gate": gate, "approved": approved})


def runs():
    return store.shared().runs()


def stub_triage(text, use_retrieval, **_):
    return {
        "path": "AUTO_FIX",
        "retrieved": [],
        "tool_name": "clear_teams_cache",
        "tool_input": {"username": "a.b"},
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "response_time_sec": 1.0,
        "cause": "Unknown",
        "rule": None,
    }


def test_health_reports_the_key(client, monkeypatch):
    assert client.get("/api/health").json() == {
        "status": "ok",
        "api_key": True,
        "model": models.label(config.model_name()),
    }
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert client.get("/api/health").json()["api_key"] is False


def test_starting_the_api_builds_nothing(client):
    assert not main._graph.built()


def test_triage_needs_a_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    body = {"text": "My ticket", "use_retrieval": True, "requester": "o.lang"}
    response = client.post("/api/triage", json=body)
    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_a_blank_ticket_is_refused(client):
    body = {"text": "   ", "use_retrieval": True, "requester": "o.lang"}
    assert client.post("/api/triage", json=body).status_code == 422


def test_a_ticket_needs_a_known_requester(client):
    body = {"text": "My ticket", "use_retrieval": True}
    assert client.post("/api/triage", json=body).status_code == 422
    body = {**body, "requester": "nobody.here"}
    assert client.post("/api/triage", json=body).status_code == 422


def test_sec04_turns_an_unlock_into_a_security_ticket(client, monkeypatch):
    monkeypatch.setattr(
        graph, "retrieve", lambda q: [{**UNIT, "doc": "account-lockout"}]
    )
    unlock = fix("unlock_ad_account", "Unlock it.", username="s.keller")
    run = start(client, monkeypatch, unlock, requester="s.keller")
    assert run["pending"]["kind"] == "confirm_ticket"
    assert run["pending"]["ticket"]["queue"] == "SEC-INCIDENT"
    assert run["rule"]["rule"] == "SEC-04"
    assert run["rule"]["proposed"]["tool_name"] == "unlock_ad_account"


def test_one_lockout_needs_a_technician_not_security(client, monkeypatch):
    monkeypatch.setattr(
        graph, "retrieve", lambda q: [{**UNIT, "doc": "account-lockout"}]
    )
    unlock = fix("unlock_ad_account", "Unlock it.", username="m.huber")
    run = start(client, monkeypatch, unlock, requester="m.huber")
    # An unlock is sensitive, so the Assistant hands it to a technician.
    assert run["pending"]["ticket"]["queue"] == "DESK-SUPPORT"
    assert run["rule"]["rule"] == "Sensitive fix"


def test_a_sensitive_fix_in_the_assistant_becomes_a_ticket(client, monkeypatch):
    run = start(client, monkeypatch, fix("restart_print_spooler", "Restart it."))
    assert run["pending"]["kind"] == "confirm_ticket"
    assert run["rule"]["rule"] == "Sensitive fix"


def test_requesters_list_the_rules_set_first(client):
    people = client.get("/api/requesters").json()
    assert len(people) == len(records.users())
    first = [p for p in people if p["rules_set"]]
    assert people[: len(first)] == first
    keller = next(p for p in people if p["id"] == "s.keller")
    assert keller["lockouts_24h"] == 2
    assert "email" not in keller


def test_a_failed_model_call_is_reported(client, monkeypatch):
    def fail():
        raise anthropic.APIConnectionError(request=httpx2.Request("POST", "http://x"))

    monkeypatch.setattr(graph, "_get_llm", fail)
    body = {"text": "My ticket", "use_retrieval": True, "requester": "o.lang"}
    run = finished(client, client.post("/api/triage", json=body))
    assert run["status"] == "failed"
    assert run["error"].startswith("The run failed: APIConnectionError")
    assert runs() == []


def test_a_run_starts_in_the_background_and_is_read_as_it_goes(client, monkeypatch):
    release = threading.Event()
    llm = FakeLLM(ESCALATE)

    def slow():
        release.wait(timeout=5)
        return llm

    monkeypatch.setattr(graph, "_get_llm", slow)
    body = {"text": "My ticket", "use_retrieval": True, "requester": "s.keller"}
    response = client.post("/api/triage", json=body)
    first = response.json()
    assert first["status"] == "running"
    assert first["query"] == "My ticket"
    assert first["requester"] == {
        "id": "s.keller",
        "department": "Client Services",
        "office": "Zürich",
    }
    assert first["design"] == "loop"
    release.set()
    run = finished(client, response)
    assert run["status"] == "waiting"
    assert run["pending"]["kind"] == "confirm_ticket"
    assert run["next"] == ["confirm_ticket"]


def test_the_assistant_keeps_each_loop_step_with_its_cost(client, monkeypatch):
    llm = ScriptedLLM(
        [call("lookup_requester")],
        ESCALATE,
        usage={"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100},
    )
    monkeypatch.setattr(graph, "_get_llm", lambda: llm)
    body = {"text": "My ticket", "use_retrieval": True, "requester": "s.keller"}
    run = finished(client, client.post("/api/triage", json=body))
    first, decided = run["steps"]
    assert first["tool"] == "lookup_requester"
    assert first["result"].startswith("Client Services, Zürich; 2 lockouts")
    assert first["cost_chf"] == pytest.approx(first["cost_usd"] * config.USD_TO_CHF)
    assert decided["tool"] == "record_decision"
    assert run["status"] == "waiting"


def test_an_example_reads_its_own_recorded_checks(client, monkeypatch):
    example = client.get("/api/examples").json()[0]
    assert example["id"] == "INC-ALP-0010"
    llm = ScriptedLLM(
        [call("run_check", step="account-lockout-source-check")], ESCALATE
    )
    monkeypatch.setattr(graph, "_get_llm", lambda: llm)
    body = {
        "text": example["text"],
        "use_retrieval": True,
        "requester": example["requester"],
        "ticket_id": example["id"],
    }
    run = finished(client, client.post("/api/triage", json=body))
    assert run["steps"][0]["result"].startswith("fail: ")


def test_examples_are_development_tickets_only(client):
    examples = client.get("/api/examples").json()
    splits = json.loads((config.TICKETS_DIR / "splits.json").read_text())
    assert len(examples) == 12  # one for each family with a playbook
    assert {e["id"] for e in examples} <= set(splits["dev"])
    assert all(e["text"].startswith(e["title"]) for e in examples)


def test_only_an_example_ticket_can_be_named(client):
    held_out = json.loads((config.TICKETS_DIR / "splits.json").read_text())
    body = {
        "text": "My ticket",
        "use_retrieval": True,
        "requester": "o.lang",
        "ticket_id": held_out["held_out"][0],
    }
    assert client.post("/api/triage", json=body).status_code == 422


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


def test_a_confirmed_fix_runs_and_is_recorded(client, monkeypatch):
    run = start(client, monkeypatch, AUTO_FIX)
    done = answer(client, run, "confirm_fix", True).json()
    assert done["pending"] is None
    assert done["human_decision"] == {"fix": True}
    assert done["tool_result"]["simulated"] is True
    (run,) = runs()
    assert run["path"] == "AUTO_FIX"
    assert run["answers"] == [{"gate": "confirm_fix", "approved": True}]


def test_a_declined_fix_gives_a_pre_filled_ticket(client, monkeypatch):
    run = start(client, monkeypatch, AUTO_FIX)
    monkeypatch.setattr(graph, "_get_llm", lambda: pytest.fail("a new model call"))
    waiting = answer(client, run, "confirm_fix", False).json()
    assert waiting["pending"]["kind"] == "confirm_ticket"
    assert waiting["pending"]["ticket"]["source"] == "decline"
    assert waiting["tool_result"] is None
    done = answer(client, run, "confirm_ticket", True).json()
    assert done["tool_result"]["action"] == "create_escalation_ticket"


def test_escalate_creates_no_ticket_when_declined(client, monkeypatch):
    run = start(client, monkeypatch, ESCALATE)
    assert run["pending"]["ticket"]["queue"] == "SEC-INCIDENT"
    done = answer(client, run, "confirm_ticket", False).json()
    assert done["tool_result"] is None
    assert done["human_decision"] == {"ticket": False}
    assert runs()[0]["answers"] == [{"gate": "confirm_ticket", "approved": False}]


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


def test_out_of_scope_takes_no_action(client, monkeypatch):
    run = start(client, monkeypatch, OUT_OF_SCOPE)
    assert run["path"] == "OUT_OF_SCOPE"
    assert run["pending"] is None
    assert runs()[0]["path"] == "OUT_OF_SCOPE"


def test_retrieval_off_gives_no_tools_and_no_path(client, monkeypatch):
    run = start(client, monkeypatch, [text("Try restarting.")], use_retrieval=False)
    assert run["path"] == "NO_TOOLS"
    assert run["pending"] is None
    assert run["retrieved"] == []
    assert runs() == []  # a comparison only, not a use of the Assistant


def test_a_gate_can_only_be_answered_when_it_is_the_one_waiting(client, monkeypatch):
    run = start(client, monkeypatch, AUTO_FIX)
    assert answer(client, run, "confirm_ticket", True).status_code == 409
    assert answer(client, run, "self_serve", True).status_code == 409
    assert client.get(f"/api/runs/{run['id']}").json()["tool_result"] is None


def test_a_repeated_answer_changes_nothing(client, monkeypatch):
    run = start(client, monkeypatch, AUTO_FIX)
    assert answer(client, run, "confirm_fix", True).status_code == 200
    assert answer(client, run, "confirm_fix", True).status_code == 409
    assert len(runs()[0]["answers"]) == 1


def test_a_paused_run_survives_a_restart(client, monkeypatch, empty_postgres):
    monkeypatch.setenv("SUPABASE_DB_URL", empty_postgres)
    run = start(client, monkeypatch, AUTO_FIX)
    main._graph.cache_clear()  # what a new process starts with
    store.shared.cache_clear()
    read = client.get(f"/api/runs/{run['id']}").json()
    assert read["pending"]["kind"] == "confirm_fix"
    assert answer(client, run, "confirm_fix", True).json()["tool_result"]
    with psycopg.connect(empty_postgres) as conn:
        kinds = conn.execute(
            "select kind, actor from events where ticket_id = %s order by id",
            [run["id"]],
        ).fetchall()
    assert kinds == [
        ("decided", "agent"),
        ("answered", "person"),
        ("action_ran", "code"),
    ]


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
