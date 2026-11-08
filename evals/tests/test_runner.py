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
        "cause": "Stale VPN profile",
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
    stubbed.joinpath("20260101T000000-dev.json").write_text(
        json.dumps({"id": "old", "yardsticks": {}})
    )
    runner.save_run({"id": "20270101T000000-dev", "yardsticks": {}})
    assert [r["id"] for r in runner.load_runs()] == ["20270101T000000-dev", "old"]


def test_the_command_saves_and_reports(stubbed, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["evals", "--set", "rules_held_out", "--tiny"])
    runpy.run_module("evals", run_name="__main__")
    out = capsys.readouterr().out
    assert "-rules_held_out-tiny" in out
    assert "cost per ticket CHF 0.0016" in out
    assert "CHF" in out
    assert len(list(stubbed.glob("*.json"))) == 1


def test_a_run_records_its_versions_and_measures(stubbed):
    run = runner.evaluate("rules", tiny=True)
    assert len(run["instructions_version"]) == 8
    assert len(run["tools_version"]) == 8
    assert len(run["kb_version"]) == 8
    assert run["yardsticks"].keys() == {"most_common", "classifier"}
    assert run["confusion"]["ESCALATE"]
    assert run["per_path"]["ESCALATE"]["n"] > 0
    assert run["by_family"]["Rules set"]["n"] == 5


def test_a_run_from_before_the_yardsticks_is_left_out(stubbed, tmp_path):
    (tmp_path / "old.json").write_text(json.dumps({"id": "old"}))
    assert runner.load_runs() == []


def test_imported_sets_score_family_and_cause(stubbed):
    run = runner.evaluate("unseen_dev")
    assert run["summary"]["n"] == 52
    assert run["by_family"].keys() == {"API timeouts", "Certificate expiry"}
    assert run["summary"]["cause_accuracy"] == 0


def test_tiny_only_applies_to_the_rules_sets(stubbed, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["evals", "--set", "dev", "--tiny"])
    with pytest.raises(SystemExit):
        runner.main()
    assert "--tiny only applies" in capsys.readouterr().err


def test_a_failed_ticket_has_no_cause(stubbed, monkeypatch):
    def fail(text, use_retrieval):
        raise RuntimeError("down")

    monkeypatch.setattr(runner, "run_triage", fail)
    row = runner.evaluate("rules", tiny=True)["tickets"][0]
    assert row["cause"] is None
    assert row["error"] == "RuntimeError: down"


def no_model(text, use_retrieval):
    raise AssertionError("re-scoring must not call the model")


def command(monkeypatch, *args):
    monkeypatch.setattr("sys.argv", ["evals", *args])
    runner.main()


def test_a_sample_takes_a_few_tickets_from_each_family_the_same_every_time():
    picked = runner.sample(runner.load_any("dev"))
    families = [answer["family"] for _, answer in picked]
    assert len(picked) == 12 * runner.SAMPLE_PER_FAMILY
    assert all(families.count(f) == runner.SAMPLE_PER_FAMILY for f in families)
    assert picked == runner.sample(runner.load_any("dev"))


def test_a_small_family_is_sampled_whole():
    pairs = [({"id": "A-1"}, {"family": "A"}), ({"id": "A-2"}, {"family": "A"})]
    assert runner.sample(pairs) == pairs


@pytest.mark.usefixtures("stubbed")
def test_a_sample_run_is_named_and_marked():
    run = runner.evaluate("unseen_dev", sampled=True)
    assert run["summary"]["n"] == 2 * runner.SAMPLE_PER_FAMILY
    assert run["sample"] is True
    assert run["id"].endswith("-unseen_dev-sample")


@pytest.mark.parametrize("name", ["rules", "held_out", "unseen_held_out"])
def test_only_the_practice_sets_can_be_sampled(stubbed, monkeypatch, capsys, name):
    with pytest.raises(SystemExit):
        command(monkeypatch, "--set", name, "--sample")
    assert "--sample only applies" in capsys.readouterr().err


