"""The Langfuse upload, against a fake client that records what it's sent."""

import json
from contextlib import contextmanager
from types import SimpleNamespace
from typing import cast

import pytest
from langfuse import Langfuse

from agent import config
from evals import langfuse_upload as upload
from evals import runner


class FakeLangfuse:
    def __init__(self, experiments=(), traces=()):
        self.datasets, self.items, self.experiments, self.observations = {}, [], [], []
        self.flushed = False
        self.known_experiments, self.known_traces = set(experiments), set(traces)
        self.api = SimpleNamespace(
            experiments=SimpleNamespace(list=self._list_experiments),
            observations=SimpleNamespace(get_many=self._get_observations),
        )

    def _list_experiments(self, *, name, **_):
        return SimpleNamespace(data=[name] if name in self.known_experiments else [])

    def _get_observations(self, *, trace_id, **_):
        return SimpleNamespace(data=[1] if trace_id in self.known_traces else [])

    def create_dataset(self, *, name, **_):
        self.datasets[name] = []

    def create_dataset_item(self, *, dataset_name, **item):
        self.datasets[dataset_name].append(item)
        self.items.append(item)

    def get_dataset(self, name):
        items = [SimpleNamespace(**i) for i in self.datasets[name]]
        return SimpleNamespace(items=items)

    def run_experiment(self, *, data, task, evaluators, run_evaluators, **meta):
        results = []
        for item in data:
            output = task(item=item)
            scores = [e(input=item.input, output=output) for e in evaluators]
            results.append((item.id, output, scores))
        run_level = [e(item_results=results) for e in run_evaluators]
        self.experiments.append({**meta, "results": results, "run": run_level})

    def create_trace_id(self, *, seed):
        return f"trace-{seed}"

    @contextmanager
    def start_as_current_observation(self, **observation):
        self.observations.append(observation)
        yield

    def flush(self):
        self.flushed = True


def client(fake: FakeLangfuse) -> Langfuse:
    """The fake, standing in where the upload expects a real client."""
    return cast(Langfuse, fake)


@pytest.fixture
def no_attributes(monkeypatch):
    @contextmanager
    def nothing(**_):
        yield

    monkeypatch.setattr(upload, "propagate_attributes", nothing)


def a_run(set_name, tickets, **extra):
    return {
        "id": f"20261108T000000-{set_name}",
        "set": set_name,
        "tiny": False,
        "model": "m",
        "version": "v",
        "kb_version": "k",
        "date": "2026-11-08",
        "summary": {"path_accuracy": 0.5, "kappa": None, "mistake_cost_chf": 120},
        "tickets": tickets,
        "yardsticks": {},
        **extra,
    }


def a_row(ticket_id, path_ok=True):
    return {
        "id": ticket_id,
        "path": "ESCALATE",
        "tool": None,
        "queue": "DESK-SUPPORT",
        "cause": "x",
        "retrieved": [],
        "error": None,
        "path_correct": path_ok,
        "action_correct": path_ok,
        "team_correct": None,
        "cause_correct": None,
        "retrieval_correct": True,
        "mistake_cost_chf": 0 if path_ok else 120,
    }


def test_only_the_practice_sets_are_uploaded():
    assert set(upload.UPLOADED_SETS) == {"rules", "dev", "unseen_dev"}
    lf = FakeLangfuse()
    count = upload.upload_datasets(client(lf))
    assert set(lf.datasets) == {
        "firstline-rules",
        "firstline-dev",
        "firstline-unseen_dev",
    }
    assert count == 25 + 129 + 52
    splits = json.loads((config.TICKETS_DIR / "splits.json").read_text())
    closed = set(splits["held_out"]) | set(splits["unseen_held_out"])
    assert not {item["id"] for item in lf.items} & closed
    assert not any(item["id"].startswith("H-") for item in lf.items)


def test_a_dataset_item_holds_what_the_agent_sees_and_the_answer_apart():
    ticket, answer = runner.load_any("dev")[0]
    item = upload.dataset_item(ticket, answer)
    assert item["input"]["id"] == ticket["id"]
    assert item["input"]["requester"] == ticket["requester"]
    assert item["expected_output"]["paths"] == answer["paths"]
    assert "root_cause" not in json.dumps(item["input"])


