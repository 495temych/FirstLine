"""Where the Queue keeps its record: Supabase, or memory when there's no database.

The board saves each step here as it happens, and reads everything back when the
backend starts. A ticket's state is never stored. It follows from what happened to the
ticket, its events, decision and review, through `state_of`, in both versions.

What Supabase doesn't hold, such as a ticket's title, SLA and requester's profile, the
board joins from `data/` by id, so no copy can drift.
"""

import os
from collections import defaultdict
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol, TypedDict

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

REVIEWER = "technician"  # until people sign in
CONNECT_TIMEOUT_SEC = 30  # the session pooler can be slow to answer on a bad network
POOL_SIZE = 4  # two workers, a review and the board's reads

# Each kind of event, and who causes it.
ACTORS = {
    "loaded": "code",
    "started": "code",
    "decided": "agent",
    "failed": "agent",
    "reviewed": "person",
    "action_ran": "code",
}


class Arrival(TypedDict):
    id: str
    text: str
    requester: str


class Proposal(TypedDict):
    """The agent's decision, with what it took to make it."""

    path: str
    cause: str | None
    reasoning: str | None
    tool: str | None
    tool_input: dict | None
    queue: str | None
    priority: str | None
    summary: str | None
    retrieved: list[dict]
    model: str
    version: str
    trace_id: str | None
    cost_usd: float | None
    latency_ms: int | None


class Verdict(TypedDict):
    verdict: str
    seconds: int
    queue: str | None
    note: str
    reviewer: str


class Saved(TypedDict):
    """One ticket as the record holds it."""

    id: str
    batch: str
    state: str
    error: str | None
    decision: Proposal | None
    review: Verdict | None
    reviewed_at: str | None
    outcome: dict | None


class Event(TypedDict):
    kind: str
    detail: dict


def state_of(events: list[Event], decided: bool, reviewed: bool) -> str:
    """A ticket's state, from what has happened to it."""
    if reviewed:
        return "closed"
    if decided:
        return "review"
    progress = [e["kind"] for e in events if e["kind"] in ("started", "failed")]
    if not progress:
        return "queued"
    return "failed" if progress[-1] == "failed" else "working"


def _detail(events: list[Event], kind: str) -> dict | None:
    found = [e["detail"] for e in events if e["kind"] == kind]
    return found[-1] if found else None


def saved(
    ticket_id: str,
    batch: str,
    events: list[Event],
    decision: Proposal | None,
    review: tuple[Verdict, str] | None,
) -> Saved:
    """A ticket from its rows. A review comes with the time it was made."""
    failure = _detail(events, "failed")
    return {
        "id": ticket_id,
        "batch": batch,
        "state": state_of(events, decision is not None, review is not None),
        "error": failure["error"] if failure else None,
        "decision": decision,
        "review": review[0] if review else None,
        "reviewed_at": review[1] if review else None,
        "outcome": _detail(events, "action_ran"),
    }


class Store(Protocol):
    def ticket_ids(self) -> set[str]: ...
    def add_batch(self, note: str, tickets: list[Arrival]) -> str: ...
    def started(self, ticket_id: str) -> None: ...
    def failed(self, ticket_id: str, error: str) -> None: ...
    def decided(self, ticket_id: str, decision: Proposal) -> None: ...
    def reviewed(self, ticket_id: str, review: Verdict, outcome: dict) -> None: ...
    def tickets(self) -> list[Saved]: ...


