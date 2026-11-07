"""Retrieval scoring, with retrieval stubbed. The encoder never runs here."""

import json

import pytest

from agent import retrieval
from evals import import_tickets, retrieval_score, runner

FAMILIES = {
    "ALP": {"name": "Account lockout", "doc": "account-access"},
    "CES": {"name": "Certificate expiry", "doc": None},
}
ALP = {"id": "INC-ALP-0001"}
CES = {"id": "INC-CES-0001"}
MATCH = {"doc": "account-access", "kind": "playbook", "score": 0.6}
WRONG = {"doc": "vpn", "kind": "playbook", "score": 0.4}
POLICY = {"doc": "sec-04", "kind": "policy", "score": 0.7}
RANKED = [{"doc": "account-access"}, {"doc": "vpn"}]
WRONG_FIRST = [{"doc": "vpn"}, {"doc": "account-access"}]


@pytest.fixture
def runs(tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval_score, "RUNS_DIR", tmp_path / "retrieval")
    monkeypatch.setattr(retrieval_score, "HIT_RATE_FLOOR", 0)
    monkeypatch.setattr(retrieval, "retrieve", lambda q: [MATCH])
    monkeypatch.setattr(retrieval, "rank_playbooks", lambda q: RANKED)


def rows() -> list[dict]:
    return [
        retrieval_score.score_ticket(ALP, "account-access", [MATCH, WRONG], RANKED),
        retrieval_score.score_ticket(
            ALP, "account-access", [WRONG, MATCH], WRONG_FIRST
        ),
        retrieval_score.score_ticket(CES, None, [WRONG], RANKED),
        retrieval_score.score_ticket(CES, None, [], RANKED),
    ]


def test_only_the_top_match_counts_as_a_hit():
    hit, miss, *_ = rows()
    assert hit["hit"]
    assert not miss["hit"]
    assert miss["top"] == "vpn"


def test_a_family_with_no_document_should_match_nothing():
    *_, false_match, clean = rows()
    assert false_match["false_match"]
    assert not clean["false_match"]
    assert clean["top"] is None


def test_a_policy_is_not_a_playbook_match():
    row = retrieval_score.score_ticket(CES, None, [POLICY], RANKED)
    assert not row["false_match"]
    assert row["top"] is None


def test_a_covered_family_that_finds_nothing_is_a_miss():
    row = retrieval_score.score_ticket(ALP, "account-access", [], RANKED)
    assert not row["hit"]
    assert not row["false_match"]


def test_the_summary_keeps_covered_and_uncovered_apart():
    assert retrieval_score.summarize(rows()) == {
        "n": 4,
        "covered": 2,
        "uncovered": 2,
        "hit_rate": 0.5,
        "mean_reciprocal_rank": 0.75,
        "recall": 1.0,
        "false_match_rate": 0.5,
    }


def test_a_playbook_outside_the_first_two_is_a_recall_miss():
    ranked = [{"doc": "a"}, {"doc": "b"}, {"doc": "account-access"}]
    row = retrieval_score.score_ticket(ALP, "account-access", [], ranked)
    summary = retrieval_score.summarize([row])
    assert summary["recall"] == 0
    assert summary["mean_reciprocal_rank"] == pytest.approx(1 / 3)


def test_a_rate_with_no_tickets_is_unknown_not_zero():
    summary = retrieval_score.summarize(rows()[:2])
    assert summary["false_match_rate"] is None


def test_families_are_scored_apart():
    family = retrieval_score.by_family(rows(), FAMILIES)["CES"]
    assert family["name"] == "Certificate expiry"
    assert family["n"] == 2
    assert family["hit_rate"] is None


def test_a_set_is_scored_saved_and_reloaded(runs):
    run = retrieval_score.evaluate("dev")
    retrieval_score.save_run(run)
    assert retrieval_score.load_runs() == [run]
    assert run["summary"]["n"] == 129
    assert run["threshold"] == retrieval.PLAYBOOK_THRESHOLD
    assert len(run["kb_version"]) == 8


def test_the_query_is_the_title_and_description(monkeypatch):
    queries = []
    monkeypatch.setattr(retrieval, "retrieve", lambda q: queries.append(q) or [MATCH])
    monkeypatch.setattr(retrieval, "rank_playbooks", lambda q: RANKED)
    retrieval_score.evaluate("unseen_dev")
    ticket = retrieval_score.load_split("unseen_dev")[0]
    assert queries[0] == f"{ticket['title']}\n\n{ticket['description']}"


def test_the_knowledge_base_version_follows_its_files(tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval_score.config, "KB_DIR", tmp_path)
    (tmp_path / "a.md").write_text("one")
    first = retrieval_score.kb_version()
    (tmp_path / "a.md").write_text("two")
    assert retrieval_score.kb_version() != first


def test_the_command_scores_both_development_sets(runs, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["evals", "--retrieval"])
    runner.main()
    out = capsys.readouterr().out
    assert "dev: 129 tickets" in out
    assert "unseen_dev: 52 tickets" in out
    assert retrieval_score.load_runs() == []


def test_the_command_saves_a_chosen_set_when_asked(runs, monkeypatch, capsys):
    argv = ["evals", "--retrieval", "--split", "kb", "--save"]
    monkeypatch.setattr("sys.argv", argv)
    runner.main()
    assert "kb: 384 tickets" in capsys.readouterr().out
    assert [r["set"] for r in retrieval_score.load_runs()] == ["kb"]


@pytest.mark.usefixtures("runs")
def test_a_hit_rate_under_the_floor_fails_the_check(monkeypatch, capsys):
    monkeypatch.setattr(retrieval_score, "HIT_RATE_FLOOR", 0.95)
    with pytest.raises(SystemExit, match="under 95%"):
        retrieval_score.main(["dev"], save=False)
    capsys.readouterr()


def test_every_family_has_a_name_and_a_real_document():
    families = retrieval_score.load_families()
    assert len(families) == 14
    docs = {u["doc"] for u in retrieval._get_units()}
    assert {f["doc"] for f in families.values()} - {None} <= docs
    for family in import_tickets.UNSEEN_FAMILIES:
        assert families[family]["doc"] is None


def test_the_saved_scores_are_the_before_numbers():
    saved = retrieval_score.RUNS_DIR.glob("*.json")
    sets = {json.loads(p.read_text())["set"] for p in saved}
    assert sets >= {"dev", "unseen_dev"}
