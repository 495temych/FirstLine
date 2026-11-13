"""The real API and graph with a stub model, so the browser tests cost nothing.

The ticket text picks the stub's answer. Everything is written to a temporary folder,
and the record and paused runs are kept in memory, never in Supabase.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["LANGFUSE_TRACING"] = "false"  # before .env is read, so nothing is traced
os.environ["SUPABASE_DB_URL"] = ""  # and the Queue keeps its record in memory

import uvicorn
from langchain_core.messages import ToolMessage

from agent import graph, lookups, retrieval
from agent.tests.fakes import (
    UNIT,
    FakeLLM,
    call,
    decision,
    fix,
    out_of_scope,
    steps,
)
from backend import main
from evals import retrieval_score, runner

ANSWERS = {
    "fix": fix("reset_vpn_profile", "Reset the profile.", username="a.b"),
    "lockout": decision(
        "ESCALATE",
        "Repeat lockout, a possible compromise.",
        cause="Repeat lockout",
        queue="SEC-INCIDENT",
        summary="Repeat lockout",
        priority="P2-High",
        evidence=["s1", "s2"],
        ruled_out="A mistyped password: the lockouts come from another device.",
        next_step="Find the device that sends the old password.",
    ),
    "locked out": fix(
        "unlock_ad_account", "A routine unlock.", username="current.user"
    ),
    "steps": steps("Reseat the cable."),
    "weather": out_of_scope(),
}


TURN_SEC = 0.4  # each model turn takes this long, so the page can show each step
LOOKUPS = [
    call("lookup_requester"),
    call("run_check", step="account-lockout-source-check"),
]


class StubLLM(FakeLLM):
    """Answers by the ticket's words. In the loop it looks two things up first.

    Runs overlap when tests run in parallel, so each bind gets its own copy and a
    turn keeps its answer to itself."""

    def __init__(self, tools=None):
        super().__init__([])
        self.bound_tools = tools

    def bind_tools(self, tools, tool_choice=None):
        return StubLLM(tools)

    def invoke(self, messages):
        time.sleep(TURN_SEC)
        # Only the ticket picks the answer, not the requester's record before it.
        ticket = str(messages[1].content).partition("User issue: ")[2]
        offered = {tool["name"] for tool in self.bound_tools or []}
        looked = any(isinstance(m, ToolMessage) for m in messages)
        if "lookup_requester" in offered and not looked:
            blocks = LOOKUPS
        else:
            blocks = next(
                (blocks for word, blocks in ANSWERS.items() if word in ticket),
                ANSWERS["weather"],
            )
        return FakeLLM(blocks).invoke(messages)


def prepare(folder: Path) -> None:
    """Point everything at temporary files and save one evaluation."""
    runner.RUNS_DIR = folder / "runs"
    retrieval_score.RUNS_DIR = folder / "retrieval"
    llm = StubLLM()
    graph._get_llm = lambda: llm
    graph.retrieve = lambda q: [UNIT]
    lookups.retrieve = lambda q: [UNIT]
    main.os.environ["ANTHROPIC_API_KEY"] = "stub"
    runner.save_run(runner.evaluate("rules", tiny=True))
    retrieval.retrieve = lambda q: []
    retrieval.rank_playbooks = lambda q: []
    retrieval_score.save_run(retrieval_score.evaluate("unseen_dev"))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as folder:
        prepare(Path(folder))
        uvicorn.run(main.app, port=int(sys.argv[1]))
