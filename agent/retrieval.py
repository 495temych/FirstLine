"""Finds the knowledge base content for a ticket.

Tickets are matched against playbook sections, so one precise section can win. The
winning playbook comes back whole, with any policy or reference that also matches.
"""

import re
from functools import cache

import numpy as np
from sentence_transformers import SentenceTransformer

from agent.config import KB_DIR

# A playbook matches if its best section reaches PLAYBOOK_SURE, or reaches
# PLAYBOOK_THRESHOLD and beats the next playbook by PLAYBOOK_MARGIN. Short requests
# score low but clearly favour one playbook. docs/DECISIONS.md shows how these were set.
PLAYBOOK_SURE = 0.52
PLAYBOOK_THRESHOLD = 0.40
PLAYBOOK_MARGIN = 0.15
SUPPORT_THRESHOLD = 0.35  # a policy or reference unit must reach this
TOP_K = 2

# Multi-topic references are split into one retrievable unit per `##` section.
REFERENCE_DOCS = {"company-profile"}
# Written to match tickets, not to help answer them.
MATCH_ONLY_SECTIONS = {"Symptoms"}

MIN_LINE_CHARS = 25  # shorter lines are headers or blank rows
MIN_LINE_SCORE = 0.25  # weaker lines are not worth highlighting


@cache
def _get_model() -> SentenceTransformer:
    return SentenceTransformer("all-MiniLM-L6-v2")


def _chunk_by_heading(text: str) -> list[dict]:
    """Split text into one unit per `##` section, dropping anything before the first."""
    parts = re.split(r"(?m)^## ", text)
    sections = []
    for part in parts[1:]:
        heading, _, body = part.partition("\n")
        sections.append(
            {"section": heading.strip(), "text": f"## {heading}\n{body}".strip()}
        )
    return sections


def read_playbook(text: str) -> tuple[dict, str]:
    """Separate a playbook's fields from its body."""
    _, fields, body = text.split("---\n", 2)
    meta = {}
    for line in fields.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, body.strip()


def _playbook_units(text: str, doc: str) -> list[dict]:
    meta, body = read_playbook(text)
    sections = _chunk_by_heading(body)
    answer = "\n\n".join(
        s["text"] for s in sections if s["section"] not in MATCH_ONLY_SECTIONS
    )
    return [
        {
            "doc": doc,
            "kind": "playbook",
            "section": s["section"],
            "text": f"{meta['title']}\n{s['text']}",
            "full": f"# {meta['title']}\n\n{answer}",
        }
        for s in sections
    ]


@cache
def _get_units() -> list[dict]:
    """Each unit is {"doc", "kind", "section", "text"}, and playbooks add "full"."""
    units = []
    for p in sorted(KB_DIR.rglob("*.md")):
        text = p.read_text()
        if p.parent.name == "playbooks":
            units.extend(_playbook_units(text, p.stem))
        elif p.stem in REFERENCE_DOCS:
            units.extend(
                {"doc": p.stem, "kind": "reference", **section}
                for section in _chunk_by_heading(text)
            )
        else:
            kind = "policy" if p.parent.name == "policies" else "reference"
            units.append({"doc": p.stem, "kind": kind, "section": None, "text": text})
    return units


@cache
def _get_embeddings() -> np.ndarray:
    texts = [u["text"] for u in _get_units()]
    return _get_model().encode(texts, normalize_embeddings=True)


def _top_lines(doc_text: str, query_vec: np.ndarray, n: int = 3) -> list[dict]:
    """Return up to n lines from doc_text most similar to query_vec."""
    lines = [
        line.strip()
        for line in doc_text.split("\n")
        if len(line.strip()) >= MIN_LINE_CHARS
    ]
    if not lines:
        return []
    vecs = _get_model().encode(lines, normalize_embeddings=True)
    scores = np.dot(vecs, query_vec)
    top_n = min(n, len(lines))
    top_idx = np.argsort(scores)[::-1][:top_n]
    return [
        {"text": lines[i], "score": float(scores[i])}
        for i in top_idx
        if scores[i] >= MIN_LINE_SCORE
    ]


def _score(query: str) -> tuple[np.ndarray, np.ndarray]:
    query_vec = _get_model().encode([query], normalize_embeddings=True)[0]
    return query_vec, np.dot(_get_embeddings(), query_vec)


def _rank(scores: np.ndarray) -> list[tuple[str, int]]:
    """Each playbook with the index of its best section, best first."""
    best: dict[str, int] = {}
    for i, unit in enumerate(_get_units()):
        if unit["kind"] != "playbook":
            continue
        if unit["doc"] not in best or scores[i] > scores[best[unit["doc"]]]:
            best[unit["doc"]] = i
    return sorted(best.items(), key=lambda item: -scores[item[1]])


def rank_playbooks(query: str) -> list[dict]:
    """Every playbook, best first, with its score and best section."""
    _, scores = _score(query)
    units = _get_units()
    return [
        {"doc": doc, "section": units[i]["section"], "score": float(scores[i])}
        for doc, i in _rank(scores)
    ]


def _confident(ranked: list[tuple[str, int]], scores: np.ndarray) -> int | None:
    """The best playbook's section index, if it's clearly a match."""
    if not ranked:
        return None
    best = scores[ranked[0][1]]
    runner_up = scores[ranked[1][1]] if len(ranked) > 1 else -1.0
    clear = best >= PLAYBOOK_THRESHOLD and best - runner_up >= PLAYBOOK_MARGIN
    return ranked[0][1] if best >= PLAYBOOK_SURE or clear else None


def retrieve(query: str) -> list[dict]:
    """Return up to TOP_K results: the best playbook if it's a clear match, then the
    best policies and references. Empty if nothing clears the bar.
    """
    query_vec, scores = _score(query)
    units = _get_units()
    results = []

    best = _confident(_rank(scores), scores)
    if best is not None:
        unit = units[best]
        results.append(
            {
                "doc": unit["doc"],
                "kind": "playbook",
                "section": None,
                "text": unit["full"],
                "score": float(scores[best]),
                "highlights": _top_lines(unit["full"], query_vec),
            }
        )

    for i in np.argsort(scores)[::-1]:
        unit = units[i]
        if len(results) >= TOP_K or scores[i] < SUPPORT_THRESHOLD:
            break
        if unit["kind"] == "playbook":
            continue
        results.append(
            {
                "doc": unit["doc"],
                "kind": unit["kind"],
                "section": unit["section"],
                "text": unit["text"],
                "score": float(scores[i]),
                "highlights": _top_lines(unit["text"], query_vec),
            }
        )
    return results
