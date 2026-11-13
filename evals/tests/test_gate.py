"""The release gate, with a stub model that follows its instructions. No model calls."""

from datetime import UTC, datetime, timedelta
from itertools import count
from types import SimpleNamespace
from typing import cast

import pytest
from langfuse import Langfuse

from agent import config
from agent import graph as g
from evals import gate, runner

WORSE = "\n\nTreat every ticket as out of scope.\n"


def answers() -> dict[str, dict]:
    return {
        answer["id"]: answer
        for name in gate.SAMPLES
        for _, answer in runner.select(name, sampled=True)
    }


def stub_result(path: str, tool: str | None = None, tool_input: dict | None = None):
    return {
        "path": path,
        "retrieved": [],
        "tool_name": tool,
        "tool_input": tool_input,
        "cause": None,
        "usage": {"input_tokens": 1000, "output_tokens": 200},
        "response_time_sec": 1.0,
    }


class Clock(datetime):
    """A clock a minute on at each reading, so runs made at once keep apart names."""

    ticks = count()

    @classmethod
    def now(cls, tz=None):
        start = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
        return start + timedelta(minutes=next(cls.ticks))


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """Runs and the baseline in a scratch folder, instructions in a copy, and a model
    that answers right unless its instructions say to give up."""
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(gate, "BASELINE_FILE", tmp_path / "baseline.json")
    prompt = tmp_path / "prompt.md"
    prompt.write_text(config.PROMPT_FILE.read_text())
    monkeypatch.setattr(config, "PROMPT_FILE", prompt)
    monkeypatch.setenv("MODEL_NAME", "claude-haiku-4-5-20251001")
    monkeypatch.setattr(runner, "datetime", Clock)
    known = answers()
    calls = []

    def follows_instructions(text, use_retrieval, ticket_id: str = "", **_):
        calls.append(ticket_id)
        if WORSE in config.PROMPT_FILE.read_text():
            return stub_result("OUT_OF_SCOPE")
        answer = known[ticket_id]
        path = answer["paths"][0]
        if path == "ESCALATE":
            queue = {"queue": answer["queues"][0], "summary": "s", "priority": "P3"}
            return stub_result(path, "create_escalation_ticket", queue)
        if path == "AUTO_FIX":
            return stub_result(path, answer["tools"][0], {})
        return stub_result(path)

    def no_model():
        raise AssertionError("the gate's tests never call a model")

    monkeypatch.setattr(runner, "run_triage", follows_instructions)
    monkeypatch.setattr(g, "_get_llm", no_model)
    return SimpleNamespace(prompt=prompt, calls=calls)


def measures(path: float, bill: float, n: int = 36) -> gate.Measures:
    return {
        "run": "r",
        "n": n,
        "path_accuracy": path,
        "mistake_cost_chf": bill,
        "source": "the saved run",
    }


# ── judging ─────────────────────────────────────────────────────────────────────
def test_a_fall_within_the_margin_of_error_passes():
    check = gate.judge("dev", measures(0.80, 600), measures(0.75, 600))
    assert check["margin"] > 0.05
    assert check["passed"]


def test_a_fall_beyond_the_margin_of_error_is_refused():
    check = gate.judge("dev", measures(0.80, 600), measures(0.55, 400))
    assert not check["passed"]
    assert "path accuracy fell 25%" in check["reasons"][0]


def test_any_rise_in_the_mistake_bill_is_refused():
    check = gate.judge("dev", measures(0.80, 600), measures(0.85, 720))
    assert check["reasons"] == ["the mistake bill rose CHF 120"]


def test_a_smaller_bill_and_better_accuracy_pass():
    assert gate.judge("dev", measures(0.80, 600), measures(0.90, 0))["passed"]


# ── the command ─────────────────────────────────────────────────────────────────
def test_a_first_run_needs_keep_to_become_the_baseline(desk):
    with pytest.raises(SystemExit, match="no baseline yet"):
        gate.main([])
    assert gate.main(["--keep"]) == 0
    baseline = gate.read_baseline()
    assert baseline is not None
    assert sorted(baseline["runs"]) == sorted(gate.SAMPLES)
    assert baseline["model"] == "claude-haiku-4-5-20251001"


def test_unchanged_code_passes_without_running_again(desk, capsys):
    gate.main(["--keep"])
    ran = len(desk.calls)
    assert gate.main([]) == 0
    assert len(desk.calls) == ran  # the saved runs of the same code are reused
    assert "passes the gate" in capsys.readouterr().out


