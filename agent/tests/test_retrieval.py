"""The knowledge base as retrieval sees it. No embeddings are computed here."""

import numpy as np
import pytest
from qdrant_client import QdrantClient

from agent import retrieval
from agent.config import ROOT


def test_kb_has_a_unit_for_each_section_and_document():
    units = retrieval._get_units()
    assert sum(u["kind"] == "playbook" for u in units) == 90
    assert sum(u["kind"] == "policy" for u in units) == 4
    assert len({u["doc"] for u in units}) == 21


def test_policies_are_retrievable_on_their_own():
    docs = {u["doc"] for u in retrieval._get_units()}
    assert "sec-04-account-lockout" in docs
    assert "escalation-queues" in docs


def test_a_playbook_keeps_its_fields_out_of_its_text():
    meta, body = retrieval.read_playbook(
        "---\ntitle: VPN\nfamily: null\n---\n\n## Symptoms\nDrops"
    )
    assert meta == {"title": "VPN", "family": "null"}
    assert body == "## Symptoms\nDrops"


def test_a_returned_playbook_leaves_out_its_symptoms():
    units = retrieval._playbook_units(
        "---\ntitle: VPN\n---\n\n## Symptoms\nDrops\n\n## Fix\nReset", "vpn"
    )
    assert len(units) == 2
    assert units[0]["text"].startswith("VPN\n## Symptoms")
    assert units[0]["full"] == "# VPN\n\n## Fix\nReset"


def test_no_unit_comes_from_a_project_document():
    docs = {u["doc"] for u in retrieval._get_units()}
    project_docs = {p.stem for p in (ROOT / "docs").glob("*.md")}
    assert project_docs
    assert not docs & project_docs


WORDS = ["vpn", "printer", "gateway"]


class FakeEncoder:
    """Embeds text as counts of a few words, so scores are easy to reason about."""

    def encode(self, texts, normalize_embeddings=True):
        vectors = []
        for t in texts:
            v = np.array([t.lower().count(w) for w in WORDS], dtype=float)
            norm = np.linalg.norm(v)
            vectors.append(v / norm if norm else v)
        return np.array(vectors)


def playbook(doc: str, section: str, text: str) -> dict:
    return {
        "doc": doc,
        "kind": "playbook",
        "section": section,
        "text": text,
        "full": f"whole {doc} playbook",
    }


CORPUS = [
    playbook("vpn", "Symptoms", "vpn gateway troubleshooting steps here"),
    playbook("vpn", "Fix", "nothing relevant in this section"),
    playbook("printer", "Symptoms", "printer queue steps"),
    {
        "doc": "policy",
        "kind": "policy",
        "section": None,
        "text": "vpn printer rules for the service desk",
    },
    {
        "doc": "other",
        "kind": "reference",
        "section": "Quirks",
        "text": "nothing relevant in this document",
    },
]


@pytest.fixture
def corpus(monkeypatch):
    monkeypatch.setattr(retrieval, "_get_model", FakeEncoder)
    monkeypatch.setattr(retrieval, "_get_units", lambda: CORPUS)
    retrieval._get_embeddings.cache_clear()
    retrieval._get_index.cache_clear()
    yield
    retrieval._get_embeddings.cache_clear()
    retrieval._get_index.cache_clear()


@pytest.mark.usefixtures("corpus")
def test_the_best_playbook_comes_back_whole_with_a_policy():
    results = retrieval.retrieve("vpn gateway")
    assert [r["doc"] for r in results] == ["vpn", "policy"]
    assert results[0]["text"] == "whole vpn playbook"
    assert results[0]["section"] is None
    assert results[1]["kind"] == "policy"


@pytest.mark.usefixtures("corpus")
def test_playbooks_rank_by_their_best_section():
    ranked = retrieval.rank_playbooks("vpn gateway")
    assert [r["doc"] for r in ranked] == ["vpn", "printer"]
    assert ranked[0]["section"] == "Symptoms"


@pytest.mark.usefixtures("corpus")
def test_retrieve_is_empty_below_the_threshold():
    assert retrieval.retrieve("what is the weather") == []


