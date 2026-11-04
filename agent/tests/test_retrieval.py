"""The knowledge base as retrieval sees it. No embeddings are computed here."""

import numpy as np
import pytest

from agent import retrieval


def test_kb_has_17_units_from_12_docs():
    units = retrieval._get_units()
    assert len(units) == 17
    assert len({u["doc"] for u in units}) == 12


def test_no_unit_comes_from_a_project_document():
    docs = {u["doc"] for u in retrieval._get_units()}
    assert not docs & {
        "SPEC",
        "ROADMAP",
        "STATUS",
        "DECISIONS",
        "FOUNDATION",
        "PLAN_FOUNDATION",
    }


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


CORPUS = [
    {"doc": "vpn", "section": None, "text": "vpn gateway troubleshooting steps here"},
    {"doc": "printer", "section": None, "text": "printer queue steps\nshort\n"},
    {"doc": "mix", "section": None, "text": "vpn printer notes for the service desk"},
    {"doc": "other", "section": None, "text": "nothing relevant in this document"},
]


@pytest.fixture
def corpus(monkeypatch):
    monkeypatch.setattr(retrieval, "_get_model", FakeEncoder)
    monkeypatch.setattr(retrieval, "_get_units", lambda: CORPUS)
    retrieval._get_embeddings.cache_clear()
    yield
    retrieval._get_embeddings.cache_clear()


@pytest.mark.usefixtures("corpus")
def test_retrieve_returns_top_two_ranked():
    results = retrieval.retrieve("vpn gateway")
    assert [r["doc"] for r in results] == ["vpn", "mix"]
    assert results[0]["score"] >= results[1]["score"]


@pytest.mark.usefixtures("corpus")
def test_retrieve_is_empty_below_the_threshold():
    assert retrieval.retrieve("what is the weather") == []


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
