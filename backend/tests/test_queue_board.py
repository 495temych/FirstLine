"""The Queue, with the agent stubbed and the work done in the calling thread."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from agent import config
from backend import main, queue_board

FIX = {
    "path": "AUTO_FIX",
    "cause": "Stale VPN profile",
    "reasoning": "The profile predates the migration.",
    "tool_name": "reset_vpn_profile",
    "tool_input": {"username": "a.b"},
    "retrieved": [{"doc": "vpn", "section": "Fix", "score": 0.61, "text": "..."}],
    "usage": {"input_tokens": 4000, "output_tokens": 200},
}
ESCALATION = {
    **FIX,
    "path": "ESCALATE",
    "tool_name": "create_escalation_ticket",
    "tool_input": {
        "queue": "SEC-INCIDENT",
        "summary": "Repeat lockout.",
        "priority": "P2-High",
    },
}


@pytest.fixture
def board(monkeypatch):
    """A fresh board that works each ticket as soon as it's loaded."""
    fresh = queue_board.Board(submit=lambda work: work())
    monkeypatch.setattr(queue_board, "board", fresh)
    monkeypatch.setattr(queue_board, "run_triage", lambda text, use_retrieval: FIX)
    return fresh


@pytest.fixture
def client(board):
    return TestClient(main.app)


def loaded(client):
    response = client.post("/api/queue/load")
    assert response.status_code == 200
    return response.json()


def review(client, ticket_id, **body):
    body = {"seconds": 30, **body}
    return client.post(f"/api/queue/tickets/{ticket_id}/review", json=body)


def test_a_batch_comes_from_the_development_tickets_only(client):
    view = loaded(client)
    splits = json.loads((config.TICKETS_DIR / "splits.json").read_text())
    ids = [t["id"] for t in view["tickets"]]
    assert len(ids) == queue_board.BATCH_SIZE
    assert set(ids) <= set(splits["dev"])
    assert view["at_desk"] == len(splits["dev"]) - queue_board.BATCH_SIZE


def test_a_batch_mixes_kinds_of_request(client):
    ids = [t["id"] for t in loaded(client)["tickets"]]
    families = {ticket_id.split("-")[1] for ticket_id in ids}
    assert len(families) == queue_board.BATCH_SIZE


def test_the_next_batch_brings_new_tickets(client):
    first = {t["id"] for t in loaded(client)["tickets"]}
    second = loaded(client)
    assert len(second["tickets"]) == 2 * queue_board.BATCH_SIZE
    assert len({t["id"] for t in second["tickets"]} - first) == queue_board.BATCH_SIZE


def test_an_empty_desk_says_so(client, monkeypatch):
    monkeypatch.setattr(queue_board.board, "waiting_at_desk", list)
    response = client.post("/api/queue/load")
    assert response.status_code == 409


def test_tickets_are_worked_most_urgent_first_then_oldest():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    tickets = [
        {"priority": "low", "submitted_at": now.isoformat()},
        {"priority": "high", "submitted_at": (now + timedelta(hours=1)).isoformat()},
        {"priority": "high", "submitted_at": now.isoformat()},
        {"priority": "unknown", "submitted_at": now.isoformat()},
    ]
    ordered = sorted(tickets, key=queue_board.dispatch_order)
    assert [t["priority"] for t in ordered] == ["high", "high", "low", "unknown"]
    assert ordered[0]["submitted_at"] == now.isoformat()


def test_each_ticket_waits_for_review_with_its_decision_and_cost(client):
    ticket = loaded(client)["tickets"][0]
    assert ticket["state"] == "review"
    assert ticket["requester"]["name"]
    assert ticket["decision"]["tool"] == "reset_vpn_profile"
    assert ticket["decision"]["retrieved"] == [
        {"doc": "vpn", "section": "Fix", "score": 0.61}
    ]
    assert ticket["cost_chf"] == pytest.approx((4000 * 1 + 200 * 5) / 1e6 * 0.8)
    assert ticket["trace_id"] is None  # tests never trace


def test_an_escalation_shows_its_team_and_no_tool(board):
    board.tickets["T"] = queue_board.card(
        {
            "id": "T",
            "title": "Locked out",
            "description": "Again.",
            "priority": "high",
            "sla_plan": "Business hours",
            "submitted_at": "2026-01-01",
            "applications": [],
            "requester": "nobody",
        },
        {},
        "b",
    )
    queue_board.run_triage = lambda text, use_retrieval: ESCALATION
    board.work("T")
    decision = board.tickets["T"]["decision"]
    assert decision["queue"] == "SEC-INCIDENT"
    assert decision["tool"] is None
    assert board.tickets["T"]["requester"]["name"] == "nobody"


def test_a_failed_ticket_fails_alone(client, monkeypatch):
    calls = []

    def flaky(text, use_retrieval):
        calls.append(text)
        if len(calls) == 1:
            raise RuntimeError("model unavailable")
        return FIX

    monkeypatch.setattr(queue_board, "run_triage", flaky)
    view = loaded(client)
    assert view["counts"]["failed"] == 1
    assert view["counts"]["review"] == queue_board.BATCH_SIZE - 1
    failed = next(t for t in view["tickets"] if t["state"] == "failed")
    assert failed["error"] == "RuntimeError: model unavailable"


def test_approving_a_fix_runs_it(client):
    ticket = loaded(client)["tickets"][0]
    response = review(client, ticket["id"], verdict="approved")
    closed = response.json()
    assert closed["state"] == "closed"
    assert closed["review"]["outcome"]["action"] == "reset_vpn_profile"
    assert closed["review"]["seconds"] == 30


