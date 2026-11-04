"""The golden-set runner, with a stub run_triage."""

import runpy

import pytest

from evals import runner


def result_for(query: str, use_retrieval: bool) -> dict:
    """Answers every ticket correctly except the VPN one."""
    case = next(c for c in runner.load_golden() if c["query"] == query)
    retrieved = [
        {"doc": u.split("::")[0], "section": (u.split("::") + [None])[1]}
        for u in sorted(case["expected_units"])
    ]
    path = "ESCALATE" if "VPN keeps" in query else sorted(case["expected_path"])[0]
    return {"retrieved": retrieved, "path": path}


@pytest.fixture
def stubbed(monkeypatch):
    monkeypatch.setattr(runner, "run_triage", result_for)


def test_golden_set_loads_with_labels_as_sets():
    cases = runner.load_golden()
    assert len(cases) == 10
    assert all(isinstance(c["expected_path"], set) for c in cases)
    assert all(isinstance(c["expected_units"], set) for c in cases)


def test_unit_ids_name_the_section_when_there_is_one():
    assert runner._unit_id({"doc": "vpn", "section": None}) == "vpn"
    assert runner._unit_id({"doc": "co", "section": "Sec"}) == "co::Sec"


def test_top1_is_correct_when_it_is_an_expected_unit():
    assert runner._top1_correct({"vpn"}, ["vpn", "teams"])
    assert not runner._top1_correct({"vpn"}, ["teams", "vpn"])


def test_top1_with_nothing_expected_is_correct_only_when_nothing_returned():
    assert runner._top1_correct(set(), [])
    assert not runner._top1_correct(set(), ["vpn"])


@pytest.mark.usefixtures("stubbed")
def test_run_and_summarize():
    summary = runner.summarize(runner.run_eval())
    assert summary["n"] == 10
    assert summary["retrieval_accuracy"] == 1.0
    assert summary["path_accuracy"] == 0.9


@pytest.mark.usefixtures("stubbed")
def test_the_module_entry_point_prints_the_report(capsys):
    runpy.run_module("evals", run_name="__main__")
    out = capsys.readouterr().out
    assert "Golden-set evaluation — 10 queries" in out
    assert "retrieval_accuracy=100%" in out
    assert "path_accuracy=90%" in out
    assert "✗ path" in out
