"""The FirstLine API. It's thin: the graph holds all the triage logic."""

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import cache
from threading import Lock
from typing import Annotated, Literal
from uuid import uuid4

import anthropic
from fastapi import FastAPI, HTTPException
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, StateSnapshot
from pydantic import BaseModel, StringConstraints

from agent import config, records, tracing
from agent.graph import build_graph, initial_state
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
]


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


class GateAnswer(BaseModel):
    # Naming the gate means a repeated click can't answer the gate that follows it.
    gate: Literal["confirm_fix", "confirm_ticket", "self_serve"]
    approved: bool


@cache
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


def _view(run_id: str, snapshot: StateSnapshot) -> dict:
    fields = {name: snapshot.values[name] for name in RUN_FIELDS}
    return {"id": run_id, **fields, "pending": _pending(snapshot)}


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


@app.post("/api/triage", operation_id="start_triage")
def start_triage(ticket: NewTicket) -> dict:
    """Triage a ticket up to its first human gate."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "ANTHROPIC_API_KEY isn't set. Add it to .env.")
    if ticket.requester not in records.users():
        raise HTTPException(422, "That requester isn't in the staff directory.")
    run_id = uuid4().hex
    state = initial_state(
        ticket.text,
        ticket.use_retrieval,
        records.requester(ticket.requester),
        "assistant",
    )
    try:
        with _traced(run_id):
            _graph().invoke(state, _thread(run_id))
    except anthropic.APIError as exc:
        raise HTTPException(502, f"The model call failed: {exc}") from exc
    snapshot = _snapshot(run_id)
    values = snapshot.values
    if values["path"] in stats.PATHS:  # a run without retrieval is a comparison only
        decision = queue_board.proposal_of(values, values["response_time_sec"], None)
        store.shared().add_run(run_id, ticket.text, ticket.requester, decision)
    return _view(run_id, snapshot)


@app.get("/api/runs/{run_id}", operation_id="read_run")
def read_run(run_id: str) -> dict:
    """Read one run, including the gate it's waiting at."""
    return _view(run_id, _snapshot(run_id))


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
