"""Sends each run to Langfuse as a trace, when its keys are in the environment.

Tracing is off without `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`, or when
`LANGFUSE_TRACING` is `false`, which tests and the browser tests set. Emails, employee
ids and IP addresses are masked before anything leaves the machine.
"""

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langfuse import Langfuse, propagate_attributes
from langfuse.langchain import CallbackHandler
from langfuse.span_filter import is_langfuse_span

KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
SWITCH = "LANGFUSE_TRACING"
MASKS = (
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    (re.compile(r"\bE(?:MP)?-\d{4,6}\b"), "[employee id]"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "[ip address]"),
)


def redact(data: Any) -> Any:
    """The same data with personal details masked, in strings at any depth."""
    if isinstance(data, str):
        for pattern, label in MASKS:
            data = pattern.sub(label, data)
        return data
    if isinstance(data, dict):
        return {key: redact(value) for key, value in data.items()}
    if isinstance(data, list | tuple):
        return [redact(value) for value in data]
    return data


def _mask(*, data: Any, **_: Any) -> Any:
    return redact(data)


def enabled() -> bool:
    """Whether runs are traced: both keys are set and tracing isn't switched off."""
    switched_off = os.getenv(SWITCH, "true").lower() == "false"
    return not switched_off and all(os.getenv(key) for key in KEYS)


@cache
def client() -> Langfuse:
    """The one Langfuse client, reading its keys and address from the environment.

    It exports only its own spans. The Anthropic SDK also traces each call, which
    would count every model call twice and skip the mask.
    """
    return Langfuse(mask=_mask, should_export_span=is_langfuse_span)


def callbacks() -> list[BaseCallbackHandler]:
    """What a graph call passes in its config to be traced. Empty when it's off."""
    if not enabled():
        return []
    client()
    return [CallbackHandler()]


@contextmanager
def trace(
    name: str,
    *,
    session_id: str | None = None,
    tags: tuple[str, ...] = (),
    metadata: dict[str, str] | None = None,
) -> Iterator[None]:
    """Name the trace of every graph call inside, and group them by session."""
    if not enabled():
        yield
        return
    client()
    with propagate_attributes(
        trace_name=name, session_id=session_id, tags=list(tags), metadata=metadata
    ):
        yield


def flush() -> None:
    """Send what's waiting, before a command-line run exits."""
    if enabled():
        client().flush()
