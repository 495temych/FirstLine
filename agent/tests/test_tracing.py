"""Tracing to Langfuse, with stand-ins so no test reaches the service."""

from contextlib import contextmanager, nullcontext
from types import SimpleNamespace

import pytest

from agent import tracing


class FakeClient:
    def __init__(self):
        self.flushed = False

    def flush(self):
        self.flushed = True


@pytest.fixture
def on(monkeypatch):
    """Tracing switched on, with a fake client and handler."""
    for key in tracing.KEYS:
        monkeypatch.setenv(key, "test-key")
    monkeypatch.setenv(tracing.SWITCH, "true")
    fake = FakeClient()
    monkeypatch.setattr(tracing, "client", lambda: fake)
    monkeypatch.setattr(tracing, "CallbackHandler", lambda: "handler")
    return fake


def test_personal_details_are_masked_at_any_depth():
    data = {
        "text": "Mail j.doe@corplabs.com from 10.42.18.77, I'm EMP-40291 (E-5027)",
        "steps": ["Call a.b@x.ch", 3],
        "n": 7,
    }
    assert tracing.redact(data) == {
        "text": "Mail [email] from [ip address], I'm [employee id] ([employee id])",
        "steps": ["Call [email]", 3],
        "n": 7,
    }
    assert tracing.redact(("v1.2 build",)) == ["v1.2 build"]


def test_the_client_masks_and_sends_only_its_own_spans(monkeypatch):
    made = {}
    monkeypatch.setattr(tracing, "Langfuse", lambda **options: made.update(options))
    tracing.client.cache_clear()
    try:
        tracing.client()
    finally:
        tracing.client.cache_clear()
    assert made["mask"] is tracing._mask
    assert made["should_export_span"] is tracing.is_langfuse_span


def test_the_mask_langfuse_calls_redacts():
    assert tracing._mask(data="a@b.ch", extra=1) == "[email]"


def test_tracing_needs_both_keys_and_no_switch(monkeypatch):
    monkeypatch.delenv(tracing.SWITCH, raising=False)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert not tracing.enabled()
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    assert tracing.enabled()
    monkeypatch.setenv(tracing.SWITCH, "False")
    assert not tracing.enabled()


def test_tests_never_trace():
    assert not tracing.enabled()
    assert tracing.callbacks() == []


def test_off_means_no_callbacks_no_attributes_and_no_flush(monkeypatch):
    monkeypatch.setattr(tracing, "propagate_attributes", None)
    with tracing.trace("assistant"):
        pass
    tracing.flush()


def test_on_gives_a_handler_and_names_the_trace(on, monkeypatch):
    seen = {}

    @contextmanager
    def record(**attributes):
        seen.update(attributes)
        yield

    monkeypatch.setattr(tracing, "propagate_attributes", record)
    assert tracing.callbacks() == ["handler"]
    with tracing.trace("evaluation", session_id="s1", tags=("evaluation", "dev")):
        pass
    assert seen == {
        "trace_name": "evaluation",
        "session_id": "s1",
        "tags": ["evaluation", "dev"],
        "metadata": None,
    }
    tracing.flush()
    assert on.flushed


def test_off_means_no_trace_id_url_or_verdict():
    assert tracing.new_trace_id("seed") is None
    assert tracing.trace_url("t1") is None
    tracing.verdict("t1", "approved")


def test_a_trace_id_from_the_same_seed_is_the_same(on):
    assert tracing.new_trace_id("queue b T-1") == tracing.new_trace_id("queue b T-1")
    assert tracing.new_trace_id("queue b T-1") != tracing.new_trace_id("queue b T-2")


class RecordingClient(FakeClient):
    def __init__(self):
        super().__init__()
        self.observations, self.scores = [], []
        observations = SimpleNamespace(get_many=self._get_many)
        self.api = SimpleNamespace(observations=observations)

    @contextmanager
    def start_as_current_observation(self, **observation):
        self.observations.append(observation)
        yield

    def _get_many(self, **query):
        self.query = query
        return SimpleNamespace(data=[SimpleNamespace(model_dump=lambda: {"name": "x"})])

    def get_trace_url(self, *, trace_id):
        return f"https://lf/{trace_id}"

    def create_score(self, **score):
        self.scores.append(score)


@pytest.fixture
def recording(on, monkeypatch):
    fake = RecordingClient()
    monkeypatch.setattr(tracing, "client", lambda: fake)
    monkeypatch.setattr(tracing, "propagate_attributes", lambda **_: nullcontext())
    return fake


def test_a_given_trace_id_holds_everything_inside(recording):
    with tracing.trace("queue", trace_id="t1"):
        pass
    assert recording.observations == [
        {"trace_context": {"trace_id": "t1"}, "name": "queue"}
    ]


def test_a_trace_is_read_back_with_usage_and_cost(recording):
    assert tracing.trace_steps("t1") == [{"name": "x"}]
    assert recording.query["trace_id"] == "t1"
    assert "usage" in recording.query["fields"]
    assert tracing.trace_url("t1") == "https://lf/t1"


def test_a_verdict_lands_on_its_trace(recording):
    tracing.verdict("t1", "rejected", "Wrong user")
    assert recording.scores == [
        {
            "trace_id": "t1",
            "name": "technician_verdict",
            "value": "rejected",
            "data_type": "CATEGORICAL",
            "comment": "Wrong user",
        }
    ]
