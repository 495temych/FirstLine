"""Each group's findings, built from made-up saved runs and an empty Queue."""

import pytest
from fastapi.testclient import TestClient

from agent import config
from backend import insights, main
from backend.tests.test_benchmark import run
from evals import retrieval_score, runner


@pytest.fixture
def no_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(retrieval_score, "RUNS_DIR", tmp_path / "retrieval")
    monkeypatch.setenv("MODEL_NAME", "claude-haiku-4-5-20251001")


def retrieval_run(name: str, summary: dict) -> dict:
    return {"id": f"r-{name}", "set": name, "summary": summary, "tickets": []}


@pytest.fixture
def saved(no_runs):
    for name in ("dev", "unseen_dev", "rules"):
        runner.save_run(
            run(config.model_name(), f"a-{name}", (0.7, 0.001, 2.0), name=name)
        )
        runner.save_run(run("gpt-6-luna", f"b-{name}", (0.8, 0.002, 1.0), name=name))
    retrieval_score.save_run(retrieval_run("dev", {"n": 129, "hit_rate": 1.0}))
    retrieval_score.save_run(
        retrieval_run("unseen_dev", {"n": 52, "false_match_rate": 0.04})
    )


def texts(group: dict) -> str:
    return " ".join(f["text"] for f in group["findings"])


def test_with_no_runs_each_group_says_what_would_fill_it(no_runs):
    groups = insights.groups()
    assert set(groups) == {"try", "worth", "how"}
    assert "3 human gates" in texts(groups["try"])
    assert "No Queue reviews yet" in texts(groups["try"])
    assert "has no development run yet" in texts(groups["worth"])
    assert "Search finds" not in texts(groups["how"])


def test_findings_come_from_the_saved_runs(saved):
    groups = insights.groups()
    worth = texts(groups["worth"])
    assert "On Claude Haiku 4.5, the default, each ticket saves CHF" in worth
    assert "models save" in worth
    assert "The free classifier" in worth
    how = groups["how"]["findings"]
    assert how[0]["text"].startswith("Search finds the right playbook for 100% of 129")
    assert how[0]["source"] == "r-dev"
    assert "Claude Haiku 4.5 chooses the right path for 70%" in how[1]["text"]
    assert how[1]["view"] == "evaluations"
    assert all(f["source"] for g in groups.values() for f in g["findings"])


def test_a_loss_is_called_a_loss(saved):
    assert insights._saves(-8) == "loses CHF 8.00"
    assert insights._saves(2.5) == "saves CHF 2.50"


def test_the_insights_route_answers_each_groups_question(no_runs):
    body = TestClient(main.app).get("/api/insights").json()
    assert body["worth"]["question"] == "Does it pay, and on which model?"


def test_the_queues_reviews_say_how_technicians_did(no_runs, monkeypatch):
    reviewed = {
        "id": "INC-1",
        "review": {"verdict": "approved", "seconds": 90},
        "cost_chf": 0.001,
    }
    tickets = [{**reviewed, "id": f"INC-{i}"} for i in range(8)]
    monkeypatch.setattr(insights.economics, "_price", lambda ticket: 0)
    monkeypatch.setattr(
        insights.queue_board.board, "view", lambda: {"tickets": tickets}
    )
    finding = insights.groups()["try"]["findings"][1]
    assert finding["text"].startswith("Technicians approved 100% of 8 reviewed")
    assert "1.5 minutes each" in finding["text"]
    assert finding["n"] == 8
