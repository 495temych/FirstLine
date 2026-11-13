"""Each action runs once. It carries a key made from its ticket and what it does, and
the ledger keeps the key with the action's outcome, so a second attempt with the same
key returns the first outcome without running again.

An action claims its key before it runs and records its outcome after. A key that is
claimed with no outcome belongs to an action cut off by a restart: it may or may not
have happened, so it is held for a person instead of run again. An action whose input
doesn't fit its tool gives its key back, since nothing ran.

The backend keeps the ledger in Supabase, through `backend/store.py`, and installs it
with `use` when it starts. Without it the ledger is in memory.
"""

import hashlib
import json
from threading import Lock
from typing import Protocol, TypedDict

from agent import tools

HELD = (
    "This action was cut off by a restart before its outcome was recorded, so it "
    "isn't run again. Check by hand whether it happened."
)


class Ledger(Protocol):
    def claim(self, key: str, ticket_id: str, tool: str, tool_input: dict) -> bool:
        """True when the key was free and is now this action's."""
        ...

    def outcome(self, key: str) -> dict | None: ...
    def finish(self, key: str, outcome: dict) -> None: ...
    def release(self, key: str) -> None: ...


class Entry(TypedDict):
    ticket_id: str
    tool: str
    tool_input: dict
    outcome: dict | None


class MemoryLedger:
    """The ledger in memory, for tests and for running without Supabase."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._entries: dict[str, Entry] = {}

    def claim(self, key: str, ticket_id: str, tool: str, tool_input: dict) -> bool:
        with self._lock:
            if key in self._entries:
                return False
            self._entries[key] = {
                "ticket_id": ticket_id,
                "tool": tool,
                "tool_input": tool_input,
                "outcome": None,
            }
            return True

    def outcome(self, key: str) -> dict | None:
        with self._lock:
            entry = self._entries.get(key)
            return None if entry is None else entry["outcome"]

    def finish(self, key: str, outcome: dict) -> None:
        with self._lock:
            self._entries[key]["outcome"] = outcome

    def release(self, key: str) -> None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry["outcome"] is None:
                del self._entries[key]


def key_of(ticket_id: str, tool: str, tool_input: dict) -> str:
    """The same ticket and the same action always make the same key."""
    action = json.dumps([ticket_id, tool, tool_input], sort_keys=True)
    return hashlib.sha256(action.encode()).hexdigest()[:32]


def perform(ledger: Ledger, ticket_id: str, tool: str, tool_input: dict) -> dict:
    """Run the action unless its key has run before, and return its outcome."""
    key = key_of(ticket_id, tool, tool_input)
    if not ledger.claim(key, ticket_id, tool, tool_input):
        done = ledger.outcome(key)
        return done if done is not None else {"status": "held", "detail": HELD}
    try:
        outcome = {**tools.dispatch(tool, tool_input), "action_key": key}
    except (KeyError, TypeError):
        ledger.release(key)  # its input didn't fit the tool, so nothing ran
        raise
    ledger.finish(key, outcome)
    return outcome


_installed: list[Ledger] = [MemoryLedger()]


def use(ledger: Ledger) -> None:
    """Keep actions in this ledger from now on."""
    _installed[0] = ledger


def ledger() -> Ledger:
    return _installed[0]