def test_a_sure_score_needs_no_margin():
    scores = np.array([0.6, 0.0, 0.55])
    ranked = [("a", 0), ("b", 2)]
    assert retrieval._confident(ranked, scores) == 0


def test_a_lower_score_needs_a_clear_margin():
    assert retrieval._confident([("a", 0), ("b", 1)], np.array([0.45, 0.2])) == 0
    assert retrieval._confident([("a", 0), ("b", 1)], np.array([0.45, 0.4])) is None


def test_a_score_below_the_threshold_never_matches():
    assert retrieval._confident([("a", 0), ("b", 1)], np.array([0.3, 0.0])) is None


def test_no_playbooks_means_no_match():
    assert retrieval._confident([], np.array([])) is None


@pytest.mark.usefixtures("corpus")
def test_highlights_skip_short_and_weak_lines():
    query_vec = FakeEncoder().encode(["printer"])[0]
    text = (
        "printer queue is stuck on floor five\nshort\nnothing about that in this line"
    )
    lines = retrieval._top_lines(text, query_vec)
    assert [line["text"] for line in lines] == ["printer queue is stuck on floor five"]


@pytest.mark.usefixtures("corpus")
def test_highlights_of_a_doc_with_only_short_lines_are_empty():
    assert retrieval._top_lines("short\nlines", np.zeros(3)) == []


def test_chunking_drops_the_preamble_and_keeps_each_section():
    sections = retrieval._chunk_by_heading(
        "# Title\nintro\n## One\nfirst\n## Two\nsecond"
    )
    assert [s["section"] for s in sections] == ["One", "Two"]
    assert sections[0]["text"] == "## One\nfirst"


@pytest.mark.usefixtures("corpus")
def test_the_index_scores_every_unit_as_a_dot_product():
    query_vec, scores = retrieval._score("vpn gateway")
    expected = np.dot(retrieval._get_embeddings(), query_vec)
    assert np.allclose(scores, expected)


@pytest.mark.usefixtures("corpus")
def test_a_fresh_index_matches_the_knowledge_base():
    client = QdrantClient(":memory:")
    assert retrieval.index_problem(client) == "it has no knowledge base yet"
    assert retrieval.build_index(client) == len(CORPUS)
    assert retrieval.index_problem(client) is None
    assert retrieval.build_index(client) == len(CORPUS)
    assert client.count(retrieval.COLLECTION).count == len(CORPUS)


@pytest.mark.usefixtures("corpus")
def test_a_changed_knowledge_base_makes_the_index_stale(monkeypatch):
    client = QdrantClient(":memory:")
    retrieval.build_index(client)
    monkeypatch.setattr(retrieval, "kb_version", lambda: "changed")
    assert retrieval.index_problem(client) == (
        "the knowledge base has changed since it was built"
    )
    monkeypatch.setattr(retrieval, "_get_units", lambda: CORPUS[:2])
    assert retrieval.index_problem(client) == (
        "it holds a different number of sections"
    )


@pytest.mark.usefixtures("corpus")
def test_another_embedding_model_makes_the_index_stale(monkeypatch):
    client = QdrantClient(":memory:")
    retrieval.build_index(client)
    monkeypatch.setattr(retrieval, "EMBEDDING_MODEL", "another-model")
    assert retrieval.index_problem(client) == (
        "it was built with another embedding model"
    )


@pytest.mark.usefixtures("corpus")
def test_a_stale_cloud_index_stops_search_with_the_fix(monkeypatch):
    monkeypatch.setenv("QDRANT_URL", "https://example.test")
    monkeypatch.setattr(retrieval, "cloud_client", lambda: QdrantClient(":memory:"))
    with pytest.raises(RuntimeError, match="uv run -m agent.index"):
        retrieval.retrieve("vpn")


@pytest.mark.usefixtures("corpus")
def test_a_current_cloud_index_is_used(monkeypatch):
    cloud = QdrantClient(":memory:")
    retrieval.build_index(cloud)
    monkeypatch.setenv("QDRANT_URL", "https://example.test")
    monkeypatch.setattr(retrieval, "cloud_client", lambda: cloud)
    assert retrieval._get_index() is cloud