def test_approving_an_escalation_opens_the_ticket(client, monkeypatch):
    monkeypatch.setattr(
        queue_board, "run_triage", lambda text, use_retrieval: ESCALATION
    )
    ticket = loaded(client)["tickets"][0]
    outcome = review(client, ticket["id"], verdict="approved").json()["review"]
    assert outcome["outcome"]["queue"] == "SEC-INCIDENT"
    assert outcome["outcome"]["priority"] == "P2-High"


def test_a_correction_sends_it_to_the_chosen_team(client):
    ticket = loaded(client)["tickets"][0]
    assert review(client, ticket["id"], verdict="corrected").status_code == 422
    response = review(client, ticket["id"], verdict="corrected", queue="NET-VPN")
    assert response.json()["review"]["outcome"]["queue"] == "NET-VPN"


def test_a_rejection_needs_a_reason(client):
    ticket = loaded(client)["tickets"][0]
    assert (
        review(client, ticket["id"], verdict="rejected", note="  ").status_code == 422
    )
    response = review(client, ticket["id"], verdict="rejected", note="Wrong user")
    assert response.json()["review"]["note"] == "Wrong user"


def test_a_ticket_is_decided_once(client):
    ticket = loaded(client)["tickets"][0]
    assert review(client, ticket["id"], verdict="approved").status_code == 200
    assert review(client, ticket["id"], verdict="approved").status_code == 409


def test_an_unknown_ticket_is_not_found(client):
    assert review(client, "nope", verdict="approved").status_code == 404
    assert client.get("/api/queue/tickets/nope/trace").status_code == 404


def test_a_fix_that_cannot_run_stays_for_review(client, monkeypatch):
    broken = {**FIX, "tool_input": {"wrong": "x"}}
    monkeypatch.setattr(queue_board, "run_triage", lambda text, use_retrieval: broken)
    ticket = loaded(client)["tickets"][0]
    response = review(client, ticket["id"], verdict="approved")
    assert response.status_code == 422
    assert queue_board.board.get(ticket["id"])["state"] == "review"


def test_the_value_counts_approvals_against_review_time_and_cost(client):
    tickets = loaded(client)["tickets"]
    review(client, tickets[0]["id"], verdict="approved", seconds=60)
    review(client, tickets[1]["id"], verdict="rejected", note="No", seconds=120)
    value = client.get("/api/queue").json()["value"]
    assert value["reviewed"] == 2
    assert value["approved"] == 1
    assert value["review_seconds"] == 90
    assert value["minutes_saved"] == pytest.approx(15 - 3)
    assert value["net_chf"] == pytest.approx(12 - value["model_cost_chf"])


def test_an_empty_board_is_worth_nothing_yet(client):
    view = client.get("/api/queue").json()
    assert view["tickets"] == []
    assert view["value"]["agent_seconds"] is None
    assert view["value"]["net_chf"] == 0


def test_a_verdict_is_recorded_on_the_trace(client, monkeypatch):
    sent = []
    monkeypatch.setattr(queue_board.tracing, "new_trace_id", lambda seed: "t1")
    monkeypatch.setattr(queue_board.tracing, "trace_url", lambda t: f"https://lf/{t}")
    monkeypatch.setattr(queue_board.tracing, "verdict", lambda *args: sent.append(args))
    ticket = loaded(client)["tickets"][0]
    assert ticket["trace_url"] == "https://lf/t1"
    review(client, ticket["id"], verdict="rejected", note="Wrong user")
    assert sent == [("t1", "rejected", "Wrong user")]


def test_a_trace_reads_off_when_tracing_is(client):
    ticket = loaded(client)["tickets"][0]
    trace = client.get(f"/api/queue/tickets/{ticket['id']}/trace").json()
    assert trace == {"status": "off", "url": None, "steps": []}


def test_a_trace_waits_for_langfuse_then_shows_its_steps(client, monkeypatch):
    monkeypatch.setattr(queue_board.tracing, "new_trace_id", lambda seed: "t1")
    monkeypatch.setattr(queue_board.tracing, "trace_url", lambda t: "https://lf/t1")
    ticket = loaded(client)["tickets"][0]
    url = f"/api/queue/tickets/{ticket['id']}/trace"
    monkeypatch.setattr(queue_board.tracing, "trace_steps", lambda t: [])
    assert client.get(url).json()["status"] == "pending"
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = [
        {
            "name": "ChatAnthropic",
            "type": "GENERATION",
            "start_time": start + timedelta(seconds=2),
            "end_time": start + timedelta(seconds=4.5),
            "model": "claude-haiku",
            "usage_details": {"input": 3564, "output": 189},
            "total_cost": 0.0045,
        },
        {
            "name": "route_after_triage",
            "type": "CHAIN",
            "start_time": start,
            "end_time": start,
        },
        {
            "name": "retrieve",
            "type": "CHAIN",
            "start_time": start,
            "end_time": start + timedelta(seconds=2),
        },
    ]
    monkeypatch.setattr(queue_board.tracing, "trace_steps", lambda t: observations)
    trace = client.get(url).json()
    assert trace["status"] == "ready"
    assert trace["url"] == "https://lf/t1"
    assert [s["name"] for s in trace["steps"]] == ["retrieve", "ChatAnthropic"]
    model_call = trace["steps"][1]
    assert model_call["start_ms"] == 2000
    assert model_call["duration_ms"] == 2500
    assert model_call["input_tokens"] == 3564
    assert model_call["cost_usd"] == 0.0045
