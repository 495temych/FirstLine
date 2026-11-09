"""The Queue: a batch from the service desk, triaged by the agent, decided by a person.

Tickets come from a simulated service desk: the development tickets, so held-out
tickets never appear. The desk hands them out like a real morning's mix, the oldest of
each kind of request in turn. The agent works each one with the same call the
Scoreboard measures, and only proposes. Nothing runs until a technician approves.

Every step is saved in Supabase as it happens, through `backend/store.py`, and the
board reads it back when the backend starts. Tickets left unfinished go back to the
agent then, and a ticket with a decision is never triaged again.
"""

import json
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import cache
from itertools import chain, zip_longest
from threading import Lock
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from agent import config, tools, tracing
from agent.decision import DEFAULT_PRIORITY
from agent.tool_schemas import ESCALATION_TOOL, QUEUES
from agent.triage import run_triage
from backend.store import REVIEWER, MemoryStore, Proposal, Saved, Store
from evals import retrieval_score, runner, scoring
from evals.import_tickets import family_of

SOURCE_SPLIT = "dev"  # the service desk's tickets, never the held-out ones
BATCH_SIZE = 8
WORKERS = 2
PRIORITIES = ("critical", "high", "medium", "low")
STATES = ("queued", "working", "review", "closed", "failed")
# docs/BUSINESS_GOAL.md's assumptions, until a client's own numbers replace them.
HIDDEN_STEPS = ("__start__", "route_")  # LangGraph's plumbing, not the agent's work
UNFINISHED = ("queued", "working")
DECISION_FIELDS = (
    "path",
    "cause",
    "reasoning",
    "tool",
    "tool_input",
    "queue",
    "priority",
    "summary",
    "retrieved",
)

Submit = Callable[[Callable[[], None]], object]


class Review(BaseModel):
    verdict: Literal["approved", "corrected", "rejected"]
    seconds: int = Field(ge=0, description="How long the technician took to decide.")
    queue: str | None = None
    note: Annotated[str, StringConstraints(strip_whitespace=True)] = ""


@cache
def staff() -> dict[str, dict]:
    """Staff records by username: name, department and device."""
    return {u["id"]: u for u in json.loads(config.USERS_FILE.read_text())}


def dispatch_order(ticket: dict) -> tuple[int, str]:
    """Most urgent first, then oldest."""
    priority = ticket["priority"]
    rank = PRIORITIES.index(priority) if priority in PRIORITIES else len(PRIORITIES)
    return rank, ticket["submitted_at"]


def card(ticket: dict, user: dict, batch: str) -> dict:
    """A ticket as the board shows it, before the agent has seen it."""
    device = user.get("device", {})
    return {
        "id": ticket["id"],
        "batch": batch,
        "title": ticket["title"],
        "description": ticket["description"],
        "priority": ticket["priority"],
        "sla_plan": ticket["sla_plan"],
        "submitted_at": ticket["submitted_at"],
        "applications": ticket["applications"],
        "requester": {
            "id": ticket["requester"],
            "name": user.get("name", ticket["requester"]),
            "department": user.get("department"),
            "office": user.get("office"),
            "device": device.get("id"),
        },
        "state": "queued",
        "decision": None,
        "agent_seconds": None,
        "cost_chf": None,
        "trace_id": None,
        "trace_url": None,
        "review": None,
        "error": None,
    }


def decision_of(result: dict) -> dict:
    """The agent's proposal, in the fields a technician reads."""
    escalating = result["path"] == "ESCALATE"
    ticket = (result["tool_input"] or {}) if escalating else {}
    return {
        "path": result["path"],
        "cause": result["cause"],
        "reasoning": result["reasoning"],
        "tool": None if escalating else result["tool_name"],
        "tool_input": None if escalating else result["tool_input"],
        "queue": ticket.get("queue"),
        "priority": ticket.get("priority"),
        "summary": ticket.get("summary"),
        "retrieved": [
            {"doc": u["doc"], "section": u["section"], "score": u["score"]}
            for u in result["retrieved"]
        ],
    }


