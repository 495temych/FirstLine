"""The FirstLine API. It's thin: the graph holds all the triage logic."""

import json
import os
import sqlite3
from functools import cache
from threading import Lock
from typing import Annotated, Literal
from uuid import uuid4

import anthropic
from fastapi import FastAPI, HTTPException
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command, StateSnapshot
from pydantic import BaseModel, StringConstraints

from agent import config, tracing
from agent.graph import build_graph, initial_state
from backend import queue_board, stats
from evals import retrieval_score, runner, scoring

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
]

app = FastAPI(title="FirstLine")
app.include_router(queue_board.router)

_gate_lock = Lock()  # two answers to one gate must not both pass its check


class NewTicket(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    use_retrieval: bool


class GateAnswer(BaseModel):
    # Naming the gate means a repeated click can't answer the gate that follows it.
    gate: Literal["confirm_fix", "confirm_ticket", "self_serve"]
    approved: bool


@cache
def _graph():
    # check_same_thread=False: FastAPI runs each request on a worker thread, and
    # SqliteSaver serializes access with an internal lock.
    connection = sqlite3.connect(config.CHECKPOINT_DB, check_same_thread=False)
    return build_graph(SqliteSaver(connection))


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
    run_id = uuid4().hex
    try:
        with _traced(run_id):
            _graph().invoke(
                initial_state(ticket.text, ticket.use_retrieval), _thread(run_id)
            )
    except anthropic.APIError as exc:
        raise HTTPException(502, f"The model call failed: {exc}") from exc
    return _view(run_id, _snapshot(run_id))


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
    return _view(run_id, _snapshot(run_id))


def readable(run: dict) -> dict:
    """A saved run as the API may show it: a held-out run keeps its scores only."""
    return run if run["set"] in READABLE_SETS else {**run, "tickets": []}


@app.get("/api/evaluations", operation_id="list_evaluations")
def list_evaluations() -> dict:
    """List saved evaluations and retrieval scores, with the assumed mistake costs."""
    return {
        "runs": [readable(run) for run in runner.load_runs()],
        "retrieval": retrieval_score.load_runs(),
        "costs": {
            "security": scoring.COST_SECURITY,
            "wrong": scoring.COST_WRONG,
            "minor": scoring.COST_MINOR,
        },
    }


@app.get("/api/tickets", operation_id="list_tickets")
def list_tickets() -> list[dict]:
    """List the tickets to review. Held-out tickets stay out, as they're the exam."""
    latest = latest_results(runner.load_runs())
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


@app.get("/api/stats", operation_id="read_stats")
def read_stats() -> dict:
    """Read the live usage statistics from logs.csv."""
    return {**stats.summary_stats(), "paths": stats.PATHS}
