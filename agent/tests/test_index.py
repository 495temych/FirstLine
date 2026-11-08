"""The command that builds the Qdrant Cloud index, against an in-memory client."""

import pytest
from qdrant_client import QdrantClient

from agent import index, retrieval


def test_the_command_needs_an_address():
    with pytest.raises(SystemExit, match="QDRANT_URL"):
        index.main()


def test_the_command_builds_checks_and_reports(monkeypatch, capsys):
    client = QdrantClient(":memory:")
    monkeypatch.setenv("QDRANT_URL", "https://example.test")
    monkeypatch.setattr(retrieval, "cloud_client", lambda: client)
    monkeypatch.setattr(retrieval, "build_index", lambda c: 7)
    monkeypatch.setattr(retrieval, "index_problem", lambda c: None)
    monkeypatch.setattr(retrieval, "kb_version", lambda: "abcd1234")
    index.main()
    assert capsys.readouterr().out.strip() == (
        "7 sections in kb_sections, knowledge base abcd1234"
    )


def test_the_command_fails_if_the_index_does_not_check_out(monkeypatch):
    monkeypatch.setenv("QDRANT_URL", "https://example.test")
    monkeypatch.setattr(retrieval, "cloud_client", lambda: QdrantClient(":memory:"))
    monkeypatch.setattr(retrieval, "build_index", lambda c: 0)
    monkeypatch.setattr(retrieval, "index_problem", lambda c: "it has no sections")
    with pytest.raises(SystemExit, match="it has no sections"):
        index.main()