def cost_usd(usage: dict | None) -> float | None:
    usage = usage or {}
    return config.cost_usd(
        config.model_name(), usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    )


def proposal_of(result: dict, seconds: float, trace_id: str | None) -> Proposal:
    """The decision as the record keeps it, with what it took to make it."""
    decision = decision_of(result)
    return {
        "path": decision["path"],
        "cause": decision["cause"],
        "reasoning": decision["reasoning"],
        "tool": decision["tool"],
        "tool_input": decision["tool_input"],
        "queue": decision["queue"],
        "priority": decision["priority"],
        "summary": decision["summary"],
        "retrieved": decision["retrieved"],
        "model": config.model_name(),
        "version": runner.version(),
        "trace_id": trace_id,
        "cost_usd": cost_usd(result["usage"]),
        "latency_ms": round(seconds * 1000),
    }


def decided(proposal: Proposal) -> dict:
    """What a decision adds to a ticket on the board."""
    usd = proposal["cost_usd"]
    trace_id = proposal["trace_id"]
    latency = proposal["latency_ms"]
    return {
        "decision": {field: proposal[field] for field in DECISION_FIELDS},
        "agent_seconds": None if latency is None else round(latency / 1000, 1),
        "cost_chf": None if usd is None else usd * scoring.USD_TO_CHF,
        "trace_id": trace_id,
        "trace_url": tracing.trace_url(trace_id) if trace_id else None,
    }


def restored(record: Saved, ticket: dict, user: dict) -> dict:
    """A ticket on the board again, as the record left it."""
    shown = card(ticket, user, record["batch"])
    unfinished = record["state"] in UNFINISHED
    shown["state"] = "queued" if unfinished else record["state"]
    shown["error"] = record["error"]
    if record["decision"]:
        shown.update(decided(record["decision"]))
    review = record["review"]
    if review:
        shown["review"] = {
            "verdict": review["verdict"],
            "seconds": review["seconds"],
            "queue": review["queue"],
            "note": review["note"],
            "outcome": record["outcome"] or {},
            "at": record["reviewed_at"],
        }
    return shown


def _escalate(queue: str, summary: str, priority: str | None) -> dict:
    return tools.dispatch(
        ESCALATION_TOOL,
        {"queue": queue, "summary": summary, "priority": priority or DEFAULT_PRIORITY},
    )


def carry_out(ticket: dict, review: Review) -> dict:
    """What happens once a technician decides. Every action here is simulated."""
    decision = ticket["decision"]
    summary = decision["summary"] or ticket["title"]
    if review.verdict == "rejected":
        return {"detail": "Returned to the desk to handle by hand."}
    if review.verdict == "corrected":
        return _escalate(review.queue or "", summary, decision["priority"])
    if decision["path"] == "AUTO_FIX":
        return tools.dispatch(decision["tool"], decision["tool_input"] or {})
    if decision["path"] == "ESCALATE":
        return _escalate(decision["queue"], summary, decision["priority"])
    if decision["path"] == "SELF_SERVE":
        return {"detail": "Steps sent to the requester."}
    return {"detail": "Closed as out of scope, and the requester was told."}


def check(review: Review) -> None:
    if review.verdict == "corrected" and review.queue not in QUEUES:
        raise HTTPException(422, "Choose the team that should take this ticket.")
    if review.verdict == "rejected" and not review.note:
        raise HTTPException(422, "Say why the decision is wrong.")


def steps_of(observations: list[dict]) -> list[dict]:
    """A trace's steps in order, with offsets from its start, for a timeline."""
    shown = [
        o
        for o in observations
        if o["start_time"] and not o["name"].startswith(HIDDEN_STEPS)
    ]
    if not shown:
        return []
    start = min(o["start_time"] for o in shown)
    steps = []
    for o in sorted(shown, key=lambda o: o["start_time"]):
        end = o["end_time"] or o["start_time"]
        usage = o.get("usage_details") or {}
        steps.append(
            {
                "name": o["name"],
                "type": o["type"],
                "start_ms": round((o["start_time"] - start).total_seconds() * 1000),
                "duration_ms": round((end - o["start_time"]).total_seconds() * 1000),
                "model": o.get("model"),
                "input_tokens": usage.get("input"),
                "output_tokens": usage.get("output"),
                "cost_usd": o.get("total_cost"),
            }
        )
    return steps