class MemoryStore:
    """The same record, kept in memory, for tests and for running without Supabase."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._batches: list[str] = []
        self._batch_of: dict[str, str] = {}
        self._events: dict[str, list[Event]] = defaultdict(list)
        self._decisions: dict[str, Proposal] = {}
        self._reviews: dict[str, tuple[Verdict, str]] = {}

    def ticket_ids(self) -> set[str]:
        with self._lock:
            return set(self._batch_of)

    def add_batch(self, note: str, tickets: list[Arrival]) -> str:
        with self._lock:
            batch = f"memory-{len(self._batches) + 1}"
            self._batches.append(batch)
            for ticket in tickets:
                self._batch_of[ticket["id"]] = batch
                self._events[ticket["id"]].append({"kind": "loaded", "detail": {}})
            return batch

    def _event(self, ticket_id: str, kind: str, detail: dict) -> None:
        self._events[ticket_id].append({"kind": kind, "detail": detail})

    def started(self, ticket_id: str) -> None:
        with self._lock:
            self._event(ticket_id, "started", {})

    def failed(self, ticket_id: str, error: str) -> None:
        with self._lock:
            self._event(ticket_id, "failed", {"error": error})

    def decided(self, ticket_id: str, decision: Proposal) -> None:
        with self._lock:
            self._decisions[ticket_id] = decision
            self._event(ticket_id, "decided", {"path": decision["path"]})

    def reviewed(self, ticket_id: str, review: Verdict, outcome: dict) -> None:
        with self._lock:
            self._reviews[ticket_id] = (review, datetime.now(UTC).isoformat())
            self._event(ticket_id, "reviewed", {"verdict": review["verdict"]})
            self._event(ticket_id, "action_ran", outcome)

    def tickets(self) -> list[Saved]:
        with self._lock:
            return [
                saved(
                    ticket_id,
                    batch,
                    list(self._events[ticket_id]),
                    self._decisions.get(ticket_id),
                    self._reviews.get(ticket_id),
                )
                for ticket_id, batch in self._batch_of.items()
            ]


def _add_event(conn: Connection, ticket_id: str, kind: str, detail: dict) -> None:
    conn.execute(
        "insert into events (ticket_id, actor, kind, detail) values (%s, %s, %s, %s)",
        [ticket_id, ACTORS[kind], kind, Jsonb(detail)],
    )


ADD_DECISION = """
insert into decisions (ticket_id, path, tool, tool_input, queue, priority, cause,
  rationale, summary, retrieved, model, version, trace_id, cost_usd, latency_ms)
values (%(ticket_id)s, %(path)s, %(tool)s, %(tool_input)s, %(queue)s, %(priority)s,
  %(cause)s, %(reasoning)s, %(summary)s, %(retrieved)s, %(model)s, %(version)s,
  %(trace_id)s, %(cost_usd)s, %(latency_ms)s)
"""

ADD_REVIEW = """
insert into reviews (decision_id, verdict, correction, reviewer, seconds_spent, note)
select id, %s, %s, %s, %s, %s from decisions
where ticket_id = %s order by created_at desc limit 1
"""

READ_TICKETS = """
select t.id, t.batch_id::text as batch
from tickets t join batches b on b.id = t.batch_id
where t.mode = 'queue' order by b.created_at, t.id
"""

READ_DECISIONS = """
select distinct on (ticket_id) ticket_id, path, cause, rationale as reasoning, tool,
  tool_input, queue, priority, summary, retrieved, model, version, trace_id, cost_usd,
  latency_ms
from decisions order by ticket_id, created_at desc
"""

READ_REVIEWS = """
select d.ticket_id, r.verdict, r.correction, r.reviewer, r.seconds_spent, r.note,
  r.created_at
