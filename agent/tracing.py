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


def new_trace_id(seed: str) -> str | None:
    """A trace id fixed in advance, so a record can link to its trace. None if off."""
    return Langfuse.create_trace_id(seed=seed) if enabled() else None


@contextmanager
def trace(
    name: str,
    *,
    session_id: str | None = None,
    tags: tuple[str, ...] = (),
    metadata: dict[str, str] | None = None,
    trace_id: str | None = None,
) -> Iterator[None]:
    """Name the trace of every graph call inside, and group them by session.

    With a `trace_id`, everything inside lands in that one trace.
    """
    if not enabled():
        yield
        return
    lf = client()
    with propagate_attributes(
        trace_name=name, session_id=session_id, tags=list(tags), metadata=metadata
    ):
        if trace_id is None:
            yield
            return
        with lf.start_as_current_observation(
            trace_context={"trace_id": trace_id}, name=name
        ):
            yield


def trace_url(trace_id: str) -> str | None:
    """Where a trace opens in Langfuse."""
    return client().get_trace_url(trace_id=trace_id) if enabled() else None


def trace_steps(trace_id: str) -> list[dict]:
    """A trace's observations with their timing, model, tokens and cost.

    Empty until Langfuse has ingested the trace, which takes a few seconds.
    """
    found = client().api.observations.get_many(
        trace_id=trace_id, fields="core,basic,time,usage,model", limit=100
    )
    return [observation.model_dump() for observation in found.data]


def verdict(trace_id: str, value: str, comment: str | None = None) -> None:
    """Record a person's verdict on the trace it judges."""
    if enabled():
        client().create_score(
            trace_id=trace_id,
            name="technician_verdict",
            value=value,
            data_type="CATEGORICAL",
            comment=comment,
        )


def flush() -> None:
    """Send what's waiting, before a command-line run exits."""
    if enabled():
        client().flush()
