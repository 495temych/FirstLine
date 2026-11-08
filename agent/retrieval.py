"""Finds the knowledge base content for a ticket.

Tickets are matched against playbook sections, so one precise section can win. The
winning playbook comes back whole, with any policy or reference that also matches.

Sections are searched in Qdrant: Qdrant Cloud when `QDRANT_URL` is set, built there
with `uv run -m agent.index`, or an in-memory index built on first use otherwise.
"""

import hashlib
import os
import re
from functools import cache

import numpy as np
from qdrant_client import QdrantClient, models
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

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
COLLECTION = "kb_sections"

MIN_LINE_CHARS = 25  # shorter lines are headers or blank rows
MIN_LINE_SCORE = 0.25  # weaker lines are not worth highlighting


@cache
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)


def kb_version() -> str:
    """A short hash of the knowledge base, so runs and the index can be compared."""
    digest = hashlib.sha256()
    for path in sorted(KB_DIR.rglob("*.md")):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:8]


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


def build_index(client: QdrantClient) -> int:
    """Embed every unit into a fresh collection. A unit's point id is its position.

    Vectors are normalized, so the dot product is the cosine similarity the thresholds
    were set on.
    """
    vectors = _get_embeddings()
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(
        COLLECTION,
        vectors_config=models.VectorParams(
            size=vectors.shape[1], distance=models.Distance.DOT
        ),
    )
    stamp = {"kb_version": kb_version(), "model": EMBEDDING_MODEL}
    client.upsert(
        COLLECTION,
        points=[
            models.PointStruct(
                id=i,
                vector=vectors[i].tolist(),
                payload={"doc": u["doc"], "kind": u["kind"], "section": u["section"]}
                | stamp,
            )
            for i, u in enumerate(_get_units())
        ],
    )
    return len(vectors)


def index_problem(client: QdrantClient) -> str | None:
    """Why the index doesn't match the knowledge base, or None if it does."""
    if not client.collection_exists(COLLECTION):
        return "it has no knowledge base yet"
    if client.count(COLLECTION, exact=True).count != len(_get_units()):
        return "it holds a different number of sections"
    [first] = client.retrieve(COLLECTION, ids=[0])
    payload = first.payload or {}
    if payload.get("kb_version") != kb_version():
        return "the knowledge base has changed since it was built"
    if payload.get("model") != EMBEDDING_MODEL:
        return "it was built with another embedding model"
    return None


def cloud_client() -> QdrantClient:
    return QdrantClient(
        url=os.environ["QDRANT_URL"], api_key=os.getenv("QDRANT_API_KEY")
    )


@cache
def _get_index() -> QdrantClient:
    """Qdrant Cloud if `QDRANT_URL` is set and the index is current, else in memory."""
    if not os.getenv("QDRANT_URL"):
        client = QdrantClient(":memory:")
        build_index(client)
        return client
    client = cloud_client()
    problem = index_problem(client)
    if problem:
        raise RuntimeError(
            f"The Qdrant index is out of date: {problem}. Run `uv run -m agent.index`."
        )
    return client


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
    """The query's vector, and its score against every unit, by position."""
    query_vec = _get_model().encode([query], normalize_embeddings=True)[0]
    hits = _get_index().query_points(
        COLLECTION, query=query_vec.tolist(), limit=len(_get_units())
    )
    scores = np.zeros(len(_get_units()))
    for hit in hits.points:
        scores[int(hit.id)] = hit.score
    return query_vec, scores


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
