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


def always_escalate(text, use_retrieval, **_):
    queue = {"queue": "SEC-INCIDENT", "summary": "s", "priority": "P2-High"}
    return result("ESCALATE", "create_escalation_ticket", queue)


@pytest.fixture
def stubbed(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(runner, "run_triage", always_escalate)
    # The sums below assume Haiku 4.5's prices, whatever the default.
    monkeypatch.setenv("MODEL_NAME", "claude-haiku-4-5-20251001")
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
    def fail_once(text, use_retrieval, **_):
        monkeypatch.setattr(runner, "run_triage", always_escalate)
        raise TimeoutError("no answer")

    monkeypatch.setattr(runner, "run_triage", fail_once)
    run = runner.evaluate("rules", tiny=True)
    assert run["summary"]["n"] == 5
    assert run["summary"]["failed"] == 1
    # Tickets run in parallel, so any one of them may be the one that failed.
    failed = [t for t in run["tickets"] if t["error"]]
    assert [t["error"] for t in failed] == ["TimeoutError: no answer"]
    assert failed[0]["path"] == "ESCALATE"
    assert failed[0]["cost_usd"] == 0


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
    def fail(text, use_retrieval, **_):
        raise RuntimeError("down")

    monkeypatch.setattr(runner, "run_triage", fail)
    row = runner.evaluate("rules", tiny=True)["tickets"][0]
    assert row["cause"] is None
    assert row["error"] == "RuntimeError: down"


def no_model(text, use_retrieval, **_):
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


def test_the_cost_the_provider_reports_beats_the_list_price(stubbed, monkeypatch):
    def reported(text, use_retrieval, **_):
        usage = {"input_tokens": 1000, "output_tokens": 200, "cost_usd": 0.0001}
        return {**always_escalate(text, use_retrieval), "usage": usage}

    monkeypatch.setattr(runner, "run_triage", reported)
    run = runner.evaluate("rules", tiny=True)
    assert run["tickets"][0]["cost_usd"] == 0.0001


def test_an_unreadable_decision_is_marked_invalid(stubbed, monkeypatch):
    def unreadable(text, use_retrieval, **_):
        return {**always_escalate(text, use_retrieval), "reasoning": runner.UNREADABLE}

    monkeypatch.setattr(runner, "run_triage", unreadable)
    run = runner.evaluate("rules", tiny=True)
    assert run["summary"]["invalid"] == 5
    assert run["summary"]["failed"] == 0


def test_a_run_records_who_served_it(stubbed, monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "mistralai/mistral-small-2603")
    run = runner.evaluate("rules", tiny=True)
    assert run["serving"] == {
        "lab": "openrouter",
        "provider": "mistral/eu",
        "region": "EU",
        "effort": None,
    }
    assert runner.serving("claude-future")["lab"] == "anthropic"


def test_the_model_flag_picks_the_model(stubbed, monkeypatch, capsys):
    monkeypatch.setenv("MODEL_NAME", "")  # restored after the flag sets it
    argv = ["evals", "--tiny", "--model", "gpt-5-nano"]
    monkeypatch.setattr("sys.argv", argv)
    runpy.run_module("evals", run_name="__main__")
    assert "gpt-5-nano" in capsys.readouterr().out
    assert runner.config.model_name() == "gpt-5-nano"


def test_each_ticket_runs_in_queue_mode_with_its_requester(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    seen, ids = [], []

    def overridden(text, use_retrieval, requester=None, mode=None, ticket_id=None):
        seen.append((requester, mode))
        ids.append(ticket_id)
        rule = {"rule": "SEC-04", "reason": "r", "proposed": {}}
        return {**always_escalate(text, use_retrieval), "rule": rule}

    monkeypatch.setattr(runner, "run_triage", overridden)
    run = runner.evaluate("rules", tiny=True)
    tickets = {t["id"]: t for t, _ in runner.load_any("rules", tiny=True)}
    assert seen
    assert all(mode == "queue" for _, mode in seen)
    assert {r for r, _ in seen} == {t["requester"] for t in tickets.values()}
    assert set(ids) == set(tickets)  # so the loop's checks read the right ticket
    assert {row["rule"] for row in run["tickets"]} == {"SEC-04"}
    assert run["summary"]["sec04_failures"] == 0


def test_the_rules_are_part_of_the_tools_version(tmp_path, monkeypatch):
    before = runner.tools_version()
    (tmp_path / "agent").mkdir()
    rules = runner.config.ROOT / "agent" / "rules.py"
    (tmp_path / "agent" / "rules.py").write_bytes(rules.read_bytes() + b"# changed")
    monkeypatch.setattr(runner.config, "ROOT", tmp_path)
    assert runner.tools_version() != before


def test_the_design_is_part_of_the_version(monkeypatch):
    monkeypatch.setenv("DESIGN", "one call")
    one_call = runner.version()
    assert one_call == runner._hash(
        f"{runner.instructions_version()}{runner.tools_version()}".encode()
    )  # unchanged, so saved one-call runs still match
    monkeypatch.setenv("DESIGN", "loop")
    assert runner.version() != one_call


def test_the_design_flag_runs_the_loop_and_tells_the_runs_apart(
    stubbed, monkeypatch, capsys
):
    monkeypatch.setenv("DESIGN", "")
    command(monkeypatch, "--tiny")
    capsys.readouterr()
    command(monkeypatch, "--tiny", "--design", "loop")  # not a repeat of one call
    out = capsys.readouterr().out
    assert "-rules-loop-tiny" in out
    assert "  loop  " in out
    runs = runner.load_runs()
    assert sorted(run["design"] for run in runs) == ["loop", "one call"]
    with pytest.raises(SystemExit):
        command(monkeypatch, "--tiny", "--design", "loop")
    assert "same design" in capsys.readouterr().err


def test_a_loop_estimate_assumes_the_step_limit():
    runs = [
        {"model": "m", "summary": {"cost_per_ticket_chf": 0.001}},
        {"model": "m", "design": "loop", "summary": {"cost_per_ticket_chf": 0.5}},
    ]
    turns = runner.config.MAX_LOOKUPS + 1
    assert runner.estimate_chf("m", 10, runs, "loop") == pytest.approx(
        0.001 * turns * 10
    )
    assert runner.estimate_chf("m", 10, runs) == pytest.approx(0.01)
    dear = [{"model": "m", "summary": {"cost_per_ticket_chf": 0.01}}]
    capped = runner.estimate_chf("m", 10, dear, "loop")
    assert capped == pytest.approx(runner.config.MAX_LOOP_CHF * 10)


def test_a_loop_run_keeps_each_tickets_steps(stubbed, monkeypatch):
    step = {"id": "s1", "tool": "lookup_requester", "ok": True, "result": "r"}

    def looped(text, use_retrieval, **_):
        return {
            **always_escalate(text, use_retrieval),
            "steps": [step],
            "stopped": None,
        }

    monkeypatch.setattr(runner, "run_triage", looped)
    run = runner.evaluate("rules", tiny=True)
    assert run["tickets"][0]["steps"] == [step]
    again = runner.rescore(run)
    assert again["tickets"][0]["steps"] == [step]
    assert again["design"] == run["design"]


def test_loop_runs_stay_out_of_the_one_call_views(monkeypatch):
    one = {"id": "b", "set": "dev", "tiny": False, "model": "m", "yardsticks": {}}
    looped = {**one, "id": "a", "design": "loop"}
    monkeypatch.setattr(runner, "load_runs", lambda: [looped, one])
    monkeypatch.setenv("MODEL_NAME", "m")
    monkeypatch.setenv("DESIGN", "one call")
    assert [run["id"] for run in runner.default_runs()] == ["b"]
    assert {r["id"] for r in runner.to_rescore([], [looped, one])} == {"a", "b"}