class Board:
    """The tickets on the board, in dispatch order, and the work on them."""

    def __init__(self, submit: Submit, store: Store | None = None) -> None:
        self._submit = submit
        self._lock = Lock()
        self.store: Store = store or MemoryStore()
        self.tickets: dict[str, dict] = {}

    def restore(self, store: Store) -> list[str]:
        """Read the record back after a restart, and finish what was left."""
        desk = {t["id"]: t for t in retrieval_score.load_split(SOURCE_SPLIT)}
        users = staff()
        records = [r for r in store.tickets() if r["id"] in desk]
        batches = {
            b: i for i, b in enumerate(dict.fromkeys(r["batch"] for r in records))
        }
        records.sort(key=lambda r: (batches[r["batch"]], dispatch_order(desk[r["id"]])))
        with self._lock:
            self.store = store
            self.tickets = {
                r["id"]: restored(
                    r, desk[r["id"]], users.get(desk[r["id"]]["requester"], {})
                )
                for r in records
            }
        unfinished = [r["id"] for r in records if r["state"] in UNFINISHED]
        for ticket_id in unfinished:
            self._submit(lambda ticket_id=ticket_id: self.work(ticket_id))
        return unfinished

    def waiting_at_desk(self) -> list[dict]:
        """The desk's tickets not yet on the board: each kind's oldest, in turn."""
        tickets = retrieval_score.load_split(SOURCE_SPLIT)
        fresh = sorted(
            (t for t in tickets if t["id"] not in self.tickets),
            key=lambda t: t["submitted_at"],
        )
        kinds: dict[str, list[dict]] = {}
        for ticket in fresh:
            kinds.setdefault(family_of(ticket["id"]), []).append(ticket)
        mixed = chain.from_iterable(zip_longest(*kinds.values()))
        return [ticket for ticket in mixed if ticket is not None]

    def load(self, users: dict[str, dict]) -> list[str]:
        """Take the next batch from the desk and start the agent on it."""
        with self._lock:
            taken = sorted(self.waiting_at_desk()[:BATCH_SIZE], key=dispatch_order)
            batch = self.store.add_batch(
                datetime.now(UTC).strftime("%Y%m%dT%H%M%S"),
                [
                    {
                        "id": t["id"],
                        "text": f"{t['title']}\n\n{t['description']}",
                        "requester": t["requester"],
                    }
                    for t in taken
                ],
            )
            for ticket in taken:
                user = users.get(ticket["requester"], {})
                self.tickets[ticket["id"]] = card(ticket, user, batch)
        for ticket in taken:
            self._submit(lambda ticket_id=ticket["id"]: self.work(ticket_id))
        return [t["id"] for t in taken]

    def _update(self, ticket_id: str, **fields: object) -> dict:
        with self._lock:
            self.tickets[ticket_id].update(fields)
            return dict(self.tickets[ticket_id])

    def work(self, ticket_id: str) -> None:
        """Triage one ticket. A failure fails this ticket alone."""
        self.store.started(ticket_id)
        ticket = self._update(ticket_id, state="working")
        trace_id = tracing.new_trace_id(f"queue {ticket['batch']} {ticket_id}")
        started = time.perf_counter()
        try:
            with tracing.trace(
                "queue",
                session_id=f"queue-{ticket['batch']}",
                tags=("queue",),
                metadata={"ticket": ticket_id},
                trace_id=trace_id,
            ):
                result = run_triage(
                    f"{ticket['title']}\n\n{ticket['description']}", use_retrieval=True
                )
            elapsed = time.perf_counter() - started
        except Exception as exc:  # the batch carries on without this ticket
            error = f"{type(exc).__name__}: {exc}"
            self.store.failed(ticket_id, error)
            self._update(ticket_id, state="failed", error=error)
            return
        # Langfuse sends the trace in the background, so the next ticket needn't wait.
        proposal = proposal_of(result, elapsed, trace_id)
        self.store.decided(ticket_id, proposal)
        self._update(ticket_id, state="review", **decided(proposal))

    def review(self, ticket_id: str, review: Review) -> dict:
        """Record a technician's decision, then carry it out."""
        check(review)
        with self._lock:
            ticket = self.tickets.get(ticket_id)
            if ticket is None:
                raise HTTPException(404, "This ticket isn't on the board.")
            if ticket["state"] != "review":
                raise HTTPException(409, "This ticket isn't waiting for a decision.")
            try:
                outcome = carry_out(ticket, review)
            except (KeyError, TypeError) as exc:
                raise HTTPException(
                    422, f"The proposed fix can't run as written: {exc}"
                ) from exc
            self.store.reviewed(
                ticket_id,
                {
                    "verdict": review.verdict,
                    "seconds": review.seconds,
                    "queue": review.queue,
                    "note": review.note,
                    "reviewer": REVIEWER,
                },
                outcome,
            )
            ticket["state"] = "closed"
            ticket["review"] = {
                **review.model_dump(),
                "outcome": outcome,
                "at": datetime.now(UTC).isoformat(),
            }
            closed = dict(ticket)
        if closed["trace_id"]:
            tracing.verdict(closed["trace_id"], review.verdict, review.note or None)
        return closed

    def get(self, ticket_id: str) -> dict:
        with self._lock:
            if ticket_id not in self.tickets:
                raise HTTPException(404, "This ticket isn't on the board.")
            return dict(self.tickets[ticket_id])

    def view(self) -> dict:
        """Every ticket, the count in each state, and how the batch went."""
        with self._lock:
            tickets = [dict(t) for t in self.tickets.values()]
        reviews = [t["review"] for t in tickets if t["review"]]
        timed = [t["agent_seconds"] for t in tickets if t["agent_seconds"] is not None]
        approved = sum(r["verdict"] == "approved" for r in reviews)
        model_cost = sum(t["cost_chf"] or 0 for t in tickets)
        return {
            "tickets": tickets,
            "counts": {s: sum(t["state"] == s for t in tickets) for s in STATES},
            "at_desk": len(self.waiting_at_desk()),
            "batch_size": BATCH_SIZE,
            "queues": QUEUES,
            "value": {
                "model_cost_chf": model_cost,
                "agent_seconds": sum(timed) / len(timed) if timed else None,
                "reviewed": len(reviews),
                "approved": approved,
                "review_seconds": (
                    sum(r["seconds"] for r in reviews) / len(reviews)
                    if reviews
                    else None
                ),
            },
        }


