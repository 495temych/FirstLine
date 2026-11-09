"""The business case's sums, against hand-worked numbers."""

import pytest
from fastapi.testclient import TestClient

from backend import economics, main, queue_board
from evals import runner, scoring

RATES = {"minutes_by_hand": 15, "chf_per_hour": 60}
SUMMARY = {
    "n": 100,
    "action_accuracy": 0.7,
    "cost_per_ticket_chf": 0.01,
    "mistake_cost_chf": 6000,
}
WRONG_ANSWER = {
    "paths": ["ESCALATE"],
    "tools": [],
    "queues": ["NETWORK"],
}


def test_net_saving_follows_the_business_goal():
    saved = economics.net(0.7, 2, (0.01, 1.0))
    assert saved["minutes_saved"] == pytest.approx(0.7 * 15 - 2)
    assert saved["time_chf"] == pytest.approx(8.5)
    assert saved["net_chf"] == pytest.approx(8.5 - 0.01 - 1.0)


def test_break_even_is_review_time_over_time_by_hand():
    assert economics.break_even(2) == pytest.approx(2 / 15)
    assert economics.break_even(3, 10) == pytest.approx(0.3)


def test_the_catch_rate_needed_to_pay():
    assert economics.catch_needed(8.5, 0.5, 80) == pytest.approx(0.9)
    assert economics.catch_needed(9, 0, 3) == 0.0
    assert economics.catch_needed(1, 0, 0) is None


@pytest.fixture
def saved_run(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    run = {
        "id": "a-dev",
        "set": "dev",
        "model": "claude-haiku-4-5-20251001",
        "tiny": False,
        "summary": SUMMARY,
        "yardsticks": {},
    }
    runner.save_run(run)
    runner.save_run({**run, "id": "b-rules", "set": "rules"})
    return run


def test_projected_prices_only_the_mistakes_nobody_catches(saved_run):
    layer = economics.projected(0.9, **RATES)
    assert layer is not None
    assert layer["source"] == "a-dev"
    assert layer["bill_chf"] == 60
    assert layer["mistakes_chf"] == pytest.approx(6)
    assert layer["net_chf"] == pytest.approx(8.5 - 0.01 - 6)
    assert layer["net_low"] < layer["net_chf"] < layer["net_high"]
    assert layer["share_margin"] == scoring.margin(0.7, 100)
    assert layer["per_year_chf"] == pytest.approx(layer["net_chf"] * 1500)
    assert layer["net_none_caught"] == pytest.approx(8.5 - 0.01 - 60)
    assert layer["net_all_caught"] == pytest.approx(8.5 - 0.01)


def test_projected_reads_only_the_default_models_full_runs(saved_run, monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "claude-haiku-4-5-20251001")
    runner.save_run({**saved_run, "id": "c-dev", "model": "gpt-6-luna"})
    runner.save_run({**saved_run, "id": "d-dev-sample", "sample": True})
    layer = economics.projected(**RATES)
    assert layer is not None
    assert layer["source"] == "a-dev"


def test_catching_every_mistake_leaves_only_time_and_model(saved_run):
    layer = economics.projected(1.0, **RATES)
    assert layer is not None
    assert layer["net_chf"] == pytest.approx(8.5 - 0.01)


def test_no_development_run_means_nothing_projected(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    assert economics.projected(**RATES) is None


def reviewed(ticket_id, verdict, seconds=60, path="AUTO_FIX"):
    decision = {"path": path, "tool": "reset_vpn_profile", "queue": None}
    review = {"verdict": verdict, "seconds": seconds}
    return {"id": ticket_id, "decision": decision, "review": review, "cost_chf": 0.01}


@pytest.fixture
def labels(monkeypatch):
    right = {"paths": ["AUTO_FIX"], "tools": ["reset_vpn_profile"], "queues": []}
    answers = {"T1": right, "T2": WRONG_ANSWER, "T3": WRONG_ANSWER, "T4": right}
    monkeypatch.setattr(economics, "_answers", lambda: answers)


def test_observed_measures_review_time_and_the_mistakes_that_slipped(labels):
    tickets = [
        reviewed("T1", "approved", 30),
        reviewed("T2", "approved", 90),  # wrong, and approved: it slipped
        reviewed("T3", "rejected", 120),  # wrong, and caught
        {**reviewed("T4", "approved"), "review": None},  # not reviewed yet
    ]
    layer = economics.observed(tickets, **RATES)
    assert layer is not None
    assert (layer["n"], layer["wrong"], layer["slipped"]) == (3, 2, 1)
    assert layer["share"] == pytest.approx(2 / 3)
    assert layer["review_minutes"] == pytest.approx(80 / 60)
    assert layer["catch_rate"] == pytest.approx(0.5)
    assert layer["bill_chf"] == pytest.approx(2 * scoring.COST_WRONG / 3)
    assert layer["mistakes_chf"] == pytest.approx(scoring.COST_WRONG / 3)


def test_a_ticket_with_no_label_or_decision_costs_nothing(labels):
    unknown = {**reviewed("T9", "approved"), "decision": None}
    layer = economics.observed([reviewed("T1", "approved"), unknown], **RATES)
    assert layer is not None
    assert (layer["wrong"], layer["catch_rate"], layer["catch_needed"]) == (
        0,
        1.0,
        None,
    )


def test_nothing_reviewed_means_nothing_observed():
    assert economics.observed([reviewed("T1", "approved") | {"review": None}]) is None


def test_the_route_moves_with_the_reader_s_assumptions(saved_run, monkeypatch):
    monkeypatch.setattr(queue_board, "board", queue_board.Board(submit=lambda w: w()))
    client = TestClient(main.app)
    body = client.get("/api/business").json()
    assert body["assumptions"]["catch_rate"] == economics.CATCH_RATE
    assert body["observed"] is None
    slower = client.get(
        "/api/business",
        params={"minutes_by_hand": 30, "chf_per_hour": 120, "catch_rate": 1},
    ).json()
    assert slower["rates"] == {
        "minutes_by_hand": 30,
        "chf_per_hour": 120,
        "catch_rate": 1,
    }
    assert slower["projected"]["net_chf"] > body["projected"]["net_chf"]
    assert client.get("/api/business", params={"catch_rate": 2}).status_code == 422


def test_the_labels_read_are_the_queue_s_own():
    answers = economics._answers()
    assert answers
    assert {ticket_id.startswith("INC-") for ticket_id in answers} == {True}
