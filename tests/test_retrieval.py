"""The knowledge base as retrieval sees it. No embeddings are computed here."""

import retrieval


def test_kb_has_17_units_from_12_docs():
    units = retrieval._get_units()
    assert len(units) == 17
    assert len({u["doc"] for u in units}) == 12


def test_no_unit_comes_from_a_project_document():
    docs = {u["doc"] for u in retrieval._get_units()}
    assert not docs & {"SPEC", "ROADMAP", "STATUS", "DECISIONS", "FOUNDATION", "PLAN_FOUNDATION"}
