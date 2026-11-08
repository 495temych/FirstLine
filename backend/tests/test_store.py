"""The Queue's record. Each test runs against memory and a throwaway Postgres."""

import psycopg
import pytest

from backend import store as record
from backend.store import MemoryStore, PostgresStore, Proposal, Verdict

ARRIVALS: list[record.Arrival] = [
    {"id": "INC1", "text": "VPN drops\n\nIt keeps dropping.", "requester": "a.b"},
    {"id": "INC2", "text": "Printer jam\n\nTray 2.", "requester": "c.d"},
]
PROPOSAL: Proposal = {
    "path": "AUTO_FIX",
    "cause": "Stale VPN profile",
    "reasoning": "The profile predates the migration.",
    "tool": "reset_vpn_profile",
    "tool_input": {"username": "a.b"},
    "queue": None,
    "priority": None,
    "summary": None,
    "retrieved": [{"doc": "vpn", "section": "Fix", "score": 0.61}],
    "model": "claude-haiku-4-5-20251001",
    "version": "abc12345",
    "trace_id": "trace-1",
    "cost_usd": 0.0042,
    "latency_ms": 5300,
}
APPROVED: Verdict = {
    "verdict": "approved",
    "seconds": 31,
    "queue": None,
    "note": "",
    "reviewer": "technician",
}
OUTCOME = {"status": "ok", "detail": "Profile reset (simulated)."}


def by_id(store) -> dict[str, record.Saved]:
    return {t["id"]: t for t in store.tickets()}


def test_a_new_batch_is_queued(store):
    batch = store.add_batch("morning", ARRIVALS)
    tickets = store.tickets()
    assert [t["id"] for t in tickets] == ["INC1", "INC2"]
    assert {t["batch"] for t in tickets} == {batch}
    assert {t["state"] for t in tickets} == {"queued"}
    assert store.ticket_ids() == {"INC1", "INC2"}


def test_a_started_ticket_is_working_and_a_failure_says_why(store):
    store.add_batch("morning", ARRIVALS)
    store.started("INC1")
    store.started("INC2")
    store.failed("INC2", "APIConnectionError: no route")
    tickets = by_id(store)
    assert tickets["INC1"]["state"] == "working"
    assert tickets["INC2"]["state"] == "failed"
    assert tickets["INC2"]["error"] == "APIConnectionError: no route"


def test_a_decision_comes_back_as_it_was_saved(store):
    store.add_batch("morning", ARRIVALS)
    store.started("INC1")
    store.decided("INC1", PROPOSAL)
    ticket = by_id(store)["INC1"]
    assert ticket["state"] == "review"
    assert ticket["decision"] == PROPOSAL


def test_a_review_closes_the_ticket_with_its_outcome(store):
    store.add_batch("morning", ARRIVALS)
    store.decided("INC1", PROPOSAL)
    store.reviewed("INC1", APPROVED, OUTCOME)
    ticket = by_id(store)["INC1"]
    assert ticket["state"] == "closed"
    assert ticket["review"] == APPROVED
    assert ticket["outcome"] == OUTCOME
    assert ticket["reviewed_at"]


def test_a_correction_keeps_its_team_and_a_rejection_its_reason(store):
    store.add_batch("morning", ARRIVALS)
    store.decided("INC1", PROPOSAL)
    store.decided("INC2", PROPOSAL)
    corrected: Verdict = {**APPROVED, "verdict": "corrected", "queue": "NET-VPN"}
    rejected: Verdict = {**APPROVED, "verdict": "rejected", "note": "Wrong user"}
    store.reviewed("INC1", corrected, {})
    store.reviewed("INC2", rejected, {})
    tickets = by_id(store)
    assert tickets["INC1"]["review"] == corrected
    assert tickets["INC2"]["review"] == rejected


def test_memory_and_postgres_keep_the_same_record(postgres_store):
    def work(store):
        store.add_batch("morning", ARRIVALS)
        store.started("INC1")
        store.decided("INC1", PROPOSAL)
        store.reviewed("INC1", APPROVED, OUTCOME)
        store.started("INC2")
        store.failed("INC2", "Timeout")
        return [
            {**t, "batch": None, "reviewed_at": bool(t["reviewed_at"])}
            for t in store.tickets()
        ]

    assert work(MemoryStore()) == work(postgres_store)


@pytest.mark.parametrize(
    ("kinds", "decided", "reviewed", "state"),
    [
        ([], False, False, "queued"),
        (["loaded"], False, False, "queued"),
        (["loaded", "started"], False, False, "working"),
        (["loaded", "started", "failed"], False, False, "failed"),
        # After a restart, a ticket that was working starts again.
        (["loaded", "started", "started"], False, False, "working"),
        (["loaded", "started", "decided"], True, False, "review"),
        (["loaded", "started", "decided", "reviewed"], True, True, "closed"),
    ],
)
def test_a_state_follows_from_what_happened(kinds, decided, reviewed, state):
    events: list[record.Event] = [{"kind": k, "detail": {}} for k in kinds]
    assert record.state_of(events, decided, reviewed) == state


def test_every_step_is_an_event_with_its_actor(postgres_store, empty_postgres):
    postgres_store.add_batch("morning", ARRIVALS[:1])
    postgres_store.started("INC1")
    postgres_store.decided("INC1", PROPOSAL)
    postgres_store.reviewed("INC1", APPROVED, OUTCOME)
    with psycopg.connect(empty_postgres) as conn:
        rows = conn.execute("select kind, actor from events order by id").fetchall()
    assert rows == [
        ("loaded", "code"),
        ("started", "code"),
        ("decided", "agent"),
        ("reviewed", "person"),
        ("action_ran", "code"),
    ]


def test_a_refused_step_leaves_nothing_behind(postgres_store, empty_postgres):
    postgres_store.add_batch("morning", ARRIVALS[:1])
    with pytest.raises(psycopg.errors.CheckViolation):
        postgres_store.decided("INC1", {**PROPOSAL, "path": "GUESS"})
    with psycopg.connect(empty_postgres) as conn:
        kinds = [row[0] for row in conn.execute("select kind from events")]
    assert kinds == ["loaded"]
    assert by_id(postgres_store)["INC1"]["state"] == "queued"


def test_the_record_is_supabase_only_when_it_is_set_up(monkeypatch):
    assert isinstance(record.open_store(), MemoryStore)
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://nobody@localhost:1/none")
    store = record.open_store()
    assert isinstance(store, PostgresStore)  # it connects only when first used
    store.close()
