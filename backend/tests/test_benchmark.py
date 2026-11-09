"""Ranking models by net saving, and the Pareto front, on made-up runs."""

import pytest

from backend import benchmark

YARD = {
    "n": 10,
    "path_accuracy": 0.6,
    "path_margin": 0.3,
    "action_accuracy": 0.2,
    "action_margin": 0.2,
    "mistake_cost_chf": 1200,
}


def run(model, rid, measures, **kind):
    share, cost, time = measures
    summary = {
        "n": 10,
        "path_accuracy": share,
        "path_margin": 0.2,
        "action_accuracy": share,
        "mistake_cost_chf": 120,
        "cost_per_ticket_chf": cost,
        "time_p50_sec": time,
        "time_p90_sec": time * 2,
        "balanced_accuracy": share,
        "failed": 0,
        "invalid": 0,
    }
    return {
        "id": rid,
        "set": kind.get("name", "dev"),
        "model": model,
        "tiny": kind.get("tiny", False),
        "sample": kind.get("sample", False),
        "summary": summary,
        "tickets": kind.get("tickets", []),
        "yardsticks": {"most_common": YARD, "classifier": YARD},
    }


RUNS = [
    run("cheap", "3", (0.75, 0.001, 1.0)),
    run("dear", "2", (0.9, 0.01, 3.0)),
    run("beaten", "1", (0.5, 0.02, 4.0)),
    run("cheap", "0", (0.1, 0.001, 1.0)),  # an older run of the same model
    run("other set", "5", (1.0, 0.0, 0.1), name="rules"),
]


def test_each_model_uses_its_newest_full_run_of_the_set():
    sampled = run("sampled", "4", (1.0, 0.002, 0.1), sample=True)
    newer_sample = run("cheap", "9", (1.0, 0.002, 0.1), sample=True)
    newest = benchmark.newest_runs("dev", [newer_sample, sampled, *RUNS])
    assert set(newest) == {"cheap", "dear", "beaten", "sampled"}
    assert newest["cheap"]["id"] == "3"  # a full run beats a newer sample
    assert newest["sampled"]["sample"]


def test_models_are_ranked_by_net_saving_with_the_yardsticks_beside_them():
    entries = benchmark.table("dev", RUNS)["entries"]
    names = [e["model"] for e in entries]
    assert names[:3] == ["dear", "cheap", "beaten"]
    assert {e["kind"] for e in entries} == {"model", "yardstick"}
    assert entries[0]["net_low"] < entries[0]["net_chf"] < entries[0]["net_high"]


def test_the_front_leaves_out_a_model_beaten_on_both_counts():
    entries = {e["model"]: e for e in benchmark.table("dev", RUNS)["entries"]}
    assert entries["cheap"]["front_cost"]
    assert entries["dear"]["front_cost"]
    assert not entries["beaten"]["front_cost"]
    assert not entries["beaten"]["front_time"]
    assert not entries["classifier"]["front_cost"]


def test_a_tie_on_both_counts_keeps_both_on_the_front():
    a = {"model": "a", "net_chf": 1.0, "cost_chf": 0.1}
    b = {"model": "b", "net_chf": 1.0, "cost_chf": 0.1}
    assert benchmark.front([a, b], "cost_chf") == {"a", "b"}


def test_a_model_with_no_value_on_the_axis_cant_be_placed():
    a = {"model": "a", "net_chf": 1.0, "time_p50_sec": None}
    assert benchmark.front([a], "time_p50_sec") == set()


def test_no_runs_gives_an_empty_table():
    assert benchmark.table("dev", [])["entries"] == []


def test_the_command_prints_the_table(monkeypatch, capsys):
    monkeypatch.setattr(benchmark.runner, "load_runs", lambda: RUNS)
    monkeypatch.setattr("sys.argv", ["backend.benchmark"])
    benchmark.main()
    out = capsys.readouterr().out
    assert "* dear" in out
    assert "  beaten" in out
    assert out.index("dear") < out.index("beaten")


