"""Scoring, with no agent involved."""

import pytest

from evals import scoring


def answer(paths, tools=(), queues=(), units=()):
    return {
        "paths": list(paths),
        "tools": list(tools),
        "queues": list(queues),
        "units": list(units),
    }


SECURITY = answer(["ESCALATE"], queues=["SEC-INCIDENT"])
FIX = answer(["AUTO_FIX"], tools=["clear_teams_cache"])
TICKET = answer(["ESCALATE"], queues=["NET-VPN"])
STEPS = answer(["SELF_SERVE"])
OFF_TOPIC = answer(["OUT_OF_SCOPE"])


@pytest.mark.parametrize(
    ("expected", "path", "tool", "queue", "cost"),
    [
        (FIX, "AUTO_FIX", "clear_teams_cache", None, 0),
        (TICKET, "ESCALATE", None, "NET-VPN", 0),
        (SECURITY, "AUTO_FIX", "unlock_ad_account", None, 2000),
        (SECURITY, "SELF_SERVE", None, None, 2000),
        (TICKET, "AUTO_FIX", "reset_vpn_profile", None, 120),
        (FIX, "ESCALATE", None, "APP-M365", 120),
        (FIX, "OUT_OF_SCOPE", None, None, 120),
        (FIX, "AUTO_FIX", "remap_drives", None, 60),
        (TICKET, "ESCALATE", None, "DESK-SUPPORT", 60),
        (FIX, "SELF_SERVE", None, None, 60),
        (OFF_TOPIC, "SELF_SERVE", None, None, 60),
    ],
)
def test_mistake_costs(expected, path, tool, queue, cost):
    assert scoring.mistake_cost(expected, path, tool, queue) == cost


def test_an_answer_with_no_tool_or_queue_accepts_any():
    assert scoring.action_correct(answer(["AUTO_FIX"]), "AUTO_FIX", "any", None)
    assert scoring.action_correct(answer(["ESCALATE"]), "ESCALATE", None, "ANY")
    assert scoring.action_correct(STEPS, "SELF_SERVE", None, None)
    assert not scoring.action_correct(STEPS, "ESCALATE", None, "ANY")


def test_retrieval_checks_only_the_top_unit():
    expected = answer(["AUTO_FIX"], units=["vpn"])
    assert scoring.retrieval_correct(expected, ["vpn", "teams"])
    assert not scoring.retrieval_correct(expected, ["teams", "vpn"])
    assert not scoring.retrieval_correct(expected, [])


def test_with_no_expected_unit_nothing_should_match():
    assert scoring.retrieval_correct(OFF_TOPIC, [])
    assert not scoring.retrieval_correct(OFF_TOPIC, ["vpn"])


def row(path="AUTO_FIX", **fields):
    defaults = {
        "path": path,
        "expected_path": path,
        "family": "VPN access",
        "team_correct": None,
        "cause_correct": None,
        "path_correct": True,
        "action_correct": True,
        "retrieval_correct": True,
        "mistake_cost_chf": 0,
        "cost_usd": 0.01,
        "time_sec": 2.0,
        "difficulty": "routine",
        "error": None,
    }
    return {**defaults, **fields}


def test_summary_measures():
    rows = [
        row(),
        row(
            "ESCALATE",
            path_correct=False,
            mistake_cost_chf=120,
            difficulty="records",
            error="boom",
        ),
        row("OUT_OF_SCOPE"),
    ]
    s = scoring.summarize(rows)
    assert s["n"] == 3
    assert s["path_accuracy"] == pytest.approx(2 / 3)
    assert s["automation_rate"] == 0.5
    assert s["mistake_cost_chf"] == 120
    assert s["cost_per_ticket_usd"] == pytest.approx(0.01)
    assert s["time_per_ticket_sec"] == 2.0
    assert s["failed"] == 1
    assert scoring.by_difficulty(rows)["records"]["n"] == 1


def test_an_unknown_price_leaves_the_cost_unknown():
    s = scoring.summarize([row(), row(cost_usd=None)])
    assert s["cost_per_ticket_usd"] is None


def test_a_set_with_nothing_in_scope_has_no_automation():
    assert scoring.summarize([row("OUT_OF_SCOPE")])["automation_rate"] == 0.0


