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
        (TICKET, "ESCALATE", None, "DESKTOP-SUPPORT", 60),
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