@pytest.mark.parametrize("value", [None, 0.5])
def test_cells_show_missing_values(value):
    assert benchmark._cell(value, ".1f") == ("n/a" if value is None else "0.5")


SECURITY = {"mistake_cost_chf": benchmark.scoring.COST_SECURITY}


def _sets(rules_tickets=()):
    runs = [
        *RUNS,
        run("cheap", "6", (0.8, 0.001, 1.0), name="rules"),
        run("dear", "7", (0.9, 0.01, 3.0), name="rules", tickets=list(rules_tickets)),
        run("cheap", "8", (0.9, 0.001, 1.0), name="unseen_dev"),
        run("dear", "9", (0.5, 0.01, 3.0), name="unseen_dev"),
    ]
    return benchmark.view(runs)


def test_the_rule_picks_the_cheapest_model_within_the_best_ones_margin():
    # cheap saves less than dear, but within dear's margin, for a tenth of the cost.
    chosen = _sets()["chosen"]
    assert chosen["model"] == "cheap"
    assert chosen["best"] == "dear"


def test_a_security_mistake_on_the_rules_set_rules_a_model_out():
    runs = [r for r in RUNS if r["model"] != "cheap"]
    runs += [run("dear", "7", (0.9, 0.01, 3.0), name="rules", tickets=[SECURITY])]
    assert benchmark.view(runs)["chosen"] == {
        "model": None,
        "label": None,
        "best": "dear",
    }


def test_the_view_names_the_model_the_product_runs_on(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "claude-haiku-4-5-20251001")
    assert benchmark.view([])["default"] == {
        "model": "claude-haiku-4-5-20251001",
        "label": "Claude Haiku 4.5",
    }


def test_no_development_run_means_no_choice_and_no_insights():
    view = benchmark.view([])
    assert view["chosen"] is None
    assert view["insights"] == []


def test_the_insights_answer_questions_with_the_numbers():
    found = {i["question"]: i["answer"] for i in _sets([SECURITY])["insights"]}
    assert "dear" in found["Which model saves the most?"]
    assert "20 times" in found["Does paying more buy more?"]
    assert "cheap escalates 90%" in found["Which admits what it doesn't know?"]
    risk = found["Which ones risk a security mistake?"]
    assert "CHF 2'000 each: dear (1 on rules)" in risk
    assert "1.0 s for cheap" in found["How long does a ticket take?"]
    beat = found["Does any model beat the free classifier?"]
    assert beat.startswith("On development tickets")


def test_the_insights_say_when_no_model_beats_the_classifier():
    strong = {**YARD, "action_accuracy": 1.0, "mistake_cost_chf": 0}
    runs = [
        {**r, "yardsticks": {"most_common": YARD, "classifier": strong}} for r in RUNS
    ]
    found = {i["question"]: i["answer"] for i in benchmark.view(runs)["insights"]}
    assert found["Does any model beat the free classifier?"].startswith("Not on")


def test_the_api_serves_the_benchmark(monkeypatch):
    monkeypatch.setattr(benchmark.runner, "load_runs", lambda: RUNS)
    view = benchmark.read_benchmark()
    assert set(view["sets"]) == {"dev", "unseen_dev", "rules"}
    assert view["rule"] == benchmark.RULE


def test_no_security_mistake_anywhere_says_so():
    found = {i["question"]: i["answer"] for i in _sets()["insights"]}
    assert found["Which ones risk a security mistake?"] == "None, on any set."


def test_the_yardsticks_come_from_a_full_run_not_a_newer_sample():
    sample = run("sampled", "9", (0.9, 0.002, 1.0), sample=True)
    small = {**YARD, "n": 3, "action_accuracy": 1.0, "mistake_cost_chf": 0}
    sample["yardsticks"] = {"most_common": small, "classifier": small}
    entries = benchmark.table("dev", [sample, *RUNS])["entries"]
    classifier = next(e for e in entries if e["model"] == "classifier")
    assert classifier["n"] == 10
    assert classifier["source"] == "3"