from reviews r join decisions d on d.id = r.decision_id
"""


def _proposal(row: dict) -> Proposal:
    cost = row["cost_usd"]
    return {
        "path": row["path"],
        "cause": row["cause"],
        "reasoning": row["reasoning"],
        "tool": row["tool"],
        "tool_input": row["tool_input"],
        "queue": row["queue"],
        "priority": row["priority"],
        "summary": row["summary"],
        "retrieved": row["retrieved"],
        "model": row["model"],
        "version": row["version"],
        "trace_id": row["trace_id"],
        "cost_usd": None if cost is None else float(cost),
        "latency_ms": row["latency_ms"],
    }


def _verdict(row: dict) -> Verdict:
    return {
        "verdict": row["verdict"],
        "seconds": row["seconds_spent"],
        "queue": (row["correction"] or {}).get("queue"),
        "note": row["note"] or "",
        "reviewer": row["reviewer"],
    }


class PostgresStore:
    """The record in Supabase. Each step's writes are one transaction."""

    def __init__(self, url: str) -> None:
        self._pool = ConnectionPool(
            url,
            min_size=1,
            max_size=POOL_SIZE,
            open=False,
            timeout=CONNECT_TIMEOUT_SEC,
            # The pooler may hand a session to another client between transactions.
            kwargs={"prepare_threshold": None},
        )
        self._opening = Lock()
        self._open = False

    def _conn(self):
        with self._opening:
            if not self._open:
                self._pool.open(wait=True, timeout=CONNECT_TIMEOUT_SEC)
                self._open = True
        return self._pool.connection()

    def close(self) -> None:
        self._pool.close()

    def ticket_ids(self) -> set[str]:
        with self._conn() as conn:
            return {row[0] for row in conn.execute("select id from tickets")}

    def add_batch(self, note: str, tickets: list[Arrival]) -> str:
        with self._conn() as conn:
            row = conn.execute(
                "insert into batches (note) values (%s) returning id::text", [note]
            ).fetchone()
            if row is None:
                raise RuntimeError("The database didn't return the new batch.")
            batch = row[0]
            for ticket in tickets:
                conn.execute(
                    "insert into tickets (id, text, requester, mode, batch_id)"
                    " values (%s, %s, %s, 'queue', %s)",
                    [ticket["id"], ticket["text"], ticket["requester"], batch],
                )
                _add_event(conn, ticket["id"], "loaded", {})
            return batch

    def started(self, ticket_id: str) -> None:
        with self._conn() as conn:
            _add_event(conn, ticket_id, "started", {})

    def failed(self, ticket_id: str, error: str) -> None:
        with self._conn() as conn:
            _add_event(conn, ticket_id, "failed", {"error": error})

    def decided(self, ticket_id: str, decision: Proposal) -> None:
        values = {
            **decision,
            "ticket_id": ticket_id,
            "tool_input": None
            if decision["tool_input"] is None
            else Jsonb(decision["tool_input"]),
            "retrieved": Jsonb(decision["retrieved"]),
        }
        with self._conn() as conn:
            conn.execute(ADD_DECISION, values)
            _add_event(conn, ticket_id, "decided", {"path": decision["path"]})

    def reviewed(self, ticket_id: str, review: Verdict, outcome: dict) -> None:
        correction = (
            Jsonb({"queue": review["queue"]})
            if review["verdict"] == "corrected"
            else None
        )
        with self._conn() as conn:
            conn.execute(
                ADD_REVIEW,
                [
                    review["verdict"],
                    correction,
                    review["reviewer"],
                    review["seconds"],
                    review["note"] or None,
                    ticket_id,
                ],
            )
            _add_event(conn, ticket_id, "reviewed", {"verdict": review["verdict"]})
            _add_event(conn, ticket_id, "action_ran", outcome)

    def tickets(self) -> list[Saved]:
        with self._conn() as conn, conn.cursor(row_factory=dict_row) as cur:
            tickets = cur.execute(READ_TICKETS).fetchall()
            events: dict[str, list[Event]] = defaultdict(list)
            for row in cur.execute(
                "select ticket_id, kind, detail from events order by id"
            ).fetchall():
                events[row["ticket_id"]].append(
                    {"kind": row["kind"], "detail": row["detail"]}
                )
            decisions = {
                row["ticket_id"]: _proposal(row)
                for row in cur.execute(READ_DECISIONS).fetchall()
            }
            reviews = {
                row["ticket_id"]: (_verdict(row), row["created_at"].isoformat())
                for row in cur.execute(READ_REVIEWS).fetchall()
            }
        return [
            saved(
                t["id"],
                t["batch"],
                events[t["id"]],
                decisions.get(t["id"]),
                reviews.get(t["id"]),
            )
            for t in tickets
        ]


def open_store() -> Store:
    """Supabase when `SUPABASE_DB_URL` is set, otherwise memory."""
    url = os.getenv("SUPABASE_DB_URL")
    return PostgresStore(url) if url else MemoryStore()