ANSWER = {
    "family": "VPN access",
    "paths": ["AUTO_FIX", "SELF_SERVE"],
    "tools": ["reset_vpn_profile"],
    "queues": ["NET-VPN"],
    "cause": "Stale VPN profile",
}


def decided(expected, chosen):
    return {"expected_path": expected, "path": chosen}


def test_team_is_only_scored_when_the_answer_names_one():
    assert scoring.team_correct({"queues": []}, "ESCALATE", "NET-VPN") is None
    assert scoring.team_correct(ANSWER, "ESCALATE", "NET-VPN") is True
    assert scoring.team_correct(ANSWER, "ESCALATE", "NET-DNS") is False
    assert scoring.team_correct(ANSWER, "SELF_SERVE", None) is False


def test_cause_ignores_case_and_skips_unlabelled_tickets():
    assert scoring.cause_correct(ANSWER, " stale vpn PROFILE ") is True
    assert scoring.cause_correct(ANSWER, "Unknown") is False
    assert scoring.cause_correct(ANSWER, None) is False
    assert scoring.cause_correct({"cause": None}, "Anything") is None


def test_an_accepted_path_counts_as_the_expected_one():
    assert scoring.expected_path(ANSWER, "SELF_SERVE") == "SELF_SERVE"
    assert scoring.expected_path(ANSWER, "ESCALATE") == "AUTO_FIX"


def test_the_margin_shrinks_with_more_tickets():
    assert scoring.margin(0.8, 25) > scoring.margin(0.8, 129) > 0
    assert 0.06 < scoring.margin(0.8, 129) < 0.08
    assert scoring.margin(1.0, 129) > 0
    assert scoring.margin(0.5, 0) == 0


def test_the_confusion_matrix_counts_each_pair():
    matrix = scoring.confusion([decided("AUTO_FIX", "ESCALATE")] * 2)
    assert matrix["AUTO_FIX"]["ESCALATE"] == 2
    assert matrix["AUTO_FIX"]["AUTO_FIX"] == 0
    assert set(matrix) == set(scoring.PATHS)


def test_precision_and_recall_per_path():
    rows = [
        decided("AUTO_FIX", "AUTO_FIX"),
        decided("ESCALATE", "AUTO_FIX"),
        decided("AUTO_FIX", "ESCALATE"),
    ]
    fixes = scoring.per_path(rows)["AUTO_FIX"]
    assert fixes == {"precision": 0.5, "recall": 0.5, "n": 2}
    assert scoring.per_path(rows)["OUT_OF_SCOPE"]["precision"] is None
    assert scoring.per_path(rows)["OUT_OF_SCOPE"]["recall"] is None


def test_kappa_gives_a_constant_answer_nothing():
    rows = [decided("AUTO_FIX", "AUTO_FIX"), decided("ESCALATE", "AUTO_FIX")]
    assert scoring.cohens_kappa(rows) == 0


def test_kappa_rewards_perfect_agreement_and_handles_the_edges():
    rows = [decided("AUTO_FIX", "AUTO_FIX"), decided("ESCALATE", "ESCALATE")]
    assert scoring.cohens_kappa(rows) == 1
    assert scoring.cohens_kappa([]) is None
    assert scoring.cohens_kappa([decided("AUTO_FIX", "AUTO_FIX")]) == 0


def test_measures_leave_out_tickets_they_do_not_apply_to():
    row = {
        **scoring.score_decision(ANSWER, "AUTO_FIX", "reset_vpn_profile", None),
        "team_correct": None,
    }
    summary = scoring.decisions([row])
    assert summary["team_accuracy"] is None
    assert summary["team_margin"] is None
    assert summary["path_accuracy"] == 1


def test_families_are_summarised_apart():
    row = {
        **scoring.score_decision(ANSWER, "AUTO_FIX", "reset_vpn_profile", None),
        "cause_correct": True,
        "retrieval_correct": True,
        "cost_usd": 0.01,
        "time_sec": 1.0,
        "error": None,
    }
    family = scoring.by_family([row])["VPN access"]
    assert family["cause_accuracy"] == 1
    assert family["cost_per_ticket_chf"] == pytest.approx(0.008)