@pytest.mark.usefixtures("stubbed")
def test_rescoring_marks_saved_decisions_against_new_labels(monkeypatch):
    run = runner.evaluate("rules", tiny=True)
    first = run["tickets"][0]["id"]
    monkeypatch.setattr(runner, "run_triage", no_model)
    relabelled = [
        (t, {**a, "paths": ["ESCALATE"], "tools": [], "queues": ["SEC-INCIDENT"]})
        for t, a in runner.load_any("rules")
    ]
    monkeypatch.setattr(runner, "load_any", lambda name, tiny=False: relabelled)
    new = runner.rescore(run)
    assert new["summary"]["path_accuracy"] == 1
    assert new["rescored_from"] == run["id"]
    assert new["id"].endswith("-rules-tiny-rescored")
    assert new["tickets"][0]["id"] == first
    assert new["tickets"][0]["input_tokens"] == 1000
    assert {k: new[k] for k in runner.VERSION_KEYS} == {
        k: run[k] for k in runner.VERSION_KEYS
    }
    assert runner.rescore(new)["rescored_from"] == run["id"]


def test_the_rescore_command_picks_the_newest_full_run_of_each_set(
    stubbed, monkeypatch, capsys
):
    for run in [runner.evaluate("rules", tiny=True), runner.evaluate("unseen_dev")]:
        runner.save_run(run)
    monkeypatch.setattr(runner, "run_triage", no_model)
    command(monkeypatch, "--rescore")
    assert "re-scored from" in capsys.readouterr().out
    saved = sorted(p.name for p in stubbed.glob("*.json"))
    assert [n for n in saved if n.endswith("-rescored.json")] == [
        n for n in saved if n.endswith("-unseen_dev-rescored.json")
    ]
    assert len(saved) == 3


def test_rescoring_a_missing_run_says_so(stubbed, monkeypatch, capsys):
    with pytest.raises(SystemExit):
        command(monkeypatch, "--rescore", "no-such-run")
    assert "no saved run no-such-run" in capsys.readouterr().err


def test_a_run_over_the_cap_stops_before_any_call(stubbed, monkeypatch, capsys):
    monkeypatch.setattr(runner, "SPENDING_CAP_CHF", 0.001)
    monkeypatch.setattr(runner, "run_triage", no_model)
    with pytest.raises(SystemExit):
        command(monkeypatch, "--set", "unseen_dev")
    err = capsys.readouterr().err
    assert "over the CHF 0.00 cap" in err
    assert "--max-chf" in err
    assert not list(stubbed.glob("*.json"))


def test_a_higher_limit_lets_the_run_go_ahead(stubbed, monkeypatch, capsys):
    monkeypatch.setattr(runner, "SPENDING_CAP_CHF", 0.001)
    command(monkeypatch, "--tiny", "--max-chf", "0.5")
    assert "About CHF 0.04 for 5 tickets" in capsys.readouterr().out
    assert len(list(stubbed.glob("*.json"))) == 1


def test_the_estimate_uses_the_dearest_saved_run_of_the_model():
    runs = [
        {"model": "m", "summary": {"cost_per_ticket_chf": 0.01}},
        {"model": "m", "summary": {"cost_per_ticket_chf": 0.02}},
        {"model": "other", "summary": {"cost_per_ticket_chf": 9.0}},
    ]
    assert runner.estimate_chf("m", 10, runs) == pytest.approx(0.2)
    assert runner.estimate_chf("unpriced", 10, []) is None


def test_a_model_with_no_price_needs_a_limit(stubbed, monkeypatch, capsys):
    monkeypatch.setenv("MODEL_NAME", "a-model-with-no-price")
    with pytest.raises(SystemExit):
        command(monkeypatch, "--tiny")
    assert "has no price" in capsys.readouterr().err
    command(monkeypatch, "--tiny", "--max-chf", "1")
    assert "unknown cost" in capsys.readouterr().out


def test_the_same_run_is_not_repeated(stubbed, monkeypatch, capsys):
    command(monkeypatch, "--tiny")
    capsys.readouterr()
    with pytest.raises(SystemExit):
        command(monkeypatch, "--tiny")
    assert "already ran these tickets" in capsys.readouterr().err
    command(monkeypatch, "--tiny", "--again")
    assert "About CHF" in capsys.readouterr().out


def test_every_run_records_its_labels_version(stubbed):
    assert len(runner.evaluate("rules", tiny=True)["labels_version"]) == 8
