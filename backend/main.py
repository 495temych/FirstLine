"""The FirstLine API. It's thin: the graph holds all the triage logic."""

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import cache
from threading import Lock, Thread
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, StateSnapshot
from pydantic import BaseModel, StringConstraints

from agent import config, records, tracing
from agent.graph import GraphState, build_graph, initial_state
from backend import (
    benchmark,
    economics,
    harness,
    overview,
    queue_board,
    retrieval_view,
    stats,
    store,
)
from evals import runner, scoring

RUN_FIELDS = [
    "query",
    "use_retrieval",
    "retrieved",
    "path",
    "reasoning",
    "tool_name",
    "tool_input",
    "human_decision",
    "ticket_draft",
    "tool_result",
    "rule",
    "design",
    "stopped",
]
EXAMPLE_SPLIT = "dev"  # the Assistant's real examples, one per family


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """The Queue reads its record back, from Supabase when it's set up."""
    queue_board.start(store.shared())
    yield


app = FastAPI(title="FirstLine", lifespan=lifespan)
app.include_router(queue_board.router)
app.include_router(overview.router)
app.include_router(retrieval_view.router)
app.include_router(economics.router)
app.include_router(benchmark.router)
app.include_router(harness.router)

_gate_lock = Lock()  # two answers to one gate must not both pass its check