_workers = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="queue")
board = Board(_workers.submit)
router = APIRouter()


def start(store: Store) -> list[str]:
    """Open the record when the backend starts, and carry on where it stopped."""
    return board.restore(store)


@router.get("/api/queue", operation_id="read_queue")
def read_queue() -> dict:
    """The board: every ticket, its state, and what the work is worth so far."""
    return board.view()


@router.post("/api/queue/load", operation_id="load_batch")
def load_batch() -> dict:
    """Take the next batch from the service desk and start triage on it."""
    if not board.waiting_at_desk():
        raise HTTPException(409, "The service desk has no more tickets.")
    board.load(staff())
    return board.view()


@router.post("/api/queue/tickets/{ticket_id}/review", operation_id="review_ticket")
def review_ticket(ticket_id: str, review: Review) -> dict:
    """Approve, correct or reject the agent's decision, and carry it out."""
    return board.review(ticket_id, review)


@router.get("/api/queue/tickets/{ticket_id}/trace", operation_id="read_trace")
def read_trace(ticket_id: str) -> dict:
    """The ticket's trace from Langfuse: each step, its time, tokens and cost."""
    ticket = board.get(ticket_id)
    if not ticket["trace_id"]:
        return {"status": "off", "url": None, "steps": []}
    steps = steps_of(tracing.trace_steps(ticket["trace_id"]))
    status = "ready" if steps else "pending"
    return {"status": status, "url": ticket["trace_url"], "steps": steps}
