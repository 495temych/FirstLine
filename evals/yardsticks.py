"""Two free yardsticks for the agent to beat, trained on the knowledge base split.

One always gives the most common answer. The other is a small classifier on the ticket
text. Neither ever decides a real ticket, and the classifier stays out of `agent/`.
"""

from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline

from evals import scoring

TRAINING_SPLIT = "kb"
SEPARATOR = "|"


def target(answer: dict) -> str:
    """A label's first accepted path, with the tool or queue that goes with it."""
    path = answer["paths"][0]
    tool = answer["tools"][0] if path == "AUTO_FIX" and answer["tools"] else ""
    queue = answer["queues"][0] if path == "ESCALATE" and answer["queues"] else ""
    return SEPARATOR.join([path, tool, queue])


def _score(pairs: list[tuple[dict, dict]], predictions: list[str]) -> dict:
    rows = []
    for (_, answer), prediction in zip(pairs, predictions, strict=True):
        path, tool, queue = prediction.split(SEPARATOR)
        rows.append(scoring.score_decision(answer, path, tool or None, queue or None))
    return scoring.decisions(rows)


def _train(training: list[tuple[dict, dict]]) -> tuple[str, Pipeline]:
    """The most common answer and the classifier."""
    texts = [ticket["text"] for ticket, _ in training]
    targets = [target(answer) for _, answer in training]
    classifier = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
        LogisticRegression(max_iter=1000),
    )
    classifier.fit(texts, targets)
    return Counter(targets).most_common(1)[0][0], classifier


def score(pairs: list[tuple[dict, dict]], training: list[tuple[dict, dict]]) -> dict:
    """Both yardsticks' measures on these tickets."""
    common, classifier = _train(training)
    texts = [ticket["text"] for ticket, _ in pairs]
    return {
        "most_common": _score(pairs, [common] * len(pairs)),
        "classifier": _score(pairs, list(classifier.predict(texts))),
    }
