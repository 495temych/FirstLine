"""The Retrieval page's API, with search stubbed. The encoder never runs here."""

import pytest
from fastapi.testclient import TestClient

from agent import config, retrieval
from backend import main, retrieval_view
from evals import retrieval_score, runner

RANKED = [
    {"doc": "vpn-access", "section": "Symptoms", "score": 0.61},
    {"doc": "wifi", "section": "Checks", "score": 0.42},
]
GIVEN = [
    {
        "doc": "vpn-access",
        "kind": "playbook",
        "section": None,
        "text": "The whole playbook",
        "score": 0.61,
        "highlights": [{"text": "The VPN drops", "score": 0.5}],
    }
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(retrieval_score, "RUNS_DIR", tmp_path / "retrieval")
    monkeypatch.setattr(retrieval, "rank_playbooks", lambda q: RANKED)
    monkeypatch.setattr(retrieval, "retrieve", lambda q: GIVEN)
    return TestClient(main.app)


def scored(name: str, when: str, tickets: list[dict] | None) -> dict:
    run = {
        "id": f"{when}-retrieval-{name}",
        "date": when,
        "set": name,
        "kb_version": "abcd1234",
        "summary": {"n": 1, "hit_rate": 1.0},
    }
    return run if tickets is None else {**run, "tickets": tickets}


def test_the_page_shows_the_newest_score_with_tickets_and_their_titles(client):
    ticket = {"id": "INC-VDA-0001", "right_score": 0.6}
    retrieval_score.save_run(scored("dev", "20261107T000000", [ticket]))
    retrieval_score.save_run(scored("dev", "20261108T000000", None))  # an old format
    retrieval_score.save_run(scored("held_out", "20261108T000000", [ticket]))
    body = client.get("/api/retrieval").json()
    dev = body["sets"]["dev"]
    assert dev["id"] == "20261107T000000-retrieval-dev"
    assert dev["tickets"][0]["title"]
    assert body["sets"]["unseen_dev"] is None
    assert "held_out" not in body["sets"]
    assert [h["set"] for h in body["history"]] == ["dev", "dev"]
    assert body["history"][0]["date"] < body["history"][1]["date"]


def test_the_page_states_the_rule_and_the_floor(client):
    body = client.get("/api/retrieval").json()
    assert body["rule"]["sure"] == retrieval.PLAYBOOK_SURE
    assert body["rule"]["margin"] == retrieval.PLAYBOOK_MARGIN
    assert body["floors"] == {"hit_rate": retrieval_score.HIT_RATE_FLOOR}
    assert set(body["questions"]) == {
        "hit_rate",
        "mean_reciprocal_rank",
        "recall",
        "false_match_rate",
    }


def test_the_decision_with_and_without_search_comes_from_saved_runs(client):
    summary = {
        "n": 129,
        "path_accuracy": 0.73,
        "path_margin": 0.08,
        "cost_per_ticket_chf": 0.005,
    }
    base = {
        "set": "dev",
        "model": config.model_name(),
        "summary": summary,
        "yardsticks": {},
    }
    runner.save_run({**base, "id": "a-dev"})
    body = client.get("/api/retrieval").json()["decision"]
    assert body["with_search"]["path_accuracy"] == 0.73
    assert body["without_search"] is None
    runner.save_run({**base, "id": "b-dev", "use_retrieval": False})
    assert retrieval_view._decision()["without_search"]["run"] == "b-dev"


def test_a_search_ranks_the_playbooks_and_says_why_one_matched(client):
    body = client.post("/api/retrieval/search", json={"text": "VPN drops"}).json()
    assert body["ranked"] == RANKED
    assert body["why"] == "sure"
    assert body["given"][0]["highlights"] == GIVEN[0]["highlights"]
    assert "text" not in body["given"][0]


def test_a_search_needs_text(client):
    assert client.post("/api/retrieval/search", json={"text": "  "}).status_code == 422


def test_an_empty_knowledge_base_matches_nothing(client, monkeypatch):
    monkeypatch.setattr(retrieval, "rank_playbooks", lambda q: [])
    monkeypatch.setattr(retrieval, "retrieve", lambda q: [])
    body = client.post("/api/retrieval/search", json={"text": "x"}).json()
    assert (body["ranked"], body["why"], body["given"]) == ([], None, [])


@pytest.mark.parametrize(
    ("best", "runner_up", "why"),
    [
        (0.55, 0.54, "sure"),
        (0.45, 0.25, "clear"),
        (0.45, 0.40, None),
        (0.30, -1.0, None),
    ],
)
def test_a_match_is_sure_or_clear(best, runner_up, why):
    assert retrieval.why_matched(best, runner_up) == why
