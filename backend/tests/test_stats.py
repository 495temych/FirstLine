"""Usage statistics over the Assistant's runs."""

import pytest

from backend import stats
from backend.store import Answer, Run


def run(path: str, *answers: tuple[str, bool], ms: int | None = 2000) -> Run:
    given: list[Answer] = [{"gate": g, "approved": a} for g, a in answers]
    return {"path": path, "latency_ms": ms, "answers": given}


@pytest.mark.parametrize(
    ("case", "automated"),
    [
        (run("AUTO_FIX", ("confirm_fix", True)), True),
        (run("AUTO_FIX", ("confirm_fix", False), ("confirm_ticket", True)), False),
        (run("SELF_SERVE", ("self_serve", True)), True),
        (run("SELF_SERVE", ("self_serve", False), ("confirm_ticket", True)), False),
        (run("ESCALATE", ("confirm_ticket", True)), False),
        (run("AUTO_FIX"), False),  # still waiting for the person
        (run("OUT_OF_SCOPE"), False),
    ],
)
def test_only_an_outcome_without_a_technician_counts(case, automated):
    assert stats.automated(case) is automated


def test_the_rate_is_over_runs_in_scope():
    runs = [
        run("AUTO_FIX", ("confirm_fix", True), ms=1000),
        run("AUTO_FIX", ("confirm_fix", False), ms=3000),
        run("ESCALATE", ("confirm_ticket", True)),
        run("OUT_OF_SCOPE", ms=None),
    ]
    summary = stats.summary_stats(runs)
    assert summary["n"] == 4
    assert summary["automation_rate"] == pytest.approx(100 / 3)
    assert summary["avg_response_time_sec"]["AUTO_FIX"] == 2.0
    assert summary["avg_response_time_sec"]["OUT_OF_SCOPE"] is None
    assert summary["low_sample"] is True


def test_no_runs_means_no_rate():
    summary = stats.summary_stats([])
    assert (summary["n"], summary["automation_rate"]) == (0, None)


def test_the_summary_prints_for_a_person(capsys):
    stats.print_summary(stats.summary_stats([]))
    assert "No runs yet" in capsys.readouterr().out
    stats.print_summary(stats.summary_stats([run("AUTO_FIX", ("confirm_fix", True))]))
    out = capsys.readouterr().out
    assert "Automation rate, over runs in scope: 100%" in out
    assert "too small" in out
