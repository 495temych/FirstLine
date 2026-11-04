"""Keeps tests offline: the model and the encoder raise unless a test stubs them."""

from typing import NoReturn

import pytest

from agent import graph, retrieval


def _no_model_in_tests() -> NoReturn:
    raise AssertionError("Tests never call a model. Stub it instead.")


@pytest.fixture(autouse=True)
def no_real_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the model and the encoder with guards."""
    monkeypatch.setattr(graph, "_get_llm", _no_model_in_tests)
    monkeypatch.setattr(retrieval, "_get_model", _no_model_in_tests)
