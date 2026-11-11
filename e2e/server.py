"""The real API and graph with a stub model, so the browser tests cost nothing.

The ticket text picks the stub's answer. Everything is written to a temporary folder,
and the record and paused runs are kept in memory, never in Supabase.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ["LANGFUSE_TRACING"] = "false"  # before .env is read, so nothing is traced
os.environ["SUPABASE_DB_URL"] = ""  # and the Queue keeps its record in memory

import uvicorn

from agent import graph, retrieval
from agent.tests.fakes import UNIT, FakeLLM, escalate, fix, out_of_scope, steps
from backend import main
from evals import retrieval_score, runner

ANSWERS = {
    "fix": fix("reset_vpn_profile", "Reset the profile.", username="a.b"),
    "lockout": escalate(
        "SEC-INCIDENT", "Repeat lockout, a possible compromise.", "Repeat lockout"
    ),
    "locked out": fix(
        "unlock_ad_account", "A routine unlock.", username="current.user"
    ),
    "steps": steps("Reseat the cable."),
    "weather": out_of_scope(),
}


class StubLLM(FakeLLM):
    def __init__(self):
        super().__init__([])

    def invoke(self, messages):
        # Only the ticket picks the answer, not the requester's record before it.
        ticket = messages[-1].content.partition("User issue: ")[2]
        self.blocks = next(
            (blocks for word, blocks in ANSWERS.items() if word in ticket),
            ANSWERS["weather"],
        )
        return super().invoke(messages)


def prepare(folder: Path) -> None:
    """Point everything at temporary files and save one evaluation."""
    runner.RUNS_DIR = folder / "runs"
    retrieval_score.RUNS_DIR = folder / "retrieval"
    llm = StubLLM()
    graph._get_llm = lambda: llm
    graph.retrieve = lambda q: [UNIT]
    main.os.environ["ANTHROPIC_API_KEY"] = "stub"
    runner.save_run(runner.evaluate("rules", tiny=True))
    retrieval.retrieve = lambda q: []
    retrieval.rank_playbooks = lambda q: []
    retrieval_score.save_run(retrieval_score.evaluate("unseen_dev"))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as folder:
        prepare(Path(folder))
        uvicorn.run(main.app, port=int(sys.argv[1]))
