"""The staff directory in data/records, read once."""

import json
from functools import cache

from agent.config import USERS_FILE


@cache
def users() -> dict[str, dict]:
    """Every staff record, by AD username."""
    return {user["id"]: user for user in json.loads(USERS_FILE.read_text())}


def requester(user_id: str | None) -> dict | None:
    """One requester's record, or None when nobody is named. An unknown id raises."""
    if user_id is None:
        return None
    if user_id not in users():
        raise KeyError(f"No staff record for {user_id!r}.")
    return users()[user_id]