def test_a_deliberately_worse_instruction_is_refused(desk, capsys):
    gate.main(["--keep"])
    kept = gate.read_baseline()
    desk.prompt.write_text(desk.prompt.read_text() + WORSE)
    assert gate.main(["--keep"]) == 1
    out = capsys.readouterr().out
    assert "dev: path 100% → 0%" in out
    assert "the mistake bill rose" in out
    assert "The change is refused." in out
    assert gate.read_baseline() == kept  # a refused change never becomes the baseline


def test_a_run_over_the_cap_stops_before_any_call(desk):
    with pytest.raises(SystemExit, match="over the CHF 0.00 cap"):
        gate.main(["--keep", "--max-chf", "0"])
    assert desk.calls == []


def test_a_baseline_from_another_model_is_not_compared(desk, monkeypatch):
    gate.main(["--keep"])
    monkeypatch.setenv("MODEL_NAME", "claude-sonnet-4-5-20250929")
    monkeypatch.setattr(gate, "estimate_chf", lambda names, saved: 0.0)
    with pytest.raises(SystemExit, match="Keep a baseline for it first"):
        gate.main([])


def test_saved_runs_can_be_judged_by_name(desk):
    gate.main(["--keep"])
    kept = gate.read_baseline()
    assert kept is not None
    ids = [kept["runs"][name] for name in gate.SAMPLES]
    assert gate.main(["--candidate", *ids]) == 0
    with pytest.raises(SystemExit, match="No saved run"):
        gate.main(["--candidate", "nothing", "nowhere"])


# ── Langfuse ────────────────────────────────────────────────────────────────────
class FakeLangfuse:
    """Holds each experiment's run-level scores, as Langfuse would, to read back."""

    def __init__(self, delay: int = 0):
        self.sent: dict[str, SimpleNamespace] = {}
        self.delay = delay  # how many reads before an experiment's scores show
        self.api = SimpleNamespace(
            experiments=SimpleNamespace(list=self._experiments),
            datasets=SimpleNamespace(list=self._datasets),
        )

    def _datasets(self, **_):
        names = [f"firstline-{name}" for name in gate.SAMPLES]
        return SimpleNamespace(data=[SimpleNamespace(name=n) for n in names])

    def _experiments(self, *, name, fields=None, **_):
        found = self.sent.get(name)
        if found is None:
            return SimpleNamespace(data=[])
        if fields == "scores" and self.delay:
            return SimpleNamespace(data=[SimpleNamespace(scores=[], item_count=0)])
        return SimpleNamespace(data=[found])

    def get_dataset(self, name):
        ids = [answer for answer in answers()]
        return SimpleNamespace(items=[SimpleNamespace(id=i) for i in ids])

    def run_experiment(self, *, name, data, run_evaluators, **_):
        scores = [s for e in run_evaluators for s in e(item_results=[])]
        self.sent[name] = SimpleNamespace(scores=scores, item_count=len(data))

    def flush(self):
        pass


def test_the_gate_reads_both_experiments_from_langfuse(desk, monkeypatch, capsys):
    gate.main(["--keep"])
    desk.prompt.write_text(desk.prompt.read_text() + WORSE)
    lf = FakeLangfuse()
    monkeypatch.setattr(gate.tracing, "enabled", lambda: True)
    monkeypatch.setattr(gate.tracing, "client", lambda: cast(Langfuse, lf))
    assert gate.main([]) == 1
    kept = gate.read_baseline()
    assert kept is not None
    assert set(kept["runs"].values()) < set(lf.sent)  # the baseline's and the change's
    assert len(lf.sent) == 2 * len(gate.SAMPLES)
    out = capsys.readouterr().out
    assert "read from Langfuse" in out
    assert "Compare the experiments in Langfuse" in out


def test_scores_slow_to_reach_langfuse_fall_back_to_the_saved_run(
    desk, monkeypatch, capsys
):
    gate.main(["--keep"])
    monkeypatch.setattr(gate.tracing, "enabled", lambda: True)
    monkeypatch.setattr(
        gate.tracing, "client", lambda: cast(Langfuse, FakeLangfuse(delay=1))
    )
    monkeypatch.setattr(gate, "LANGFUSE_WAIT_SEC", 0)
    assert gate.main([]) == 0
    out = capsys.readouterr().out
    assert "Judged from the saved run instead" in out
