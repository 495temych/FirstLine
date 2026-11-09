"""The Harness view's API, read from the code. Search is stubbed and no model runs."""

import pytest
from fastapi.testclient import TestClient

from agent import config, decision, graph
from agent.tool_schemas import FIX_TOOLS
from backend import harness, main
from backend.tests.test_benchmark import run
from evals import runner

FOUND = [
    {
        "doc": "vpn-access",
        "kind": "playbook",
        "section": None,
        "text": "# VPN access\n\nReset the profile.",
        "score": 0.61,
        "highlights": [],
    }
]
DECIDED = {
    "id": "INC-VDA-0001",
    "text": "VPN drops\n\nIt drops after MFA.",
    "family": "VPN access",
    "path": "ESCALATE",
    "cause": "Expired device certificate",
    "tool": None,
    "queue": "NET-VPN",
    "invalid": False,
    "action_correct": "False",
    "expected_paths": ["AUTO_FIX"],
}


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    monkeypatch.setenv("MODEL_NAME", "claude-haiku-4-5-20251001")
    monkeypatch.setattr(harness.retrieval, "retrieve", lambda text: FOUND)
    runner.save_run(
        run(config.model_name(), "a-dev", (0.7, 0.001, 2.0), tickets=[DECIDED])
    )


def test_every_field_of_the_form_is_explained_in_order():
    fields = harness.view()["tool"]["fields"]
    names = list(decision.Decision.model_fields)
    assert [f["name"] for f in fields] == names
    assert set(harness.FIELDS) == set(names)
    assert names[0] == "rationale"
    path = next(f for f in fields if f["name"] == "path")
    assert path["required"]
    assert path["choices"] == ["SELF_SERVE", "AUTO_FIX", "ESCALATE", "OUT_OF_SCOPE"]


def test_every_check_and_read_names_code_that_exists():
    for item in [*harness.CHECKS, *harness.READS]:
        name, _, where = item["code"].partition(" in ")
        if not where:
            assert (config.ROOT / name).exists()
            continue
        module = (config.ROOT / where).read_text()
        assert f"def {name}" in module or f"{name} =" in module, item["code"]


def test_the_view_reads_the_model_search_and_instructions_from_the_code():
    view = harness.view()
    assert view["tool"]["name"] == decision.DECISION_TOOL_NAME
    assert view["fixes"] == len(FIX_TOOLS)
    assert view["model"]["attempts"] == graph.MODEL_ATTEMPTS
    assert view["model"]["max_tokens"] == 2048
    assert view["instructions"]["sections"][0].startswith("Step -1")
    assert "Hard rules" in view["instructions"]["sections"]
    assert view["loop"] == {"built": False, "calls": 1, "text": harness.LOOP}
    assert view["gates"] == [
        "Approve the fix",
        "Did the steps help?",
        "Approve the ticket",
    ]


def test_a_model_that_cant_be_forced_says_so(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "qwen/qwen3.7-flash")
    model = harness.view()["model"]
    assert model["forced"] is False
    assert model["provider"] == "alibaba"


def test_a_ticket_shows_what_the_model_read_and_answered(saved):
    assert harness.view()["examples"] == [
        {"id": "INC-VDA-0001", "title": "VPN drops", "family": "VPN access"}
    ]
    body = TestClient(main.app).get("/api/harness/tickets/INC-VDA-0001").json()
    assert body["found"] == [
        {"doc": "vpn-access", "kind": "playbook", "section": None, "score": 0.61}
    ]
    assert body["message"].startswith("User issue: VPN drops")
    assert "similarity score: 0.61" in body["message"]
    assert body["answer"]["queue"] == "NET-VPN"
    assert body["answer"]["right"] is False


def test_a_ticket_with_no_saved_decision_is_not_found(saved):
    client = TestClient(main.app)
    assert client.get("/api/harness/tickets/INC-NONE-0001").status_code == 404
    assert client.get("/api/harness").json()["answer"] == harness.ANSWER


def test_with_no_saved_run_there_are_no_examples(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    assert harness.view()["examples"] == []
    assert harness.read("INC-VDA-0001") is None