def test_dataset_items_are_redacted_before_they_leave():
    ticket = {
        "id": "T-1",
        "text": "I'm j.doe@corplabs.com, EMP-40291",
        "requester": "r",
    }
    answer = {"paths": [], "tools": [], "queues": [], "cause": None}
    item = upload.dataset_item(ticket, {**answer, "family": "f", "difficulty": "d"})
    assert item["input"]["text"] == "I'm [email], [employee id]"


def test_a_saved_run_is_replayed_with_its_own_scores():
    lf = FakeLangfuse()
    lf.create_dataset(name="firstline-rules")
    for ticket_id in ("T-001", "T-002", "T-003"):
        lf.create_dataset_item(
            dataset_name="firstline-rules", id=ticket_id, input={"id": ticket_id}
        )
    run = a_run("rules", [a_row("T-001"), a_row("T-002", path_ok=False)])
    assert upload.replay(client(lf), run) is True
    [experiment] = lf.experiments
    assert experiment["name"] == run["id"]
    assert experiment["metadata"]["rescored_from"] == ""
    [(first, output, [scores]), (_, _, [wrong])] = experiment["results"]
    assert first == "T-001"
    assert output["queue"] == "DESK-SUPPORT"
    named = {s.name: s.value for s in scores}
    assert named == {"path": 1.0, "action": 1.0, "retrieval": 1.0, "mistake_chf": 0}
    assert {s.name: s.value for s in wrong}["mistake_chf"] == 120
    [run_level] = experiment["run"]
    assert {s.name: s.value for s in run_level} == {
        "path_accuracy": 0.5,
        "mistake_cost_chf": 120,
    }


def test_a_run_already_in_langfuse_is_skipped():
    run = a_run("rules", [a_row("T-001")])
    lf = FakeLangfuse(experiments=[run["id"]])
    assert upload.replay(client(lf), run) is False
    assert lf.experiments == []


def test_held_out_runs_are_never_replayed(monkeypatch):
    runs = [a_run("held_out", []), a_run("dev", []), a_run("rules", [], tiny=True)]
    monkeypatch.setattr(runner, "load_runs", lambda: runs)
    assert [run["set"] for run in upload.runs_to_replay()] == ["dev"]


def test_usage_is_sent_once_per_logged_run(tmp_path, monkeypatch, no_attributes):
    log = tmp_path / "logs.csv"
    log.write_text(
        "timestamp,query,retrieved_units,decision_path,diagnostic_summary,"
        "tool_called,confirmed,escalation_queue,priority,response_time_sec\n"
        "t1,My VPN fails,vpn,AUTO_FIX,,reset_vpn_profile,yes,,,1.2\n"
        "t2,Locked out,sec-04,ESCALATE,Repeat lockout,,,SEC-INCIDENT,P2-High,2.0\n"
    )
    monkeypatch.setattr(config, "LOG_FILE", log)
    lf = FakeLangfuse(traces=["trace-logs.csv t2"])
    assert upload.upload_usage(client(lf)) == 1
    [sent] = lf.observations
    assert sent["trace_context"] == {"trace_id": "trace-logs.csv t1"}
    assert sent["input"] == {"query": "My VPN fails"}
    assert sent["output"]["tool"] == "reset_vpn_profile"
    assert sent["output"]["queue"] is None


def test_no_log_means_no_usage(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOG_FILE", tmp_path / "missing.csv")
    assert upload.upload_usage(client(FakeLangfuse())) == 0


def test_the_command_needs_keys(monkeypatch):
    with pytest.raises(SystemExit, match="LANGFUSE_PUBLIC_KEY"):
        upload.main()


def test_the_command_uploads_and_reports(monkeypatch, capsys, no_attributes):
    lf = FakeLangfuse()
    monkeypatch.setattr(upload.tracing, "enabled", lambda: True)
    monkeypatch.setattr(upload.tracing, "client", lambda: lf)
    monkeypatch.setattr(upload, "runs_to_replay", list)
    monkeypatch.setattr(upload, "usage_rows", list)
    upload.main()
    out = capsys.readouterr().out
    assert "206 dataset items in 3 datasets" in out
    assert "none new" in out
    assert lf.flushed