class NewTicket(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    use_retrieval: bool
    # The AD username of the person asking, from the staff directory.
    requester: str
    # A development ticket picked as an example, so its recorded checks can be read.
    ticket_id: str | None = None


class GateAnswer(BaseModel):
    # Naming the gate means a repeated click can't answer the gate that follows it.
    gate: Literal["confirm_fix", "confirm_ticket", "self_serve"]
    approved: bool


@store.once  # runs start in their own threads, so two may ask for it at once
def _graph():
    """The graph, saving paused runs in Supabase so they survive a restart."""
    return build_graph(store.checkpointer())


def _thread(run_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": run_id}, "callbacks": tracing.callbacks()}


def _traced(run_id: str):
    """Each step of one Assistant run, grouped in Langfuse as one session."""
    return tracing.trace("assistant", session_id=run_id, tags=("assistant",))


def _snapshot(run_id: str) -> StateSnapshot:
    snapshot = _graph().get_state(_thread(run_id))
    if not snapshot.values:
        raise HTTPException(404, "This run doesn't exist.")
    return snapshot


def _pending(snapshot: StateSnapshot) -> dict | None:
    return snapshot.interrupts[0].value if snapshot.interrupts else None


# Runs working in the background in this process, and why any of them failed.
running: dict[str, Thread] = {}
_started: dict[str, GraphState] = {}  # each running run's first state, until it's saved
_failed: dict[str, str] = {}


def _status(run_id: str, pending: dict | None) -> str:
    if run_id in running:
        return "running"
    if run_id in _failed:
        return "failed"
    return "waiting" if pending else "done"


def _chf(usd: float | None) -> float | None:
    return None if usd is None else usd * config.USD_TO_CHF


def _steps(values: GraphState | dict) -> list[dict]:
    """The loop's steps, with each one's cost in francs for the page."""
    return [{**step, "cost_chf": _chf(step["cost_usd"])} for step in values["steps"]]


def _view_of(
    run_id: str, values: GraphState | dict, nodes: list[str], pending: dict | None
) -> dict:
    requester = values["requester"] or {}
    return {
        "id": run_id,
        **{name: values[name] for name in RUN_FIELDS},
        "steps": _steps(values),
        "requester": {
            key: requester.get(key) for key in ("id", "department", "office")
        },
        "pending": pending,
        "status": _status(run_id, pending),
        "error": _failed.get(run_id),
        "next": nodes,
    }


def _view(run_id: str, snapshot: StateSnapshot) -> dict:
    pending = _pending(snapshot)
    return _view_of(run_id, snapshot.values, list(snapshot.next), pending)


def _read(run_id: str) -> dict:
    """A run as the page reads it, also before its first step is saved."""
    snapshot = _graph().get_state(_thread(run_id))
    if not snapshot.values and run_id in _started:
        return _view_of(run_id, _started[run_id], ["retrieve"], None)
    return _view(run_id, _snapshot(run_id))


def _work(run_id: str, state: GraphState, ticket: "NewTicket") -> None:
    """Run triage up to its first gate, saving each step as it goes."""
    try:
        with _traced(run_id):
            _graph().invoke(state, _thread(run_id))
        values = _snapshot(run_id).values
        if values["path"] in stats.PATHS:  # a run without retrieval is a comparison
            decision = queue_board.proposal_of(
                values, values["response_time_sec"], None
            )
            store.shared().add_run(run_id, ticket.text, ticket.requester, decision)
    except Exception as exc:  # the page reads the failure instead of a crash
        _failed[run_id] = f"The run failed: {type(exc).__name__}: {exc}"
    finally:
        _started.pop(run_id, None)
        running.pop(run_id, None)


READABLE_SETS = {"rules", *runner.REVIEW_SPLITS}


def latest_results(runs: list[dict]) -> dict[str, dict]:
    """Each reviewable ticket's newest result. `runs` is newest first."""
    latest: dict[str, dict] = {}
    for run in runs:
        if run["set"] in READABLE_SETS:
            for ticket in run["tickets"]:
                latest.setdefault(ticket["id"], ticket)
    return latest


@app.get("/api/health", operation_id="health")
def health() -> dict:
    """Check that the backend is running and has a model key."""
    return {"status": "ok", "api_key": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@cache
def examples() -> dict[str, dict]:
    """A development ticket from each family, with its requester, by id."""
    picked: dict[str, dict] = {}
    for ticket, answer in sorted(
        runner.load_imported(EXAMPLE_SPLIT), key=lambda pair: pair[0]["id"]
    ):
        picked.setdefault(answer["family"], ticket)
    return {ticket["id"]: ticket for ticket in picked.values()}


@app.get("/api/examples", operation_id="list_examples")
def list_examples() -> list[dict]:
    """Real development tickets to try, whose checks were recorded. Never held-out."""
    return [
        {
            "id": ticket["id"],
            "title": ticket["text"].partition("\n")[0],
            "text": ticket["text"],
            "requester": ticket["requester"],
        }
        for ticket in examples().values()
    ]


@app.post("/api/triage", operation_id="start_triage")
def start_triage(ticket: NewTicket) -> dict:
    """Start triage in the background. The page reads its steps as they happen."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "ANTHROPIC_API_KEY isn't set. Add it to .env.")
    if ticket.requester not in records.users():
        raise HTTPException(422, "That requester isn't in the staff directory.")
    if ticket.ticket_id is not None and ticket.ticket_id not in examples():
        raise HTTPException(422, "Only the example tickets can be named.")
    run_id = uuid4().hex
    state = initial_state(
        ticket.text,
        ticket.use_retrieval,
        records.requester(ticket.requester),
        "assistant",
        ticket.ticket_id,
    )
    state["design"] = config.ASSISTANT_DESIGN
    _started[run_id] = state
    worker = Thread(target=_work, args=(run_id, state, ticket), daemon=True)
    running[run_id] = worker
    worker.start()
    return _read(run_id)


@app.get("/api/runs/{run_id}", operation_id="read_run")
def read_run(run_id: str) -> dict:
    """Read one run: its steps so far, and the gate it's waiting at."""
    return _read(run_id)


@app.post("/api/runs/{run_id}/answer", operation_id="answer_gate")
def answer_gate(run_id: str, answer: GateAnswer) -> dict:
    """Answer the gate a run is waiting at."""
    with _gate_lock:
        pending = _pending(_snapshot(run_id))
        if pending is None or pending["kind"] != answer.gate:
            raise HTTPException(409, "This run isn't waiting at that gate.")
        with _traced(run_id):
            _graph().invoke(Command(resume=answer.approved), _thread(run_id))
        snapshot = _snapshot(run_id)
        ran = not snapshot.next and snapshot.values["tool_result"] is not None
        store.shared().answered(
            run_id,
            {"gate": answer.gate, "approved": answer.approved},
            snapshot.values["tool_result"] if ran else None,
        )
    return _view(run_id, snapshot)


def readable(run: dict) -> dict:
    """A saved run as the API may show it: a held-out run keeps its scores only."""
    return run if run["set"] in READABLE_SETS else {**run, "tickets": []}


@app.get("/api/evaluations", operation_id="list_evaluations")
def list_evaluations() -> dict:
    """List saved evaluations, with the assumed mistake costs."""
    return {
        "runs": [readable(run) for run in runner.load_runs()],
        "costs": {
            "security": scoring.COST_SECURITY,
            "wrong": scoring.COST_WRONG,
            "minor": scoring.COST_MINOR,
        },
    }


@app.get("/api/tickets", operation_id="list_tickets")
def list_tickets() -> list[dict]:
    """List the tickets to review. Held-out tickets stay out, as they're the exam."""
    latest = latest_results(runner.default_runs(full=False))
    users = {u["id"]: u for u in json.loads(config.USERS_FILE.read_text())}
    return [
        {
            **ticket,
            "answer": answer,
            "requester": users[ticket["requester"]],
            "latest": latest.get(ticket["id"]),
        }
        for ticket, answer in runner.load_review_tickets()
    ]


@app.get("/api/requesters", operation_id="list_requesters")
def list_requesters() -> list[dict]:
    """List the staff a ticket can come from, the rules set's users first."""
    rules_users = {ticket["requester"] for ticket, _ in runner.load_any("rules")}
    people = [
        {
            "id": user["id"],
            "name": user["name"],
            "department": user["department"],
            "office": user["office"],
            "lockouts_24h": user["lockouts_24h"],
            "device": user["device"],
            "rules_set": user["id"] in rules_users,
        }
        for user in records.users().values()
    ]
    return sorted(people, key=lambda p: (not p["rules_set"], p["id"]))


@app.get("/api/stats", operation_id="read_stats")
def read_stats() -> dict:
    """Read the live usage statistics from the Assistant's runs."""
    return {**stats.summary_stats(store.shared().runs()), "paths": stats.PATHS}