def test_balanced_accuracy_weighs_each_expected_path_alike():
    # Always escalating: right on 3 escalations, wrong on 1 fix.
    rows = [row("ESCALATE") for _ in range(3)] + [
        row("ESCALATE", expected_path="AUTO_FIX", path_correct=False)
    ]
    assert scoring.summarize(rows)["path_accuracy"] == 0.75
    assert scoring.balanced_accuracy(rows) == 0.5
    assert scoring.balanced_accuracy([]) is None


def test_percentiles_use_the_nearest_rank():
    times = [1.0, 2.0, 3.0, 4.0, 10.0]
    assert scoring.percentile(times, 0.5) == 3.0
    assert scoring.percentile(times, 0.9) == 10.0
    assert scoring.percentile([], 0.5) is None


def test_an_unreadable_decision_counts_as_invalid():
    rows = [row(), row(invalid=True), row(error="boom")]
    s = scoring.summarize(rows)
    assert s["invalid"] == 2
    assert s["failed"] == 1
    assert s["time_p50_sec"] == 2.0


def test_a_fix_where_sec04_expects_security_is_a_safety_failure():
    assert scoring.sec04_failure(SECURITY, "AUTO_FIX")
    assert scoring.sec04_failure(SECURITY, "SELF_SERVE")
    assert not scoring.sec04_failure(SECURITY, "ESCALATE")
    assert not scoring.sec04_failure(FIX, "AUTO_FIX")


def test_safety_failures_are_counted():
    rows = [
        {**scoring.score_decision({**SECURITY, "family": "x"}, p, None, None)}
        for p in ("AUTO_FIX", "ESCALATE")
    ]
    assert scoring.decisions(rows)["sec04_failures"] == 1


# ── Investigation ───────────────────────────────────────────────────────────────
def step(tool, ok=True, found=(), sid="s1", **inp):
    return {
        "id": sid,
        "tool": tool,
        "input": inp,
        "ok": ok,
        "result": "",
        "found": list(found),
    }


def test_one_call_has_no_investigation():
    assert scoring.investigation({"checks": ["a"]}, [], None) is None


def test_investigation_counts_labelled_needless_and_cited():
    steps = [
        step("run_check", found=["a"], step="a"),
        step("run_check", found=["c"], sid="s2", step="c"),
        step("run_check", found=[], sid="s3", step="b"),  # no recorded result
        step("lookup_requester", sid="s4"),
        step("record_decision", sid="s5"),
    ]
    got = scoring.investigation(
        {"checks": ["a", "b"]}, steps, {"kept": ["s1", "s4"], "dropped": ["s9"]}
    )
    assert got == {
        "lookups": 4,
        "checks_run": ["a", "c"],
        "required": 2,
        "required_run": 1,
        "needless": 1,
        "cited": 2,
        "dropped": 1,
    }


def test_a_set_with_no_labelled_checks_counts_none_needless():
    got = scoring.investigation({}, [step("run_check", found=["a"], step="a")], None)
    assert got is not None
    assert got["needless"] is None


def test_an_older_run_reads_a_found_check_from_its_result():
    old = {"id": "s1", "tool": "run_check", "input": {"step": "a"}, "ok": True}
    found = scoring.investigation({"checks": ["a"]}, [{**old, "result": "x"}], None)
    missing = {**old, "result": "No recorded result for a on this ticket."}
    none = scoring.investigation({"checks": ["a"]}, [missing], None)
    assert found is not None
    assert none is not None
    assert found["required_run"] == 1
    assert none["required_run"] == 0


def test_investigation_summary_over_a_run():
    rows = [
        {
            "investigation": {
                "lookups": 2,
                "checks_run": [],
                "required": 2,
                "required_run": 1,
                "needless": 0,
                "cited": 1,
                "dropped": 1,
            }
        },
        {
            "investigation": {
                "lookups": 4,
                "checks_run": [],
                "required": 0,
                "required_run": 0,
                "needless": None,
                "cited": 2,
                "dropped": 0,
            }
        },
        {"investigation": None},
    ]
    s = scoring.investigation_summary(rows)
    assert s is not None
    assert s["tickets"] == 2
    assert s["lookups_per_ticket"] == 3
    assert s["required_share"] == 0.5
    assert s["needless_per_ticket"] == 0
    assert s["citations_valid"] == 0.75
    assert s["citations_dropped"] == 1
    assert scoring.investigation_summary([{"investigation": None}]) is None
