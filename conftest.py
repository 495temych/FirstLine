"""Keeps tests offline: the model and the encoder raise unless a test stubs them,
nothing is traced, and search uses an in-memory index."""

from typing import NoReturn

import pytest

from agent import graph, retrieval


def _no_model_in_tests() -> NoReturn:
    raise AssertionError("Tests never call a model. Stub it instead.")


@pytest.fixture(autouse=True)
def no_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every test away from Langfuse, whatever keys .env holds."""
    monkeypatch.setenv("LANGFUSE_TRACING", "false")


@pytest.fixture(autouse=True)
def no_qdrant_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    """Search an in-memory index, whatever Qdrant address .env holds."""
    monkeypatch.delenv("QDRANT_URL", raising=False)


@pytest.fixture(autouse=True)
def no_real_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the model and the encoder with guards."""
    monkeypatch.setattr(graph, "_get_llm", _no_model_in_tests)
    monkeypatch.setattr(retrieval, "_get_model", _no_model_in_tests)
