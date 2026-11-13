"""Ranking models by net saving, and the Pareto front, on made-up runs."""

import pytest

from backend import benchmark
from evals import scoring

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


def test_the_benchmark_leaves_loop_runs_out():
    one = {"set": "dev", "tiny": False, "model": "m", "id": "one"}
    looped = {**one, "id": "loop", "design": "loop"}
    assert benchmark.newest_runs("dev", [looped, one]) == {"m": one}


# ── The loop beside one call ────────────────────────────────────────────────────
def row(tid, right, cost_usd=0.001, security=False, lookups=0):
    """One scored ticket: right, or wrong, and wrong in a way SEC-04 forbids."""
    answer = {
        "paths": ["ESCALATE"],
        "tools": [],
        "queues": ["SEC-INCIDENT" if security else "NET-VPN"],
        "checks": ["c"],
        "family": "F",
    }
    path = "ESCALATE" if right else ("AUTO_FIX" if security else "SELF_SERVE")
    queue = answer["queues"][0] if right else None
    steps = [
        {
            "id": f"s{i}",
            "tool": "run_check",
            "input": {"step": "c"},
            "ok": True,
            "result": "",
            "found": ["c"],
        }
        for i in range(lookups)
    ]
    return {
        "id": tid,
        "path": path,
        **scoring.score_decision(answer, path, None, queue),
        "cause_correct": None,
        "retrieval_correct": True,
        "cost_usd": cost_usd,
        "time_sec": 1.0,
        "error": None,
        "invalid": False,
        "investigation": scoring.investigation(answer, steps, None),
    }


def scored(model, rid, rows, **kind):
    """A saved run: `name` is its set, `design` its design, `sample` if a sample."""
    return {
        "id": rid,
        "set": kind.get("name", "dev"),
        "model": model,
        "design": kind.get("design", "one call"),
        "tiny": False,
        "sample": kind.get("sample", False),
        "summary": scoring.summarize(rows),
        "tickets": rows,
        "yardsticks": {"most_common": YARD, "classifier": YARD},
    }


IDS = [f"T{i}" for i in range(20)]


def test_the_loop_is_compared_with_one_call_on_the_same_tickets():
    full = scored("m", "1", [row(t, i % 2 == 0) for i, t in enumerate(IDS)])
    looped = scored(
        "m",
        "2",
        [row(t, True, 0.004, lookups=2) for t in IDS[:6]],
        design="loop",
        sample=True,
    )
    pairs = benchmark.loop_pairs("dev", [looped, full])
    assert len(pairs) == 1
    pair = pairs[0]
    assert pair["n"] == 6
    assert pair["one_call"]["n"] == 6  # cut to the loop's tickets, not all 20
    assert pair["one_call"]["action_accuracy"] == 0.5
    assert pair["loop"]["action_accuracy"] == 1.0
    assert pair["loop"]["design"] == "loop"
    assert pair["loop"]["investigation"]["lookups_per_ticket"] == 2


def test_a_loop_with_no_one_call_on_its_tickets_has_no_pair():
    looped = scored("m", "2", [row("NEW", True)], design="loop")
    one = scored("m", "1", [row("T0", True)])
    assert benchmark.loop_pairs("dev", [looped, one]) == []


def _loop_runs(dev_right, rules_security=False, cost_usd=0.004):
    n = 30
    return [
        scored(
            "m",
            "a",
            [
                row(t, i < n // 2)
                for i, t in enumerate(IDS + [f"U{i}" for i in range(10)])
            ],
        ),
        scored(
            "m",
            "b",
            [
                row(t, i < dev_right, cost_usd, lookups=3)
                for i, t in enumerate(IDS + [f"U{i}" for i in range(10)])
            ],
            design="loop",
            sample=True,
        ),
        scored("m", "c", [row("R1", True)], name="rules"),
        scored(
            "m",
            "d",
            [row("R1", not rules_security, security=True)],
            name="rules",
            design="loop",
        ),
    ]


def test_the_rule_keeps_a_loop_that_clearly_saves_more_and_stays_safe():
    verdict = benchmark.loop_view(_loop_runs(dev_right=30))["verdicts"]["m"]
    assert verdict["saves_more"]
    assert verdict["safe"]
    assert verdict["cheap"]
    assert verdict["valid"]
    assert verdict["keep"]
    assert verdict["gain_chf"] > 0


def test_the_rule_drops_a_loop_inside_the_margin():
    verdict = benchmark.loop_view(_loop_runs(dev_right=17))["verdicts"]["m"]
    assert not verdict["saves_more"]
    assert not verdict["keep"]


def test_one_security_mistake_drops_the_loop():
    verdict = benchmark.loop_view(_loop_runs(dev_right=30, rules_security=True))[
        "verdicts"
    ]["m"]
    assert not verdict["safe"]
    assert not verdict["keep"]


def test_a_loop_over_the_ceiling_is_dropped():
    verdict = benchmark.loop_view(_loop_runs(dev_right=30, cost_usd=0.2))["verdicts"][
        "m"
    ]
    assert not verdict["cheap"]
    assert not verdict["keep"]


def test_with_no_rules_run_safety_isnt_shown():
    runs = _loop_runs(dev_right=30)[:2]
    assert not benchmark.loop_view(runs)["verdicts"]["m"]["safe"]


def test_more_invalid_answers_than_one_call_drops_the_loop():
    runs = _loop_runs(dev_right=30)
    looped = runs[1]
    looped["tickets"][0]["invalid"] = True
    looped["summary"] = scoring.summarize(looped["tickets"])
    verdict = benchmark.loop_view(runs)["verdicts"]["m"]
    assert not verdict["valid"]
    assert not verdict["keep"]
